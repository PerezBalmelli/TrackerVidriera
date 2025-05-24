"""
Widget para la configuración de entrada de video en la aplicación TrackerVidriera.
"""
import os
import time
import sys
import cv2
import platform
import logging # Added
from pathlib import Path

if platform.system() == "Windows":
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        FilterGraph = None # Define as None if import fails
        logging.warning("pygrabber no encontrado. Nombres descriptivos de cámara no estarán disponibles en Windows.")
    except Exception as e:
        FilterGraph = None
        logging.error(f"Error al importar pygrabber: {e}", exc_info=True)


from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QLineEdit,
    QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot

logger = logging.getLogger(__name__) # Added

class CameraThread(QThread):
    """Thread para capturar frames de una cámara en segundo plano."""
    frame_received = pyqtSignal(object)
    camera_info_signal = pyqtSignal(str) # Emits (camera_id, info_text)
    camera_error_signal = pyqtSignal(str) # Emits (camera_id, error_text)

    def __init__(self, camera_id_tuple, parent=None): # camera_id_tuple = (id, descriptive_name)
        super().__init__(parent)
        self.camera_id = camera_id_tuple[0]
        self.camera_name = camera_id_tuple[1]
        self.running = False
        self.cap = None

    def run(self):
        try:
            logger.info(f"Intentando abrir cámara ID {self.camera_id} ({self.camera_name})...")
            self.cap = cv2.VideoCapture(self.camera_id)
            if not self.cap.isOpened():
                err_msg = f"Error: No se pudo abrir la cámara ID {self.camera_id} ({self.camera_name})"
                logger.error(err_msg)
                self.camera_error_signal.emit(err_msg)
                return

            # Get camera info
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0: fps = 30.0 # Default FPS if detection fails
            info_text = f"{self.camera_name}: {width}x{height} @ {fps:.2f} FPS"
            logger.info(f"Cámara {self.camera_id} ({self.camera_name}) abierta: {width}x{height} @ {fps:.2f} FPS")
            self.camera_info_signal.emit(info_text)

            self.running = True
            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    self.frame_received.emit(frame)
                else:
                    # logger.debug(f"Frame no recibido de cámara {self.camera_id}")
                    self.msleep(30) # Wait a bit if no frame

                # Adjust sleep based on FPS, but ensure it's not too small to hog CPU
                # and not too large to miss frames. Min sleep 1ms.
                sleep_duration = max(1, int(1000 / fps) - 15) # Subtract some processing time allowance
                self.msleep(sleep_duration)


        except Exception as e:
            err_msg = f"Error en CameraThread (ID {self.camera_id}, {self.camera_name}): {str(e)}"
            logger.error(err_msg, exc_info=True)
            self.camera_error_signal.emit(err_msg)
        finally:
            if self.cap:
                logger.info(f"Liberando cámara ID {self.camera_id} ({self.camera_name}).")
                self.cap.release()
            self.cap = None
            logger.info(f"CameraThread (ID {self.camera_id}, {self.camera_name}) finalizado.")


    def stop(self):
        logger.info(f"Deteniendo CameraThread para ID {self.camera_id} ({self.camera_name})...")
        self.running = False
        if self.isRunning():
             self.wait(1500) # Increased wait time
        if self.cap and self.cap.isOpened():
            logger.info(f"Asegurando liberación de cámara ID {self.camera_id} ({self.camera_name}) al detener.")
            self.cap.release()
        self.cap = None


class InputConfigWidget(QWidget):
    """Widget para la configuración de entrada de video (archivo o cámara)."""

    # Señales para comunicar cambios a la ventana principal
    input_type_changed = pyqtSignal(int) # 0 for file, 1 for camera
    video_file_selected = pyqtSignal(str) # Path to video file
    camera_selected = pyqtSignal(int, str) # (camera_id, camera_description) for main camera
    second_camera_selected = pyqtSignal(int, str) # (camera_id, camera_description) for second camera
    status_message = pyqtSignal(str, int) # (message, timeout)
    frame_received = pyqtSignal(object) # Frame from main camera preview
    second_frame_received = pyqtSignal(object) # Frame from second camera preview

    def __init__(self, parent=None):
        super().__init__(parent)
        self.camera_thread = None
        self.second_camera_thread = None
        self.available_cameras = [] # List of tuples: (id, description)

        # For managing info label text
        self.main_camera_info_str = "N/A"
        self.second_camera_info_str = "N/A"
        self.video_file_info_str = "No hay video seleccionado"


        self._init_ui()
        self._on_input_type_changed(self.input_type_combo.currentIndex())

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        input_group = QGroupBox("Configuración de entrada")
        self.form_layout = QFormLayout(input_group)

        self.input_type_combo = QComboBox()
        self.input_type_combo.addItems(["Archivo de video", "Cámara en vivo"])
        self.input_type_combo.currentIndexChanged.connect(self._on_input_type_changed)
        self.form_layout.addRow("Tipo de entrada:", self.input_type_combo)

        # --- File Panel ---
        self.file_panel_label = QLabel("Archivo:")
        self.file_panel = QWidget()
        file_layout = QHBoxLayout(self.file_panel)
        file_layout.setContentsMargins(0, 0, 0, 0)
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setReadOnly(True)
        browse_button = QPushButton("Explorar...")
        browse_button.clicked.connect(self._browse_video_file)
        file_layout.addWidget(self.video_path_edit)
        file_layout.addWidget(browse_button)
        self.form_layout.addRow(self.file_panel_label, self.file_panel)

        # --- Main Camera Panel ---
        self.camera_panel_label = QLabel("Cámara Fija:")
        self.camera_panel = QWidget()
        camera_layout = QHBoxLayout(self.camera_panel)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(180) # Adjusted width
        self.camera_combo.setToolTip("Seleccione la cámara principal (fija)")
        self.camera_combo.currentIndexChanged.connect(self._on_camera_selection_changed)
        refresh_cameras_button = QPushButton("🔄")
        refresh_cameras_button.setToolTip("Actualizar lista de cámaras")
        refresh_cameras_button.setFixedWidth(30)
        refresh_cameras_button.clicked.connect(self.refresh_cameras)
        self.test_camera_button = QPushButton("Info") # Shorter Text
        self.test_camera_button.setToolTip("Obtener información y previsualizar cámara fija")
        self.test_camera_button.clicked.connect(self.test_camera_info)
        camera_layout.addWidget(self.camera_combo)
        camera_layout.addWidget(refresh_cameras_button)
        camera_layout.addWidget(self.test_camera_button)
        self.form_layout.addRow(self.camera_panel_label, self.camera_panel)

        # --- Second Camera Panel ---
        self.second_camera_panel_label = QLabel("Cámara Móvil:")
        self.second_camera_panel = QWidget()
        second_camera_layout = QHBoxLayout(self.second_camera_panel)
        second_camera_layout.setContentsMargins(0, 0, 0, 0)
        self.second_camera_combo = QComboBox()
        self.second_camera_combo.setMinimumWidth(180) # Adjusted width
        self.second_camera_combo.setToolTip("Seleccione la segunda cámara (móvil)")
        self.second_camera_combo.addItem("Ninguna", -1) # -1 represents no camera
        self.second_camera_combo.currentIndexChanged.connect(self._on_second_camera_selection_changed)
        self.test_second_camera_button = QPushButton("Info") # Shorter Text
        self.test_second_camera_button.setToolTip("Obtener información y previsualizar cámara móvil")
        self.test_second_camera_button.clicked.connect(self.test_second_camera_info)
        second_camera_layout.addWidget(self.second_camera_combo)
        # No refresh button for second cam, uses the main one.
        second_camera_layout.addWidget(self.test_second_camera_button)
        self.form_layout.addRow(self.second_camera_panel_label, self.second_camera_panel)

        # --- Info Label ---
        self.info_label_qlabel = QLabel("Información:") # The actual QLabel for "Información:" text
        self.video_info_label = QLabel("No hay entrada seleccionada") # The QLabel that shows the info
        self.video_info_label.setWordWrap(True)
        self.form_layout.addRow(self.info_label_qlabel, self.video_info_label)

        layout.addWidget(input_group)
        self._set_form_row_visible(self.file_panel_label, self.file_panel, True) # Initial state

    def _set_form_row_visible(self, label_widget, field_widget, visible):
        """Shows or hides a form row (label and field)."""
        if label_widget: label_widget.setVisible(visible)
        if field_widget: field_widget.setVisible(visible)


    def _on_input_type_changed(self, index):
        is_file_mode = (index == 0)
        is_camera_mode = (index == 1)

        self._set_form_row_visible(self.file_panel_label, self.file_panel, is_file_mode)
        self._set_form_row_visible(self.camera_panel_label, self.camera_panel, is_camera_mode)
        self._set_form_row_visible(self.second_camera_panel_label, self.second_camera_panel, is_camera_mode)

        if is_file_mode:
            self.detener_previsualizacion()
            self.detener_segunda_previsualizacion()
            self.main_camera_info_str = "N/A" # Reset camera info
            self.second_camera_info_str = "N/A"
            if self.video_path_edit.text():
                self.update_video_info(self.video_path_edit.text()) # Updates self.video_file_info_str
            else:
                self.video_file_info_str = "No hay video seleccionado"
        else: # Camera mode
            self.video_file_info_str = "N/A" # Reset file info
            if not self.available_cameras: # If cameras list is empty
                self.refresh_cameras() # Attempt to populate

            # Trigger selection change if cameras are available to start preview
            if self.camera_combo.count() > 0:
                 self._on_camera_selection_changed(self.camera_combo.currentIndex())
            else: # No cameras listed in combo
                 self.main_camera_info_str = "Ninguna cámara fija disponible"
                 self.frame_received.emit(None)

            if self.second_camera_combo.count() > 0 : # At least "Ninguna" is present
                 self._on_second_camera_selection_changed(self.second_camera_combo.currentIndex())
            else: # Should not happen if "Ninguna" is always added
                 self.second_camera_info_str = "Ninguna cámara móvil disponible"
                 self.second_frame_received.emit(None)

        self._update_combined_video_info_label()
        self.input_type_changed.emit(index)


    def _browse_video_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar video", "",
            "Archivos de video (*.mp4 *.avi *.mov *.mkv);;Todos los archivos (*)"
        )
        if file_path:
            self.video_path_edit.setText(file_path)
            self.update_video_info(file_path) # This will set self.video_file_info_str
            self._update_combined_video_info_label()
            self.detener_previsualizacion() # Stop camera previews if running
            self.detener_segunda_previsualizacion()
            self.frame_received.emit(None) # Clear preview frames
            self.second_frame_received.emit(None)
            self.video_file_selected.emit(file_path)
            logger.info(f"Archivo de video seleccionado: {file_path}")


    def update_video_info(self, video_path_str):
        try:
            video_path = Path(video_path_str)
            if not video_path.is_file():
                self.video_file_info_str = "Error: Archivo no encontrado."
                logger.warning(f"Archivo de video no encontrado: {video_path_str}")
                return

            cap = cv2.VideoCapture(video_path_str)
            if not cap.isOpened():
                self.video_file_info_str = "Error al abrir el video."
                logger.error(f"No se pudo abrir el video: {video_path_str}")
                return

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            self.video_file_info_str = f"{video_path.name} | {width}x{height}, FPS: {fps:.2f}, Dur: {duration:.2f}s"
            cap.release()
        except Exception as e:
            self.video_file_info_str = f"Error al leer info del video: {str(e)}"
            logger.error(f"Error al leer info de {video_path_str}: {e}", exc_info=True)


    def _update_combined_video_info_label(self):
        """Updates the main info label based on current mode and info strings."""
        if self.input_type_combo.currentIndex() == 0: # File mode
            self.video_info_label.setText(self.video_file_info_str)
            self.info_label_qlabel.setText("Info Archivo:")
        else: # Camera mode
            self.info_label_qlabel.setText("Info Cámaras:")
            parts = []
            if self.main_camera_info_str and self.main_camera_info_str != "N/A":
                parts.append(f"Fija: {self.main_camera_info_str}")
            if self.second_camera_info_str and self.second_camera_info_str != "N/A" and self.second_camera_combo.currentIndex() > 0: # Only show if not "Ninguna"
                parts.append(f"Móvil: {self.second_camera_info_str}")

            if not parts:
                self.video_info_label.setText("Seleccione cámaras o actualice la lista.")
            else:
                self.video_info_label.setText(" | ".join(parts))


    def _on_camera_selection_changed(self, index):
        if index < 0 or self.camera_combo.count() == 0: # No item selected or combo empty
            self.detener_previsualizacion()
            self.main_camera_info_str = "Ninguna cámara fija seleccionada."
            self._update_combined_video_info_label()
            self.frame_received.emit(None)
            return

        camera_data = self.camera_combo.itemData(index)
        camera_text = self.camera_combo.itemText(index)

        if camera_data is None: # Should not happen if items always have data
            logger.warning("Item de cámara sin datos.")
            return

        camera_id = camera_data # Assuming data is the ID

        # Check for conflict with second camera
        second_cam_data = self.second_camera_combo.currentData()
        if second_cam_data is not None and second_cam_data == camera_id and self.second_camera_combo.currentIndex() > 0 : # currentIndex > 0 means not "Ninguna"
            msg = "Conflicto: La cámara fija no puede ser la misma que la móvil si ambas están activas."
            self.status_message.emit(msg, 4000)
            logger.warning(msg)
            # Do not start preview, revert or clear selection if needed by UX design
            # For now, just display message and potentially stop existing preview
            self.detener_previsualizacion()
            self.main_camera_info_str = "Error: Conflicto de cámaras"
            self._update_combined_video_info_label()
            self.frame_received.emit(None)
            return

        self.iniciar_previsualizacion_camara((camera_id, camera_text))
        self.camera_selected.emit(camera_id, camera_text)


    def _on_second_camera_selection_changed(self, index):
        if index < 0 or self.second_camera_combo.count() == 0: # Combo empty (should not happen)
            self.detener_segunda_previsualizacion()
            self.second_camera_info_str = "Ninguna cámara móvil seleccionada."
            self._update_combined_video_info_label()
            self.second_frame_received.emit(None)
            return

        camera_data = self.second_camera_combo.itemData(index)
        camera_text = self.second_camera_combo.itemText(index)

        if camera_data is None :
             logger.warning("Item de segunda cámara sin datos.")
             return

        camera_id = camera_data

        if camera_id == -1: # "Ninguna" selected
            self.detener_segunda_previsualizacion()
            self.second_camera_info_str = "N/A" # Reset specific info string
            self._update_combined_video_info_label()
            self.second_frame_received.emit(None)
            self.second_camera_selected.emit(-1, "Ninguna")
            return

        # Check for conflict with main camera
        main_cam_data = self.camera_combo.currentData()
        if main_cam_data is not None and main_cam_data == camera_id:
            msg = "Conflicto: La cámara móvil no puede ser la misma que la fija si ambas están activas."
            self.status_message.emit(msg, 4000)
            logger.warning(msg)
            self.detener_segunda_previsualizacion()
            self.second_camera_info_str = "Error: Conflicto de cámaras"
            self._update_combined_video_info_label()
            self.second_frame_received.emit(None)
            return

        self.iniciar_segunda_previsualizacion_camara((camera_id, camera_text))
        self.second_camera_selected.emit(camera_id, camera_text)


    def iniciar_previsualizacion_camara(self, camera_id_tuple): # (id, description)
        self.detener_previsualizacion()
        self.camera_thread = CameraThread(camera_id_tuple)
        self.camera_thread.frame_received.connect(self._on_frame_received)
        self.camera_thread.camera_info_signal.connect(self._update_main_camera_info_from_thread)
        self.camera_thread.camera_error_signal.connect(self._handle_main_camera_error_from_thread)
        self.camera_thread.start()
        self.main_camera_info_str = f"Iniciando {camera_id_tuple[1]}..."
        self._update_combined_video_info_label()
        self.status_message.emit(f"Iniciando previsualización de {camera_id_tuple[1]} (fija)", 2000)


    def iniciar_segunda_previsualizacion_camara(self, camera_id_tuple): # (id, description)
        self.detener_segunda_previsualizacion()
        self.second_camera_thread = CameraThread(camera_id_tuple)
        self.second_camera_thread.frame_received.connect(self._on_second_frame_received)
        self.second_camera_thread.camera_info_signal.connect(self._update_second_camera_info_from_thread)
        self.second_camera_thread.camera_error_signal.connect(self._handle_second_camera_error_from_thread)
        self.second_camera_thread.start()
        self.second_camera_info_str = f"Iniciando {camera_id_tuple[1]}..."
        self._update_combined_video_info_label()
        self.status_message.emit(f"Iniciando previsualización de {camera_id_tuple[1]} (móvil)", 2000)


    @pyqtSlot(object)
    def _on_frame_received(self, frame):
        self.frame_received.emit(frame)

    @pyqtSlot(object)
    def _on_second_frame_received(self, frame):
        self.second_frame_received.emit(frame)

    def _update_main_camera_info_from_thread(self, info_text):
        self.main_camera_info_str = info_text
        self._update_combined_video_info_label()

    def _update_second_camera_info_from_thread(self, info_text):
        self.second_camera_info_str = info_text
        self._update_combined_video_info_label()

    def _handle_main_camera_error_from_thread(self, error_text):
        self.main_camera_info_str = f"Error: {error_text}"
        self._update_combined_video_info_label()
        self.status_message.emit(f"Error Cámara Fija: {error_text}", 5000)
        self.frame_received.emit(None) # Clear preview

    def _handle_second_camera_error_from_thread(self, error_text):
        self.second_camera_info_str = f"Error: {error_text}"
        self._update_combined_video_info_label()
        self.status_message.emit(f"Error Cámara Móvil: {error_text}", 5000)
        self.second_frame_received.emit(None) # Clear preview

    def detener_previsualizacion(self):
        if self.camera_thread:
            logger.info("Deteniendo previsualización de cámara principal.")
            self.camera_thread.stop()
            # Attempt to disconnect, but catch TypeError if already disconnected or never connected
            try: self.camera_thread.frame_received.disconnect(self._on_frame_received)
            except TypeError: pass
            try: self.camera_thread.camera_info_signal.disconnect(self._update_main_camera_info_from_thread)
            except TypeError: pass
            try: self.camera_thread.camera_error_signal.disconnect(self._handle_main_camera_error_from_thread)
            except TypeError: pass
            self.camera_thread = None
            # self.main_camera_info_str = "N/A" # Reset info when explicitly stopped
            # self._update_combined_video_info_label()


    def detener_segunda_previsualizacion(self):
        if self.second_camera_thread:
            logger.info("Deteniendo previsualización de segunda cámara.")
            self.second_camera_thread.stop()
            try: self.second_camera_thread.frame_received.disconnect(self._on_second_frame_received)
            except TypeError: pass
            try: self.second_camera_thread.camera_info_signal.disconnect(self._update_second_camera_info_from_thread)
            except TypeError: pass
            try: self.second_camera_thread.camera_error_signal.disconnect(self._handle_second_camera_error_from_thread)
            except TypeError: pass
            self.second_camera_thread = None
            # self.second_camera_info_str = "N/A"
            # self._update_combined_video_info_label()


    def detect_available_cameras(self, max_cameras=5):
        available_cameras = [] # List of (id, description)
        logger.info("Detectando cámaras disponibles...")

        if platform.system() == "Windows" and FilterGraph is not None:
            try:
                graph = FilterGraph()
                device_names = graph.get_input_devices() # Names from pygrabber
                logger.info(f"pygrabber encontró dispositivos: {device_names}")

                # Check if these devices are valid video capture devices
                valid_pygrabber_cameras = []
                for i, name in enumerate(device_names):
                    if len(valid_pygrabber_cameras) >= max_cameras: break
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) # Try with DSHOW backend specifically
                    if cap.isOpened():
                        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                        cap.release()
                        if width > 0 and height > 0:
                             valid_pygrabber_cameras.append((i, name if name else f"Cámara {i} (DSHOW)"))
                        else:
                             logger.warning(f"pygrabber dispositivo {i} ('{name}') abrió pero devolvió dimensiones 0.")
                    else:
                        cap.release() # Ensure release

                if valid_pygrabber_cameras:
                    logger.info(f"Cámaras válidas (pygrabber/DSHOW): {valid_pygrabber_cameras}")
                    return valid_pygrabber_cameras
                else:
                    logger.info("pygrabber no encontró cámaras de video válidas, intentando método estándar.")
            except Exception as e:
                logger.error(f"Error usando pygrabber, recurriendo a método estándar: {e}", exc_info=True)

        # Fallback or non-Windows
        logger.info("Usando método estándar de detección de cámaras.")
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                cap.release()
                if width > 0 and height > 0:
                    available_cameras.append((i, f"Cámara {i}"))
                else: # Opened but returned 0 dimensions, might not be a usable camera
                    logger.warning(f"Cámara {i} abierta pero devolvió dimensiones 0.")
            else:
                cap.release() # Ensure it's released even if not opened.
        logger.info(f"Cámaras detectadas (estándar): {available_cameras}")
        return available_cameras


    def refresh_cameras(self):
        self.status_message.emit("Buscando cámaras...", 0)
        QApplication.processEvents()

        self.detener_previsualizacion() # Stop current previews before refreshing
        self.detener_segunda_previsualizacion()
        self.frame_received.emit(None)
        self.second_frame_received.emit(None)

        self.camera_combo.clear()
        self.second_camera_combo.clear()
        self.second_camera_combo.addItem("Ninguna", -1) # Add "Ninguna" first

        self.available_cameras = self.detect_available_cameras(max_cameras=5)

        if not self.available_cameras:
            self.camera_combo.addItem("Cámara 0 (predeterminada)", 0) # Add a default if none found
            self.status_message.emit("No se detectaron cámaras. Puede intentar con 'Cámara 0'.", 3000)
            self.main_camera_info_str = "No se detectaron cámaras"
            self.second_camera_info_str = "N/A"
        else:
            for cam_id, desc in self.available_cameras:
                self.camera_combo.addItem(desc, cam_id)
                self.second_camera_combo.addItem(desc, cam_id)
            self.status_message.emit(f"Se encontraron {len(self.available_cameras)} cámaras.", 3000)

        self._update_combined_video_info_label()

        # If in camera mode, try to activate the first camera in the list
        if self.input_type_combo.currentIndex() == 1:
            if self.camera_combo.count() > 0:
                self.camera_combo.setCurrentIndex(0) # Triggers _on_camera_selection_changed
            if self.second_camera_combo.count() > 0: # "Ninguna" is at index 0
                self.second_camera_combo.setCurrentIndex(0) # Default to "Ninguna"

    def test_camera_info(self):
        if self.input_type_combo.currentIndex() != 1:
            self.status_message.emit("Cambie a 'Cámara en vivo' para obtener info de la cámara fija.", 3000)
            return

        if self.camera_combo.count() == 0:
            self.status_message.emit("No hay cámaras fijas en la lista. Intente refrescar.", 3000)
            return

        camera_id = self.camera_combo.currentData()
        camera_desc = self.camera_combo.currentText()

        if camera_id is None:
            self.main_camera_info_str = "Ninguna cámara fija seleccionada para probar."
            self._update_combined_video_info_label()
            return

        self.status_message.emit(f"Probando {camera_desc} (fija)...", 0)
        # Re-initiate preview which also gets info
        self.iniciar_previsualizacion_camara((camera_id, camera_desc))


    def test_second_camera_info(self):
        if self.input_type_combo.currentIndex() != 1:
            self.status_message.emit("Cambie a 'Cámara en vivo' para obtener info de la cámara móvil.", 3000)
            return

        current_idx = self.second_camera_combo.currentIndex()
        if current_idx <= 0: # "Ninguna" is at index 0, or list is empty
            self.status_message.emit("Seleccione una cámara móvil (no 'Ninguna') para probar.", 3000)
            self.second_camera_info_str = "N/A"
            self._update_combined_video_info_label()
            return

        camera_id = self.second_camera_combo.currentData()
        camera_desc = self.second_camera_combo.currentText()

        if camera_id is None or camera_id == -1: # Should be caught by current_idx check
            self.second_camera_info_str = "Ninguna cámara móvil seleccionada para probar."
            self._update_combined_video_info_label()
            return

        self.status_message.emit(f"Probando {camera_desc} (móvil)...", 0)
        self.iniciar_segunda_previsualizacion_camara((camera_id, camera_desc))

    # --- Public Getters/Setters for MainWindow ---
    def get_input_type(self):
        return self.input_type_combo.currentIndex()

    def get_video_path(self):
        return self.video_path_edit.text()

    def set_video_path(self, path):
        if path:
            self.video_path_edit.setText(path)
            self.update_video_info(path) # Sets self.video_file_info_str
            if self.input_type_combo.currentIndex() == 0: # If in file mode
                self._update_combined_video_info_label()

    def get_selected_camera_id(self):
        if self.input_type_combo.currentIndex() == 1 and self.camera_combo.count() > 0:
            return self.camera_combo.currentData()
        return None

    def get_selected_second_camera_id(self):
        if self.input_type_combo.currentIndex() == 1 and self.second_camera_combo.count() > 0:
            cam_id = self.second_camera_combo.currentData()
            return cam_id if cam_id != -1 else None
        return None

    def get_selected_camera_description(self):
        if self.input_type_combo.currentIndex() == 1 and self.camera_combo.count() > 0:
            return self.camera_combo.currentText()
        return "N/A"

    def get_selected_second_camera_description(self):
        if self.input_type_combo.currentIndex() == 1 and self.second_camera_combo.count() > 0:
            if self.second_camera_combo.currentData() != -1:
                return self.second_camera_combo.currentText()
        return "Ninguna"

    def get_all_settings(self):
        return {
            "input_type": self.get_input_type(),
            "video_path": self.get_video_path() if self.get_input_type() == 0 else None,
            "camera_id": self.get_selected_camera_id() if self.get_input_type() == 1 else None,
            "second_camera_id": self.get_selected_second_camera_id() if self.get_input_type() == 1 else None,
        }

    def set_all_settings(self, settings_dict):
        input_type = settings_dict.get("input_type", 0)
        # Critical: Set combo index *before* calling _on_input_type_changed
        # to ensure it has the correct context.
        self.input_type_combo.setCurrentIndex(input_type)
        # _on_input_type_changed will handle visibility and initial camera/file setup

        if input_type == 0: # Archivo
            video_path = settings_dict.get("video_path")
            if video_path:
                self.set_video_path(video_path) # This updates info string and label if in file mode
        else: # Cámara
            # Refresh cameras to ensure the saved IDs can be found
            # self.refresh_cameras() # This might be too disruptive, better to assume they are there
            # _on_input_type_changed will call refresh if list is empty.

            cam_id_to_set = settings_dict.get("camera_id")
            if cam_id_to_set is not None:
                for i in range(self.camera_combo.count()):
                    if self.camera_combo.itemData(i) == cam_id_to_set:
                        self.camera_combo.setCurrentIndex(i)
                        # _on_camera_selection_changed is triggered by setCurrentIndex
                        break

            second_cam_id_to_set = settings_dict.get("second_camera_id", -1) # Default to -1 (Ninguna)
            for i in range(self.second_camera_combo.count()):
                if self.second_camera_combo.itemData(i) == second_cam_id_to_set:
                    self.second_camera_combo.setCurrentIndex(i)
                    # _on_second_camera_selection_changed is triggered
                    break
        # Ensure the UI reflects the loaded settings correctly after all changes
        self._on_input_type_changed(self.input_type_combo.currentIndex())


    def closeEvent(self, event): # This method is usually for QWidget/QMainWindow, not typically child widgets
        logger.info("InputConfigWidget closeEvent called.")
        self.detener_previsualizacion()
        self.detener_segunda_previsualizacion()
        super().closeEvent(event)