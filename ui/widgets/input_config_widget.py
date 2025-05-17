"""
Widget para la configuración de entrada de video en la aplicación TrackerVidriera.
"""
import os
import time
import sys
import cv2
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QLineEdit,
    QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread

class CameraThread(QThread):
    """Thread para capturar frames de una cámara en segundo plano."""
    frame_received = pyqtSignal(object)
    camera_info_signal = pyqtSignal(str)
    camera_error_signal = pyqtSignal(str)

    def __init__(self, camera_id=0, parent=None):
        super().__init__(parent)
        self.camera_id = camera_id
        self.running = False
        self.cap = None

    def run(self):
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            if not self.cap.isOpened():
                self.camera_error_signal.emit(f"Error: No se pudo abrir la cámara ID {self.camera_id}")
                return

            # Get camera info
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0: fps = 30.0
            info_text = f"Cámara ID {self.camera_id}: {width}x{height} @ {fps:.2f} FPS"
            self.camera_info_signal.emit(info_text)

            self.running = True
            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    self.frame_received.emit(frame)
                else:
                    self.msleep(100)
                self.msleep(int(1000/fps))

        except Exception as e:
            self.camera_error_signal.emit(f"Error en CameraThread: {str(e)}")
        finally:
            if self.cap:
                self.cap.release()

    def stop(self):
        self.running = False
        self.wait(1000)
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.cap = None


class InputConfigWidget(QWidget):
    """Widget para la configuración de entrada de video (archivo o cámara)."""
    
    # Señales para comunicar cambios a la ventana principal
    input_type_changed = pyqtSignal(int)
    video_file_selected = pyqtSignal(str)
    camera_selected = pyqtSignal(int, str)
    status_message = pyqtSignal(str, int)
    frame_received = pyqtSignal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.camera_thread = None
        self.available_cameras = []
        self._init_ui()
        
        # Asegurarse de que al iniciar, se aplique correctamente el tipo de entrada inicial
        # Esto simula un cambio del combo box para que se ejecuten todas las acciones necesarias
        self._on_input_type_changed(self.input_type_combo.currentIndex())
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Grupo de configuración
        input_group = QGroupBox("Configuración de entrada")
        self.form_layout = QFormLayout(input_group)
        
        # Selector de tipo de entrada
        self.input_type_combo = QComboBox()
        self.input_type_combo.addItems(["Archivo de video", "Cámara en vivo"])
        self.input_type_combo.currentIndexChanged.connect(self._on_input_type_changed)
        self.form_layout.addRow("Tipo de entrada:", self.input_type_combo)
        
        # Panel para archivo de video
        self.file_panel = QWidget()
        file_layout = QHBoxLayout(self.file_panel)
        file_layout.setContentsMargins(0, 0, 0, 0)
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setReadOnly(True)
        browse_button = QPushButton("Explorar...")
        browse_button.clicked.connect(self._browse_video_file)
        file_layout.addWidget(self.video_path_edit)
        file_layout.addWidget(browse_button)
        self.form_layout.addRow("Archivo:", self.file_panel)
        
        # Panel para cámara
        self.camera_panel = QWidget()
        camera_layout = QHBoxLayout(self.camera_panel)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(200)
        self.camera_combo.setToolTip("Seleccione la cámara a utilizar")
        self.camera_combo.currentIndexChanged.connect(self._on_camera_selection_changed)
        refresh_cameras_button = QPushButton("🔄")
        refresh_cameras_button.setToolTip("Actualizar lista de cámaras")
        refresh_cameras_button.setFixedWidth(30)
        refresh_cameras_button.clicked.connect(self.refresh_cameras)
        self.test_camera_button = QPushButton("Info Cámara")
        self.test_camera_button.clicked.connect(self.test_camera_info)
        camera_layout.addWidget(self.camera_combo)
        camera_layout.addWidget(refresh_cameras_button)
        camera_layout.addWidget(self.test_camera_button)
        self.form_layout.addRow("Cámara:", self.camera_panel)
        
        # Etiqueta de información
        self.video_info_label = QLabel("No hay entrada seleccionada")
        self.form_layout.addRow("Información:", self.video_info_label)
        
        layout.addWidget(input_group)
        
        # Inicializar visibilidad de paneles según tipo de entrada por defecto (archivo)
        # Por defecto se muestra el panel de archivo y se oculta el de cámara
        self._set_form_row_visible("Archivo:", True)
        
    def _on_input_type_changed(self, index):
        self._set_form_row_visible("Cámara:", False)
        
    def _on_input_type_changed(self, index):
        """Maneja el cambio de tipo de entrada (archivo o cámara)."""
        self._set_form_row_visible("Archivo:", index == 0)
        self._set_form_row_visible("Cámara:", index == 1)
        
        if index == 0:  # Archivo
            self.detener_previsualizacion()
            self._update_form_row_label_text(self.video_info_label, "Información:")
            if self.video_path_edit.text():
                self.update_video_info(self.video_path_edit.text())
            else:
                self.video_info_label.setText("No hay video seleccionado")
        else:  # Cámara
            self._update_form_row_label_text(self.video_info_label, "Info Cámara:")
            if self.camera_combo.count() == 0:
                self.refresh_cameras()
            elif self.camera_combo.currentIndex() >= 0:
                self._on_camera_selection_changed(self.camera_combo.currentIndex())
        
        self.input_type_changed.emit(index)
    
    def _browse_video_file(self):
        """Abre un diálogo para seleccionar un archivo de video."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar video", "",
            "Archivos de video (*.mp4 *.avi *.mov *.mkv);;Todos los archivos (*)"
        )
        if file_path:
            self.video_path_edit.setText(file_path)
            self.update_video_info(file_path)
            self.detener_previsualizacion()
            self.frame_received.emit(None)
            self.video_file_selected.emit(file_path)
    
    def update_video_info(self, video_path):
        """Actualiza la información del video seleccionado."""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.video_info_label.setText("Error al abrir el video")
                return
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            info_text = f"Resolución: {width}x{height}, FPS: {fps:.2f}, Duración: {duration:.2f}s"
            self.video_info_label.setText(info_text)
            cap.release()
        except Exception as e:
            self.video_info_label.setText(f"Error al leer info: {str(e)}")
    
    def _on_camera_selection_changed(self, index):
        """Maneja el cambio de selección de cámara."""
        if index >= 0 and self.camera_combo.count() > 0:
            camera_id = self.camera_combo.itemData(index)
            if camera_id is not None:
                self.iniciar_previsualizacion_camara(camera_id, self.camera_combo.itemText(index))
                self.camera_selected.emit(camera_id, self.camera_combo.itemText(index))
        else:
            self.detener_previsualizacion()
            self.video_info_label.setText("Ninguna cámara seleccionada.")
            self.frame_received.emit(None)
    
    def iniciar_previsualizacion_camara(self, camera_id, camera_description=""):
        """Inicia la previsualización de la cámara."""
        self.detener_previsualizacion()
        self.camera_thread = CameraThread(camera_id)
        self.camera_thread.frame_received.connect(self._on_frame_received)
        self.camera_thread.camera_info_signal.connect(self._update_camera_info_from_thread)
        self.camera_thread.camera_error_signal.connect(self._handle_camera_error_from_thread)
        self.camera_thread.start()
        self.video_info_label.setText(f"Iniciando {camera_description}...")
        self.status_message.emit(f"Iniciando previsualización de {camera_description}", 2000)
    
    def _on_frame_received(self, frame):
        """Recibe frames de la cámara."""
        self.frame_received.emit(frame)
    
    def _update_camera_info_from_thread(self, info_text):
        """Actualiza la etiqueta de información con datos de la cámara."""
        self.video_info_label.setText(info_text)
    
    def _handle_camera_error_from_thread(self, error_text):
        """Maneja errores de la cámara."""
        self.video_info_label.setText(error_text)
        self.status_message.emit(error_text, 5000)
        self.frame_received.emit(None)
    
    def detener_previsualizacion(self):
        """Detiene la previsualización de la cámara."""
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread.frame_received.disconnect(self._on_frame_received)
            self.camera_thread.camera_info_signal.disconnect(self._update_camera_info_from_thread)
            self.camera_thread.camera_error_signal.disconnect(self._handle_camera_error_from_thread)
            self.camera_thread = None
    
    def refresh_cameras(self):
        """Actualiza la lista de cámaras disponibles."""
        self.status_message.emit("Buscando cámaras...", 0)
        QApplication.processEvents()
        self.camera_combo.clear()
        self.available_cameras = self.detect_available_cameras(max_cameras=5)
        
        # Si no se detectaron cámaras o solo la predeterminada
        if not self.available_cameras:
            self.camera_combo.addItem("Cámara 0 (predeterminada)", 0)
            self.status_message.emit("No se detectaron cámaras. Usando ID 0.", 3000)
        else:
            for cam_id, desc in self.available_cameras:
                self.camera_combo.addItem(desc, cam_id)
            self.status_message.emit(f"Se encontraron {len(self.available_cameras)} cámaras.", 3000)
            
        # Si estamos en modo cámara, iniciar previsualización de la primera
        if self.input_type_combo.currentIndex() == 1 and self.camera_combo.count() > 0:
            self._on_camera_selection_changed(0)
    
    def test_camera_info(self):
        """Obtiene información de la cámara seleccionada."""
        if self.input_type_combo.currentIndex() != 1:
            self.status_message.emit("Cambie a 'Cámara en vivo' para obtener info.", 3000)
            return

        if self.camera_combo.count() == 0:
            self.refresh_cameras()
            if self.camera_combo.count() == 0:
                self.video_info_label.setText("No hay cámaras disponibles para probar.")
                self.status_message.emit("No hay cámaras disponibles.", 3000)
                return

        camera_id = self.camera_combo.currentData()
        camera_desc = self.camera_combo.currentText()
        if camera_id is None:
            self.video_info_label.setText("Ninguna cámara seleccionada para probar.")
            return

        self.status_message.emit(f"Obteniendo info de {camera_desc}...", 0)
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            info_text = f"Error: No se pudo abrir {camera_desc}"
            self.video_info_label.setText(info_text)
            self.status_message.emit(info_text, 3000)
            return

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        info_text = f"{camera_desc}: {width}x{height} @ {fps:.2f} FPS"
        self.video_info_label.setText(info_text)
        self.status_message.emit(f"Info de {camera_desc} obtenida.", 3000)
        
        # Iniciar previsualización si no está activa
        if not (self.camera_thread and self.camera_thread.isRunning() and 
                self.camera_thread.camera_id == camera_id):
            self.iniciar_previsualizacion_camara(camera_id, camera_desc)
    
    def detect_available_cameras(self, max_cameras=10):
        """Detecta las cámaras disponibles en el sistema."""
        detected_cameras = []
        
        
        prev_log_level = None
        try:
            if hasattr(cv2, 'setLogLevel') and hasattr(cv2, 'LOG_LEVEL_SILENT'):
                prev_log_level = cv2.getLogLevel()
                cv2.setLogLevel(cv2.LOG_LEVEL_SILENT)
        except Exception:
            pass

        for i in range(max_cameras):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if sys.platform == "win32" else None)
                time.sleep(0.1)  # Allow time for camera to initialize
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        description = f"Cámara {i}: {width}x{height}"
                        detected_cameras.append((i, description))
                    cap.release()
                    time.sleep(0.1)
            except Exception:
                if 'cap' in locals() and cap:
                    cap.release()
                continue

        
        try:
            if prev_log_level is not None and hasattr(cv2, 'setLogLevel'):
                cv2.setLogLevel(prev_log_level)
        except Exception:
            pass

        return detected_cameras
    
    # Métodos auxiliares para manejar formularios
    def _find_form_row_by_label_text(self, label_text):
        """Encuentra un índice de fila en form_layout por el texto de la etiqueta."""
        for i in range(self.form_layout.rowCount()):
            label_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            if label_item and label_item.widget() and isinstance(label_item.widget(), QLabel):
                if label_item.widget().text() == label_text:
                    return i
        return -1

    def _set_form_row_visible(self, label_text, visible):
        """Establece la visibilidad de una fila del formulario."""
        row_index = self._find_form_row_by_label_text(label_text)
        if row_index < 0:
            return
            
        label_item = self.form_layout.itemAt(row_index, QFormLayout.ItemRole.LabelRole)
        if label_item and label_item.widget():
            label_item.widget().setVisible(visible)
            
        field_item = self.form_layout.itemAt(row_index, QFormLayout.ItemRole.FieldRole)
        if field_item and field_item.widget():
            field_item.widget().setVisible(visible)

    def _update_form_row_label_text(self, target_field_widget, new_label_text):
        """Actualiza el texto de la etiqueta para una fila que contiene target_field_widget."""
        for i in range(self.form_layout.rowCount()):
            field_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if field_item and field_item.widget() == target_field_widget:
                label_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
                if label_item and label_item.widget() and isinstance(label_item.widget(), QLabel):
                    label_item.widget().setText(new_label_text)
                    return
    
    # Métodos públicos para acceder desde la ventana principal
    def get_input_type(self):
        """Retorna el tipo de entrada seleccionado (0: archivo, 1: cámara)."""
        return self.input_type_combo.currentIndex()
    
    def get_video_path(self):
        """Retorna la ruta del archivo de video seleccionado."""
        return self.video_path_edit.text()
    
    def set_video_path(self, path):
        """Establece la ruta del archivo de video."""
        if path:
            self.video_path_edit.setText(path)
            self.update_video_info(path)
    
    def get_selected_camera_id(self):
        """Retorna el ID de la cámara seleccionada."""
        return self.camera_combo.currentData()
    
    def get_selected_camera_description(self):
        """Retorna la descripción de la cámara seleccionada."""
        return self.camera_combo.currentText()
