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
from PyQt6.QtCore import Qt, pyqtSignal, QStandardPaths

from .camera_thread import CameraThread

logger = logging.getLogger(__name__)

class InputConfigWidget(QWidget):
    """Widget para la configuración de entrada de video (archivo, cámara o YouTube)."""

    input_type_changed = pyqtSignal(int)
    video_file_selected = pyqtSignal(str)
    youtube_url_changed = pyqtSignal(str) # New signal for YouTube URL
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
        self.youtube_url_info_str = "No hay URL de YouTube" # New info string

        self._init_ui()
        self._on_input_type_changed(self.input_type_combo.currentIndex())

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        input_group = QGroupBox("Configuración de entrada")
        self.form_layout = QFormLayout(input_group)

        self.input_type_combo = QComboBox()
        # Added "YouTube Stream"
        self.input_type_combo.addItems(["Archivo de video", "Cámara en vivo", "YouTube Stream"])
        self.input_type_combo.currentIndexChanged.connect(self._on_input_type_changed)
        self.form_layout.addRow("Tipo de entrada:", self.input_type_combo)

        # File Panel
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

        # YouTube Panel (New)
        self.youtube_panel_label = QLabel("URL YouTube:")
        self.youtube_panel = QWidget()
        youtube_layout = QHBoxLayout(self.youtube_panel)
        youtube_layout.setContentsMargins(0,0,0,0)
        self.youtube_url_edit = QLineEdit()
        self.youtube_url_edit.setPlaceholderText("Ej: https://www.youtube.com/watch?v=...")
        self.youtube_url_edit.textChanged.connect(self._on_youtube_url_changed)
        youtube_layout.addWidget(self.youtube_url_edit)
        self.form_layout.addRow(self.youtube_panel_label, self.youtube_panel)


        # Camera Panel
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

        # Second Camera Panel
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
        default_is_file_mode = (self.input_type_combo.currentIndex() == 0)
        default_is_camera_mode = (self.input_type_combo.currentIndex() == 1)
        default_is_youtube_mode = (self.input_type_combo.currentIndex() == 2)

        self._set_form_row_visible(self.file_panel_label, self.file_panel, default_is_file_mode)
        self._set_form_row_visible(self.youtube_panel_label, self.youtube_panel, default_is_youtube_mode)
        self._set_form_row_visible(self.camera_panel_label, self.camera_panel, default_is_camera_mode)
        self._set_form_row_visible(self.second_camera_panel_label, self.second_camera_panel, default_is_camera_mode)


    def _set_form_row_visible(self, label_widget, field_widget, visible):
        if label_widget: label_widget.setVisible(visible)
        if field_widget: field_widget.setVisible(visible)


    def _on_input_type_changed(self, index):
        is_file_mode = (index == 0)
        is_camera_mode = (index == 1)
        is_youtube_mode = (index == 2) # New condition

        self._set_form_row_visible(self.file_panel_label, self.file_panel, is_file_mode)
        self._set_form_row_visible(self.youtube_panel_label, self.youtube_panel, is_youtube_mode) # Show/hide YouTube panel
        self._set_form_row_visible(self.camera_panel_label, self.camera_panel, is_camera_mode)
        self._set_form_row_visible(self.second_camera_panel_label, self.second_camera_panel, is_camera_mode)

        self.detener_previsualizacion()
        self.detener_segunda_previsualizacion()
        self.frame_received.emit(None)
        self.second_frame_received.emit(None)

        if is_file_mode:
            self.main_camera_info_str = "N/A"
            self.second_camera_info_str = "N/A"
            self.youtube_url_info_str = "N/A"
            if self.video_path_edit.text():
                self.update_video_info(self.video_path_edit.text())
            else:
                self.video_file_info_str = "No hay video seleccionado"
        elif is_camera_mode:
            self.video_file_info_str = "N/A"
            self.youtube_url_info_str = "N/A"
            if not self.available_cameras:
                self.refresh_cameras()

            if self.camera_combo.count() > 0:
                 self._on_camera_selection_changed(self.camera_combo.currentIndex())
            else:
                 self.main_camera_info_str = "Ninguna cámara fija disponible"

            if self.second_camera_combo.count() > 0 :
                 self._on_second_camera_selection_changed(self.second_camera_combo.currentIndex())
            else:
                 self.second_camera_info_str = "Ninguna cámara móvil disponible"
        elif is_youtube_mode: # New logic for YouTube
            self.main_camera_info_str = "N/A"
            self.second_camera_info_str = "N/A"
            self.video_file_info_str = "N/A"
            if self.youtube_url_edit.text():
                self.youtube_url_info_str = f"URL: {self.youtube_url_edit.text()}"
            else:
                self.youtube_url_info_str = "Ingrese una URL de YouTube"


        self._update_combined_video_info_label()
        self.input_type_changed.emit(index)

    def _on_youtube_url_changed(self, url_text): # New method
        if self.input_type_combo.currentIndex() == 2: # YouTube mode
            if url_text:
                self.youtube_url_info_str = f"URL: {url_text}"
                self.youtube_url_changed.emit(url_text) # Emit signal for MainWindow
            else:
                self.youtube_url_info_str = "Ingrese una URL de YouTube"
            self._update_combined_video_info_label()


    def _browse_video_file(self):
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
        current_index = self.input_type_combo.currentIndex()
        if current_index == 0: # File
            self.video_info_label.setText(self.video_file_info_str)
            self.info_label_qlabel.setText("Info Archivo:")
        elif current_index == 1: # Camera
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
        elif current_index == 2: # YouTube
            self.video_info_label.setText(self.youtube_url_info_str)
            self.info_label_qlabel.setText("Info YouTube:")


    def _on_camera_selection_changed(self, index):
        if index < 0 or self.camera_combo.count() == 0:
            self.detener_previsualizacion()
            self.main_camera_info_str = "Ninguna cámara fija seleccionada."
            self._update_combined_video_info_label()
            self.frame_received.emit(None)
            self.camera_selected.emit(-1, "Ninguna")
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
        self.camera_thread = CameraThread(camera_id_tuple, self)
        self.camera_thread.frame_received.connect(self._on_frame_received)
        self.camera_thread.camera_info_signal.connect(self._update_main_camera_info_from_thread)
        self.camera_thread.camera_error_signal.connect(self._handle_main_camera_error_from_thread)
        self.camera_thread.start()
        self.main_camera_info_str = f"Iniciando {camera_id_tuple[1]}..."
        self._update_combined_video_info_label()
        self.status_message.emit(f"Iniciando previsualización de {camera_id_tuple[1]} (fija)", 2000)


    def iniciar_segunda_previsualizacion_camara(self, camera_id_tuple):
        self.detener_segunda_previsualizacion()
        self.second_camera_thread = CameraThread(camera_id_tuple, self)
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
            self.status_message.emit("No se detectaron cámaras. Verifique las conexiones.", 3000)
            self.main_camera_info_str = "No se detectaron cámaras"
            self.second_camera_info_str = "N/A"
        else:
            for cam_id, desc in self.available_cameras:
                self.camera_combo.addItem(desc, cam_id)
                self.second_camera_combo.addItem(desc, cam_id)
            self.status_message.emit(f"Se encontraron {len(self.available_cameras)} cámaras.", 3000)

        self._update_combined_video_info_label()

        if self.input_type_combo.currentIndex() == 1: # Camera mode
            if self.camera_combo.count() > 0:
                self.camera_combo.setCurrentIndex(0)
            else:
                self._on_camera_selection_changed(-1)

            if self.second_camera_combo.count() > 0:
                self.second_camera_combo.setCurrentIndex(0)
            else:
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

        if camera_id is None:
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
        if current_idx <= 0: # Index 0 is "Ninguna"
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
            if self.input_type_combo.currentIndex() == 0: # File mode
                self._update_combined_video_info_label()

    def get_youtube_url(self): # New method
        return self.youtube_url_edit.text()

    def set_youtube_url(self, url): # New method
        if url:
            self.youtube_url_edit.setText(url)
            if self.input_type_combo.currentIndex() == 2: # YouTube mode
                self.youtube_url_info_str = f"URL: {url}"
                self._update_combined_video_info_label()


    def get_selected_camera_id(self):
        if self.input_type_combo.currentIndex() == 1 and self.camera_combo.count() > 0: # Camera mode
            return self.camera_combo.currentData()
        return None

    def get_selected_second_camera_id(self):
        if self.input_type_combo.currentIndex() == 1 and self.second_camera_combo.count() > 0: # Camera mode
            cam_id = self.second_camera_combo.currentData()
            return cam_id if cam_id != -1 else None
        return None

    def get_selected_camera_description(self):
        if self.input_type_combo.currentIndex() == 1 and self.camera_combo.count() > 0: # Camera mode
            return self.camera_combo.currentText()
        return "N/A"

    def get_selected_second_camera_description(self):
        if self.input_type_combo.currentIndex() == 1 and self.second_camera_combo.count() > 0: # Camera mode
            if self.second_camera_combo.currentData() != -1:
                return self.second_camera_combo.currentText()
        return "Ninguna"

    def get_all_settings(self):
        input_type = self.get_input_type()
        settings = {"input_type": input_type}
        if input_type == 0: # File
            settings["video_path"] = self.get_video_path()
        elif input_type == 1: # Camera
            settings["camera_id"] = self.get_selected_camera_id()
            settings["second_camera_id"] = self.get_selected_second_camera_id()
        elif input_type == 2: # YouTube
            settings["youtube_url"] = self.get_youtube_url()
        return settings


    def set_all_settings(self, settings_dict):
        input_type = settings_dict.get("input_type", 0)

        # Temporarily disconnect signals to avoid multiple triggers and recursive calls
        try: self.input_type_combo.currentIndexChanged.disconnect(self._on_input_type_changed)
        except TypeError: pass
        try: self.camera_combo.currentIndexChanged.disconnect(self._on_camera_selection_changed)
        except TypeError: pass
        try: self.second_camera_combo.currentIndexChanged.disconnect(self._on_second_camera_selection_changed)
        except TypeError: pass
        try: self.youtube_url_edit.textChanged.disconnect(self._on_youtube_url_changed)
        except TypeError: pass


        self.input_type_combo.setCurrentIndex(input_type)

        if input_type == 0: # File
            video_path = settings_dict.get("video_path")
            if video_path:
                self.video_path_edit.setText(video_path) # Use setText directly
                self.update_video_info(video_path) # This sets self.video_file_info_str
        elif input_type == 1: # Camera
            cam_id_to_set = settings_dict.get("camera_id")
            found_cam = False
            if cam_id_to_set is not None:
                for i in range(self.camera_combo.count()):
                    if self.camera_combo.itemData(i) == cam_id_to_set:
                        self.camera_combo.setCurrentIndex(i)
                        found_cam = True
                        break
                if not found_cam and self.camera_combo.count() > 0:
                    self.camera_combo.setCurrentIndex(0) # Default to first if saved ID not found
            elif self.camera_combo.count() > 0: # No cam_id specified in settings, select first
                 self.camera_combo.setCurrentIndex(0)

            second_cam_id_to_set = settings_dict.get("second_camera_id", -1) # Default to -1 (Ninguna)
            found_second_cam = False
            for i in range(self.second_camera_combo.count()):
                if self.second_camera_combo.itemData(i) == second_cam_id_to_set:
                    self.second_camera_combo.setCurrentIndex(i)
                    found_second_cam = True
                    break
            if not found_second_cam: # If specific ID not found, try to set to "Ninguna"
                ninguna_idx = self.second_camera_combo.findData(-1)
                if ninguna_idx != -1:
                    self.second_camera_combo.setCurrentIndex(ninguna_idx)
                elif self.second_camera_combo.count() > 0: # Fallback to first item if "Ninguna" isn't there (should be)
                    self.second_camera_combo.setCurrentIndex(0)

        elif input_type == 2: # YouTube
            youtube_url = settings_dict.get("youtube_url")
            if youtube_url:
                self.youtube_url_edit.setText(youtube_url) # Use setText directly
                self.youtube_url_info_str = f"URL: {youtube_url}"

        # Reconnect signals
        self.input_type_combo.currentIndexChanged.connect(self._on_input_type_changed)
        self.camera_combo.currentIndexChanged.connect(self._on_camera_selection_changed)
        self.second_camera_combo.currentIndexChanged.connect(self._on_second_camera_selection_changed)
        self.youtube_url_edit.textChanged.connect(self._on_youtube_url_changed)

        # Manually trigger the update logic for the current state after all settings are applied
        self._on_input_type_changed(self.input_type_combo.currentIndex())


    def closeEvent(self, event):
        logger.info("InputConfigWidget closeEvent called.")
        self.detener_previsualizacion()
        self.detener_segunda_previsualizacion()
        super().closeEvent(event)