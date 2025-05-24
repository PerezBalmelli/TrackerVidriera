"""
Widget para la configuración de entrada de video en la aplicación TrackerVidriera.
"""
import os
import time
import sys
import cv2
import platform
import logging
from pathlib import Path

if platform.system() == "Windows":
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        FilterGraph = None
        logging.warning("pygrabber no encontrado. Nombres descriptivos de cámara no estarán disponibles en Windows.")
    except Exception as e:
        FilterGraph = None
        logging.error(f"Error al importar pygrabber: {e}", exc_info=True)


from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QLineEdit,
    QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QStandardPaths # Added QStandardPaths for better default dirs

# MODIFIED: Import new CameraThread class
from .camera_thread import CameraThread

logger = logging.getLogger(__name__)

# CameraThread class is now in camera_thread.py

class InputConfigWidget(QWidget):
    """Widget para la configuración de entrada de video (archivo o cámara)."""

    input_type_changed = pyqtSignal(int)
    video_file_selected = pyqtSignal(str)
    camera_selected = pyqtSignal(int, str)
    second_camera_selected = pyqtSignal(int, str)
    status_message = pyqtSignal(str, int)
    frame_received = pyqtSignal(object)
    second_frame_received = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.camera_thread = None
        self.second_camera_thread = None
        self.available_cameras = []

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

        self.camera_panel_label = QLabel("Cámara Fija:")
        self.camera_panel = QWidget()
        camera_layout = QHBoxLayout(self.camera_panel)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(180)
        self.camera_combo.setToolTip("Seleccione la cámara principal (fija)")
        self.camera_combo.currentIndexChanged.connect(self._on_camera_selection_changed)
        refresh_cameras_button = QPushButton("🔄")
        refresh_cameras_button.setToolTip("Actualizar lista de cámaras")
        refresh_cameras_button.setFixedWidth(30)
        refresh_cameras_button.clicked.connect(self.refresh_cameras)
        self.test_camera_button = QPushButton("Info")
        self.test_camera_button.setToolTip("Obtener información y previsualizar cámara fija")
        self.test_camera_button.clicked.connect(self.test_camera_info)
        camera_layout.addWidget(self.camera_combo)
        camera_layout.addWidget(refresh_cameras_button)
        camera_layout.addWidget(self.test_camera_button)
        self.form_layout.addRow(self.camera_panel_label, self.camera_panel)

        self.second_camera_panel_label = QLabel("Cámara Móvil:")
        self.second_camera_panel = QWidget()
        second_camera_layout = QHBoxLayout(self.second_camera_panel)
        second_camera_layout.setContentsMargins(0, 0, 0, 0)
        self.second_camera_combo = QComboBox()
        self.second_camera_combo.setMinimumWidth(180)
        self.second_camera_combo.setToolTip("Seleccione la segunda cámara (móvil)")
        self.second_camera_combo.addItem("Ninguna", -1)
        self.second_camera_combo.currentIndexChanged.connect(self._on_second_camera_selection_changed)
        self.test_second_camera_button = QPushButton("Info")
        self.test_second_camera_button.setToolTip("Obtener información y previsualizar cámara móvil")
        self.test_second_camera_button.clicked.connect(self.test_second_camera_info)
        second_camera_layout.addWidget(self.second_camera_combo)
        second_camera_layout.addWidget(self.test_second_camera_button)
        self.form_layout.addRow(self.second_camera_panel_label, self.second_camera_panel)

        self.info_label_qlabel = QLabel("Información:")
        self.video_info_label = QLabel("No hay entrada seleccionada")
        self.video_info_label.setWordWrap(True)
        self.form_layout.addRow(self.info_label_qlabel, self.video_info_label)

        layout.addWidget(input_group)
        # Set initial visibility based on default input type (usually "Archivo de video")
        default_is_file_mode = (self.input_type_combo.currentIndex() == 0)
        self._set_form_row_visible(self.file_panel_label, self.file_panel, default_is_file_mode)
        self._set_form_row_visible(self.camera_panel_label, self.camera_panel, not default_is_file_mode)
        self._set_form_row_visible(self.second_camera_panel_label, self.second_camera_panel, not default_is_file_mode)


    def _set_form_row_visible(self, label_widget, field_widget, visible):
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
            self.main_camera_info_str = "N/A"
            self.second_camera_info_str = "N/A"
            if self.video_path_edit.text():
                self.update_video_info(self.video_path_edit.text())
            else:
                self.video_file_info_str = "No hay video seleccionado"
        else:
            self.video_file_info_str = "N/A"
            if not self.available_cameras:
                self.refresh_cameras()

            if self.camera_combo.count() > 0:
                 self._on_camera_selection_changed(self.camera_combo.currentIndex())
            else:
                 self.main_camera_info_str = "Ninguna cámara fija disponible"
                 self.frame_received.emit(None)

            if self.second_camera_combo.count() > 0 :
                 self._on_second_camera_selection_changed(self.second_camera_combo.currentIndex())
            else:
                 self.second_camera_info_str = "Ninguna cámara móvil disponible"
                 self.second_frame_received.emit(None)

        self._update_combined_video_info_label()
        self.input_type_changed.emit(index)


    def _browse_video_file(self):
        # Suggest directory from user's documents/videos directory or last used
        documents_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        videos_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MoviesLocation)
        start_dir = videos_path or documents_path or ""

        current_file = self.video_path_edit.text()
        if current_file and os.path.exists(os.path.dirname(current_file)):
            start_dir = os.path.dirname(current_file)

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar video", start_dir,
            "Archivos de video (*.mp4 *.avi *.mov *.mkv);;Todos los archivos (*)"
        )
        if file_path:
            self.video_path_edit.setText(file_path)
            self.update_video_info(file_path)
            self._update_combined_video_info_label()
            self.detener_previsualizacion()
            self.detener_segunda_previsualizacion()
            self.frame_received.emit(None)
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
        if self.input_type_combo.currentIndex() == 0:
            self.video_info_label.setText(self.video_file_info_str)
            self.info_label_qlabel.setText("Info Archivo:")
        else:
            self.info_label_qlabel.setText("Info Cámaras:")
            parts = []
            if self.main_camera_info_str and self.main_camera_info_str != "N/A":
                parts.append(f"Fija: {self.main_camera_info_str}")
            if self.second_camera_info_str and self.second_camera_info_str != "N/A" and self.second_camera_combo.currentIndex() > 0:
                parts.append(f"Móvil: {self.second_camera_info_str}")

            if not parts:
                self.video_info_label.setText("Seleccione cámaras o actualice la lista.")
            else:
                self.video_info_label.setText(" | ".join(parts))


    def _on_camera_selection_changed(self, index):
        if index < 0 or self.camera_combo.count() == 0:
            self.detener_previsualizacion()
            self.main_camera_info_str = "Ninguna cámara fija seleccionada."
            self._update_combined_video_info_label()
            self.frame_received.emit(None)
            self.camera_selected.emit(-1, "Ninguna") # Emit no camera
            return

        camera_data = self.camera_combo.itemData(index)
        camera_text = self.camera_combo.itemText(index)

        if camera_data is None:
            logger.warning("Item de cámara sin datos.")
            self.camera_selected.emit(-1, "Error en datos")
            return

        camera_id = camera_data

        second_cam_data = self.second_camera_combo.currentData()
        if second_cam_data is not None and second_cam_data == camera_id and self.second_camera_combo.currentIndex() > 0 :
            msg = "Conflicto: La cámara fija no puede ser la misma que la móvil si ambas están activas."
            self.status_message.emit(msg, 4000)
            logger.warning(msg)
            self.detener_previsualizacion()
            self.main_camera_info_str = "Error: Conflicto de cámaras"
            self._update_combined_video_info_label()
            self.frame_received.emit(None)
            self.camera_selected.emit(camera_id, f"{camera_text} (Conflicto)")
            return

        self.iniciar_previsualizacion_camara((camera_id, camera_text))
        self.camera_selected.emit(camera_id, camera_text)


    def _on_second_camera_selection_changed(self, index):
        if index < 0 or self.second_camera_combo.count() == 0:
            self.detener_segunda_previsualizacion()
            self.second_camera_info_str = "Ninguna cámara móvil seleccionada."
            self._update_combined_video_info_label()
            self.second_frame_received.emit(None)
            self.second_camera_selected.emit(-1, "Ninguna")
            return

        camera_data = self.second_camera_combo.itemData(index)
        camera_text = self.second_camera_combo.itemText(index)

        if camera_data is None :
             logger.warning("Item de segunda cámara sin datos.")
             self.second_camera_selected.emit(-1, "Error en datos")
             return

        camera_id = camera_data

        if camera_id == -1:
            self.detener_segunda_previsualizacion()
            self.second_camera_info_str = "N/A"
            self._update_combined_video_info_label()
            self.second_frame_received.emit(None)
            self.second_camera_selected.emit(-1, "Ninguna")
            return

        main_cam_data = self.camera_combo.currentData()
        if main_cam_data is not None and main_cam_data == camera_id:
            msg = "Conflicto: La cámara móvil no puede ser la misma que la fija si ambas están activas."
            self.status_message.emit(msg, 4000)
            logger.warning(msg)
            self.detener_segunda_previsualizacion()
            self.second_camera_info_str = "Error: Conflicto de cámaras"
            self._update_combined_video_info_label()
            self.second_frame_received.emit(None)
            self.second_camera_selected.emit(camera_id, f"{camera_text} (Conflicto)")
            return

        self.iniciar_segunda_previsualizacion_camara((camera_id, camera_text))
        self.second_camera_selected.emit(camera_id, camera_text)


    def iniciar_previsualizacion_camara(self, camera_id_tuple):
        self.detener_previsualizacion()
        self.camera_thread = CameraThread(camera_id_tuple, self) # Pass self as parent
        self.camera_thread.frame_received.connect(self._on_frame_received)
        self.camera_thread.camera_info_signal.connect(self._update_main_camera_info_from_thread)
        self.camera_thread.camera_error_signal.connect(self._handle_main_camera_error_from_thread)
        self.camera_thread.start()
        self.main_camera_info_str = f"Iniciando {camera_id_tuple[1]}..."
        self._update_combined_video_info_label()
        self.status_message.emit(f"Iniciando previsualización de {camera_id_tuple[1]} (fija)", 2000)


    def iniciar_segunda_previsualizacion_camara(self, camera_id_tuple):
        self.detener_segunda_previsualizacion()
        self.second_camera_thread = CameraThread(camera_id_tuple, self) # Pass self as parent
        self.second_camera_thread.frame_received.connect(self._on_second_frame_received)
        self.second_camera_thread.camera_info_signal.connect(self._update_second_camera_info_from_thread)
        self.second_camera_thread.camera_error_signal.connect(self._handle_second_camera_error_from_thread)
        self.second_camera_thread.start()
        self.second_camera_info_str = f"Iniciando {camera_id_tuple[1]}..."
        self._update_combined_video_info_label()
        self.status_message.emit(f"Iniciando previsualización de {camera_id_tuple[1]} (móvil)", 2000)


    def _on_frame_received(self, frame):
        self.frame_received.emit(frame)

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
        self.frame_received.emit(None)

    def _handle_second_camera_error_from_thread(self, error_text):
        self.second_camera_info_str = f"Error: {error_text}"
        self._update_combined_video_info_label()
        self.status_message.emit(f"Error Cámara Móvil: {error_text}", 5000)
        self.second_frame_received.emit(None)

    def detener_previsualizacion(self):
        if self.camera_thread:
            logger.info("Deteniendo previsualización de cámara principal.")
            self.camera_thread.stop()
            try: self.camera_thread.frame_received.disconnect(self._on_frame_received)
            except TypeError: pass
            try: self.camera_thread.camera_info_signal.disconnect(self._update_main_camera_info_from_thread)
            except TypeError: pass
            try: self.camera_thread.camera_error_signal.disconnect(self._handle_main_camera_error_from_thread)
            except TypeError: pass
            self.camera_thread = None


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


    def detect_available_cameras(self, max_cameras=5):
        available_cameras = []
        logger.info("Detectando cámaras disponibles...")

        if platform.system() == "Windows" and FilterGraph is not None:
            try:
                graph = FilterGraph()
                device_names = graph.get_input_devices()
                logger.info(f"pygrabber encontró dispositivos: {device_names}")

                valid_pygrabber_cameras = []
                for i, name in enumerate(device_names):
                    if len(valid_pygrabber_cameras) >= max_cameras: break
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                        cap.release()
                        if width > 0 and height > 0:
                             valid_pygrabber_cameras.append((i, name if name else f"Cámara {i} (DSHOW)"))
                        else:
                             logger.warning(f"pygrabber dispositivo {i} ('{name}') abrió pero devolvió dimensiones 0.")
                    else:
                        cap.release()

                if valid_pygrabber_cameras:
                    logger.info(f"Cámaras válidas (pygrabber/DSHOW): {valid_pygrabber_cameras}")
                    return valid_pygrabber_cameras
                else:
                    logger.info("pygrabber no encontró cámaras de video válidas, intentando método estándar.")
            except Exception as e:
                logger.error(f"Error usando pygrabber, recurriendo a método estándar: {e}", exc_info=True)

        logger.info("Usando método estándar de detección de cámaras.")
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                cap.release()
                if width > 0 and height > 0:
                    available_cameras.append((i, f"Cámara {i}"))
                else:
                    logger.warning(f"Cámara {i} abierta pero devolvió dimensiones 0.")
            else:
                cap.release()
        logger.info(f"Cámaras detectadas (estándar): {available_cameras}")
        return available_cameras


    def refresh_cameras(self):
        self.status_message.emit("Buscando cámaras...", 0)
        QApplication.processEvents()

        self.detener_previsualizacion()
        self.detener_segunda_previsualizacion()
        self.frame_received.emit(None)
        self.second_frame_received.emit(None)

        self.camera_combo.clear()
        self.second_camera_combo.clear()
        self.second_camera_combo.addItem("Ninguna", -1)

        self.available_cameras = self.detect_available_cameras(max_cameras=5)

        if not self.available_cameras:
            # Add a default placeholder if no cameras are truly detected
            # self.camera_combo.addItem("Cámara 0 (No Detectada)", 0)
            self.status_message.emit("No se detectaron cámaras. Verifique las conexiones.", 3000)
            self.main_camera_info_str = "No se detectaron cámaras"
            self.second_camera_info_str = "N/A"
        else:
            for cam_id, desc in self.available_cameras:
                self.camera_combo.addItem(desc, cam_id)
                self.second_camera_combo.addItem(desc, cam_id)
            self.status_message.emit(f"Se encontraron {len(self.available_cameras)} cámaras.", 3000)

        self._update_combined_video_info_label()

        if self.input_type_combo.currentIndex() == 1:
            if self.camera_combo.count() > 0:
                self.camera_combo.setCurrentIndex(0)
            else: # No cameras in main combo after refresh (even placeholder)
                self._on_camera_selection_changed(-1) # Explicitly signal no camera

            if self.second_camera_combo.count() > 0:
                self.second_camera_combo.setCurrentIndex(0) # Default to "Ninguna"
            else: # Should not happen as "Ninguna" is always added
                self._on_second_camera_selection_changed(-1)


    def test_camera_info(self):
        if self.input_type_combo.currentIndex() != 1:
            self.status_message.emit("Cambie a 'Cámara en vivo' para obtener info de la cámara fija.", 3000)
            return

        if self.camera_combo.count() == 0:
            self.status_message.emit("No hay cámaras fijas en la lista. Intente refrescar.", 3000)
            return

        camera_id = self.camera_combo.currentData()
        camera_desc = self.camera_combo.currentText()

        if camera_id is None: # Should check for -1 if that's how you represent "no selection" in data
            self.main_camera_info_str = "Ninguna cámara fija seleccionada para probar."
            self._update_combined_video_info_label()
            return

        self.status_message.emit(f"Probando {camera_desc} (fija)...", 0)
        self.iniciar_previsualizacion_camara((camera_id, camera_desc))


    def test_second_camera_info(self):
        if self.input_type_combo.currentIndex() != 1:
            self.status_message.emit("Cambie a 'Cámara en vivo' para obtener info de la cámara móvil.", 3000)
            return

        current_idx = self.second_camera_combo.currentIndex()
        if current_idx <= 0:
            self.status_message.emit("Seleccione una cámara móvil (no 'Ninguna') para probar.", 3000)
            self.second_camera_info_str = "N/A"
            self._update_combined_video_info_label()
            return

        camera_id = self.second_camera_combo.currentData()
        camera_desc = self.second_camera_combo.currentText()

        if camera_id is None or camera_id == -1:
            self.second_camera_info_str = "Ninguna cámara móvil seleccionada para probar."
            self._update_combined_video_info_label()
            return

        self.status_message.emit(f"Probando {camera_desc} (móvil)...", 0)
        self.iniciar_segunda_previsualizacion_camara((camera_id, camera_desc))

    def get_input_type(self):
        return self.input_type_combo.currentIndex()

    def get_video_path(self):
        return self.video_path_edit.text()

    def set_video_path(self, path):
        if path:
            self.video_path_edit.setText(path)
            self.update_video_info(path)
            if self.input_type_combo.currentIndex() == 0:
                self._update_combined_video_info_label()

    def get_selected_camera_id(self):
        if self.input_type_combo.currentIndex() == 1 and self.camera_combo.count() > 0:
            return self.camera_combo.currentData()
        return None # Explicitly None if not applicable

    def get_selected_second_camera_id(self):
        if self.input_type_combo.currentIndex() == 1 and self.second_camera_combo.count() > 0:
            cam_id = self.second_camera_combo.currentData()
            return cam_id if cam_id != -1 else None # Return None if "Ninguna" (-1)
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

        # Temporarily disconnect signals to prevent multiple triggers during setup
        self.input_type_combo.currentIndexChanged.disconnect(self._on_input_type_changed)
        self.camera_combo.currentIndexChanged.disconnect(self._on_camera_selection_changed)
        self.second_camera_combo.currentIndexChanged.disconnect(self._on_second_camera_selection_changed)

        self.input_type_combo.setCurrentIndex(input_type)

        if input_type == 0:
            video_path = settings_dict.get("video_path")
            if video_path:
                self.video_path_edit.setText(video_path) # Use setText, not set_video_path to avoid duplicate info update yet
                self.update_video_info(video_path) # This sets self.video_file_info_str
        else:
            cam_id_to_set = settings_dict.get("camera_id")
            found_cam = False
            if cam_id_to_set is not None:
                for i in range(self.camera_combo.count()):
                    if self.camera_combo.itemData(i) == cam_id_to_set:
                        self.camera_combo.setCurrentIndex(i)
                        found_cam = True
                        break
                if not found_cam and self.camera_combo.count() > 0: # Cam ID not found, select first available
                    self.camera_combo.setCurrentIndex(0)
            elif self.camera_combo.count() > 0: # No cam_id specified, select first
                 self.camera_combo.setCurrentIndex(0)


            second_cam_id_to_set = settings_dict.get("second_camera_id", -1)
            found_second_cam = False
            for i in range(self.second_camera_combo.count()):
                if self.second_camera_combo.itemData(i) == second_cam_id_to_set:
                    self.second_camera_combo.setCurrentIndex(i)
                    found_second_cam = True
                    break
            if not found_second_cam and self.second_camera_combo.count() > 0: # If not found, default to "Ninguna"
                self.second_camera_combo.setCurrentIndex(0) # Index 0 is "Ninguna"

        # Reconnect signals
        self.input_type_combo.currentIndexChanged.connect(self._on_input_type_changed)
        self.camera_combo.currentIndexChanged.connect(self._on_camera_selection_changed)
        self.second_camera_combo.currentIndexChanged.connect(self._on_second_camera_selection_changed)

        # Manually trigger the update logic for the current state
        self._on_input_type_changed(self.input_type_combo.currentIndex())


    def closeEvent(self, event):
        logger.info("InputConfigWidget closeEvent called.")
        self.detener_previsualizacion()
        self.detener_segunda_previsualizacion()
        super().closeEvent(event)