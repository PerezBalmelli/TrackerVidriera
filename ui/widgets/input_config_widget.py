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
    camera_selected = pyqtSignal(int, str) # Para la cámara principal (fija)
    second_camera_selected = pyqtSignal(int, str) # Para la segunda cámara (móvil)
    status_message = pyqtSignal(str, int)
    frame_received = pyqtSignal(object) # Frame de la cámara principal
    second_frame_received = pyqtSignal(object) # Frame de la segunda cámara

    def __init__(self, parent=None):
        super().__init__(parent)
        self.camera_thread = None
        self.second_camera_thread = None # Thread para la segunda cámara
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
        
        # Panel para cámara principal (fija)
        self.camera_panel = QWidget()
        camera_layout = QHBoxLayout(self.camera_panel)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(200)
        self.camera_combo.setToolTip("Seleccione la cámara principal (fija)")
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
        self.form_layout.addRow("Cámara Fija:", self.camera_panel) # Etiqueta cambiada

        # Panel para segunda cámara (móvil)
        self.second_camera_panel = QWidget()
        second_camera_layout = QHBoxLayout(self.second_camera_panel)
        second_camera_layout.setContentsMargins(0, 0, 0, 0)
        self.second_camera_combo = QComboBox()
        self.second_camera_combo.setMinimumWidth(200)
        self.second_camera_combo.setToolTip("Seleccione la segunda cámara (móvil)")
        self.second_camera_combo.addItem("Ninguna", -1) # Opción para no usar segunda cámara
        self.second_camera_combo.currentIndexChanged.connect(self._on_second_camera_selection_changed)
        # No es necesario un botón de refresco aca, usa el mismo de la cámara principal
        self.test_second_camera_button = QPushButton("Info Cámara Móvil")
        self.test_second_camera_button.clicked.connect(self.test_second_camera_info)
        second_camera_layout.addWidget(self.second_camera_combo)
        second_camera_layout.addWidget(self.test_second_camera_button)
        self.form_layout.addRow("Cámara Móvil:", self.second_camera_panel)
        
        # Etiqueta de información
        self.video_info_label = QLabel("No hay entrada seleccionada")
        self.form_layout.addRow("Información:", self.video_info_label)
        
        layout.addWidget(input_group)
        
        # Inicializar visibilidad de paneles según tipo de entrada por defecto (archivo)
        # Por defecto se muestra el panel de archivo y se oculta el de cámara
        self._set_form_row_visible("Archivo:", True)
        
    def _on_input_type_changed(self, index):
        """Maneja el cambio de tipo de entrada (archivo o cámara)."""
        is_file_mode = (index == 0)
        is_camera_mode = (index == 1)

        self._set_form_row_visible("Archivo:", is_file_mode)
        self._set_form_row_visible("Cámara Fija:", is_camera_mode) # Etiqueta cambiada
        self._set_form_row_visible("Cámara Móvil:", is_camera_mode) # Mostrar/ocultar panel de segunda cámara
        
        if is_file_mode:  # Archivo
            self.detener_previsualizacion()
            self.detener_segunda_previsualizacion() # Detener segunda cámara también
            self._update_form_row_label_text(self.video_info_label, "Información:")
            if self.video_path_edit.text():
                self.update_video_info(self.video_path_edit.text())
            else:
                self.video_info_label.setText("No hay video seleccionado")
        else:  # Cámara
            self._update_form_row_label_text(self.video_info_label, "Info Cámara Fija:") # Etiqueta cambiada
            if self.camera_combo.count() == 0:
                self.refresh_cameras() # Esto poblará ambas comboboxes
            elif self.camera_combo.currentIndex() >= 0:
                self._on_camera_selection_changed(self.camera_combo.currentIndex())
            # Manejar la segunda cámara si ya hay algo seleccionado
            if self.second_camera_combo.currentIndex() > 0: # >0 porque "Ninguna" es índice 0
                 self._on_second_camera_selection_changed(self.second_camera_combo.currentIndex())
            elif self.second_camera_combo.count() > 1 and self.second_camera_combo.currentIndex() == 0 : # "Ninguna" seleccionada
                self.detener_segunda_previsualizacion()
                self.second_frame_received.emit(None)


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
            self.detener_segunda_previsualizacion() # Detener segunda cámara
            self.frame_received.emit(None)
            self.second_frame_received.emit(None) # Limpiar frame de segunda cámara
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
                # Asegurarse de no seleccionar la misma cámara que la segunda
                current_second_cam_id = self.second_camera_combo.currentData()
                if current_second_cam_id is not None and current_second_cam_id == camera_id and self.second_camera_combo.currentIndex() > 0:
                    self.status_message.emit("La cámara fija no puede ser la misma que la móvil si ambas están activas.", 3000)
                    # Revertir la selección o manejar de otra forma (ej. deseleccionar la otra)
                    # Por ahora, solo emitimos mensaje y no iniciamos.
                    # Idealmente, se debería deshabilitar la opción en el otro combo.
                    if self.camera_thread and self.camera_thread.isRunning(): # Si ya había una cámara corriendo
                        pass # No hacer nada, dejar la anterior
                    else: # Si no había, limpiar
                        self.detener_previsualizacion()
                        self.video_info_label.setText("Seleccione cámaras diferentes.")
                        self.frame_received.emit(None)
                    return

                self.iniciar_previsualizacion_camara(camera_id, self.camera_combo.itemText(index))
                self.camera_selected.emit(camera_id, self.camera_combo.itemText(index))
        else:
            self.detener_previsualizacion()
            self.video_info_label.setText("Ninguna cámara fija seleccionada.")
            self.frame_received.emit(None)

    def _on_second_camera_selection_changed(self, index):
        """Maneja el cambio de selección de la segunda cámara."""
        if index > 0 and self.second_camera_combo.count() > 0: # index > 0 para saltar "Ninguna"
            camera_id = self.second_camera_combo.itemData(index)
            if camera_id is not None:
                 # Asegurarse de no seleccionar la misma cámara que la principal
                current_main_cam_id = self.camera_combo.currentData()
                if current_main_cam_id is not None and current_main_cam_id == camera_id:
                    self.status_message.emit("La cámara móvil no puede ser la misma que la fija si ambas están activas.", 3000)
                    if self.second_camera_thread and self.second_camera_thread.isRunning():
                        pass
                    else:
                        self.detener_segunda_previsualizacion()
                        # Actualizar una etiqueta de info para la segunda cámara si existiera
                        self.second_frame_received.emit(None)
                    return

                self.iniciar_segunda_previsualizacion_camara(camera_id, self.second_camera_combo.itemText(index))
                self.second_camera_selected.emit(camera_id, self.second_camera_combo.itemText(index))
            else: # "Ninguna" u opción inválida
                self.detener_segunda_previsualizacion()
                self.second_frame_received.emit(None)
        elif index == 0 : # "Ninguna" seleccionada
            self.detener_segunda_previsualizacion()
            self.second_frame_received.emit(None)
            self.second_camera_selected.emit(-1, "Ninguna") # Emitir que no hay cámara
    
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

    def iniciar_segunda_previsualizacion_camara(self, camera_id, camera_description=""):
        """Inicia la previsualización de la segunda cámara."""
        self.detener_segunda_previsualizacion()
        self.second_camera_thread = CameraThread(camera_id) # Usar el nuevo thread
        self.second_camera_thread.frame_received.connect(self._on_second_frame_received) # Nueva señal de frame
        self.second_camera_thread.camera_info_signal.connect(self._update_second_camera_info_from_thread) # Nuevo slot para info
        self.second_camera_thread.camera_error_signal.connect(self._handle_second_camera_error_from_thread) # Nuevo slot para error
        self.second_camera_thread.start()
        # Podríamos tener una segunda etiqueta de información o actualizar la principal de forma combinada
        self.status_message.emit(f"Iniciando previsualización de segunda cámara: {camera_description}", 2000)
    
    def _on_frame_received(self, frame):
        """Recibe frames de la cámara."""
        self.frame_received.emit(frame)

    def _on_second_frame_received(self, frame):
        """Recibe frames de la segunda cámara."""
        self.second_frame_received.emit(frame)
    
    def _update_camera_info_from_thread(self, info_text):
        """Actualiza la etiqueta de información con datos de la cámara."""
        # Podríamos querer diferenciar la info si ambas cámaras están activas
        current_text = self.video_info_label.text()
        if "Móvil" in current_text and "Fija" not in info_text: # Si ya hay info de la móvil, no sobreescribir con la fija
             self.video_info_label.setText(f"Fija: {info_text} | {current_text.split('|')[-1].strip()}")
        else:
            self.video_info_label.setText(f"Fija: {info_text}")
    
    def _update_second_camera_info_from_thread(self, info_text):
        """Actualiza la etiqueta de información con datos de la segunda cámara."""
        current_text = self.video_info_label.text()
        if "Fija" in current_text and "Móvil" not in info_text: # Si ya hay info de la fija
            self.video_info_label.setText(f"{current_text.split('|')[0].strip()} | Móvil: {info_text}")
        else:
            self.video_info_label.setText(f"Móvil: {info_text}")

    def _handle_camera_error_from_thread(self, error_text):
        """Maneja errores de la cámara."""
        self.video_info_label.setText(f"Error Cámara Fija: {error_text}")
        self.status_message.emit(f"Error Cámara Fija: {error_text}", 5000)
        self.frame_received.emit(None)

    def _handle_second_camera_error_from_thread(self, error_text):
        """Maneja errores de la segunda cámara."""
        # Actualizar una etiqueta de info específica o la general
        self.status_message.emit(f"Error Cámara Móvil: {error_text}", 5000)
        self.second_frame_received.emit(None)
        # Podríamos querer mostrar este error en video_info_label también
        current_text = self.video_info_label.text()
        if "Fija" in current_text:
            self.video_info_label.setText(f"{current_text.split('|')[0].strip()} | Error Móvil: {error_text}")
        else:
            self.video_info_label.setText(f"Error Móvil: {error_text}")
    
    def detener_previsualizacion(self):
        """Detiene la previsualización de la cámara."""
        if self.camera_thread:
            self.camera_thread.stop()
            # Desconectar señales para evitar errores si el objeto se destruye parcialmente
            try:
                self.camera_thread.frame_received.disconnect(self._on_frame_received)
                self.camera_thread.camera_info_signal.disconnect(self._update_camera_info_from_thread)
                self.camera_thread.camera_error_signal.disconnect(self._handle_camera_error_from_thread)
            except TypeError: # En caso de que ya estén desconectadas
                pass
            self.camera_thread = None

    def detener_segunda_previsualizacion(self):
        """Detiene la previsualización de la segunda cámara."""
        if self.second_camera_thread:
            self.second_camera_thread.stop()
            try:
                self.second_camera_thread.frame_received.disconnect(self._on_second_frame_received)
                self.second_camera_thread.camera_info_signal.disconnect(self._update_second_camera_info_from_thread)
                self.second_camera_thread.camera_error_signal.disconnect(self._handle_second_camera_error_from_thread)
            except TypeError:
                pass
            self.second_camera_thread = None
    
    def detect_available_cameras(self, max_cameras=5):
        """Detecta cámaras disponibles intentando abrirlas por índice."""
        available_cameras = []
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # Intenta obtener alguna información básica para confirmar que es una cámara válida
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                cap.release()
                if width > 0 and height > 0:
                    available_cameras.append((i, f"Cámara {i}"))
            else:
                cap.release() # Asegurarse de liberar aunque no se haya abierto correctamente
        return available_cameras

    def refresh_cameras(self):
        """Actualiza la lista de cámaras disponibles."""
        self.status_message.emit("Buscando cámaras...", 0)
        QApplication.processEvents()
        self.camera_combo.clear()
        self.second_camera_combo.clear() # Limpiar también el combo de la segunda cámara
        self.second_camera_combo.addItem("Ninguna", -1) # Añadir opción "Ninguna" primero

        self.available_cameras = self.detect_available_cameras(max_cameras=5)
        
        # Si no se detectaron cámaras o solo la predeterminada
        if not self.available_cameras:
            self.camera_combo.addItem("Cámara 0 (predeterminada)", 0)
            # No añadir a la segunda cámara si solo hay una opción, o manejarlo según preferencia
            self.status_message.emit("No se detectaron cámaras. Usando ID 0 para cámara fija.", 3000)
        else:
            for cam_id, desc in self.available_cameras:
                self.camera_combo.addItem(desc, cam_id)
                self.second_camera_combo.addItem(desc, cam_id) # Poblar también el segundo combo
            self.status_message.emit(f"Se encontraron {len(self.available_cameras)} cámaras.", 3000)
            
        # Si estamos en modo cámara, iniciar previsualización de la primera cámara fija
        if self.input_type_combo.currentIndex() == 1 and self.camera_combo.count() > 0:
            self._on_camera_selection_changed(0) 
            # Para la segunda cámara, podríamos dejar "Ninguna" por defecto o seleccionar la segunda si hay más de una
            if self.second_camera_combo.count() > 1: # Si hay al menos una cámara además de "Ninguna"
                # Si hay dos cámaras o más, y la primera seleccionada es diferente de la segunda potencial
                if len(self.available_cameras) > 1 and self.camera_combo.itemData(0) != self.second_camera_combo.itemData(1):
                     # self.second_camera_combo.setCurrentIndex(1) # Seleccionar la primera cámara real (índice 1 después de "Ninguna")
                     # self._on_second_camera_selection_changed(1)
                     pass # Mejor dejar que el usuario la seleccione explícitamente
                elif len(self.available_cameras) == 1 : # Solo una cámara detectada
                    self.second_camera_combo.setCurrentIndex(0) # Dejar en "Ninguna"
                    self.detener_segunda_previsualizacion()
                    self.second_frame_received.emit(None)


    def test_camera_info(self):
        """Obtiene información de la cámara seleccionada."""
        if self.input_type_combo.currentIndex() != 1:
            self.status_message.emit("Cambie a 'Cámara en vivo' para obtener info de la cámara fija.", 3000)
            return

        if self.camera_combo.count() == 0:
            self.refresh_cameras()
            if self.camera_combo.count() == 0:
                self.video_info_label.setText("No hay cámaras fijas disponibles para probar.")
                self.status_message.emit("No hay cámaras fijas disponibles.", 3000)
                return

        camera_id = self.camera_combo.currentData()
        camera_desc = self.camera_combo.currentText()

        if camera_id is None:
            self.video_info_label.setText("Ninguna cámara fija seleccionada para probar.")
            return

        self.status_message.emit(f"Obteniendo info de {camera_desc} (fija)...", 0)
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            info_text = f"Error: No se pudo abrir {camera_desc} (fija)"
            self.video_info_label.setText(info_text)
            self.status_message.emit(info_text, 3000)
            return

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        info_text = f"Fija: {camera_desc}: {width}x{height} @ {fps:.2f} FPS"
        self._update_camera_info_from_thread(f"{camera_desc}: {width}x{height} @ {fps:.2f} FPS")
        self.status_message.emit(f"Info de {camera_desc} (fija) obtenida.", 3000)
        
        # Iniciar previsualización si no está activa
        if not (self.camera_thread and self.camera_thread.isRunning() and \
                self.camera_thread.camera_id == camera_id):
            self.iniciar_previsualizacion_camara(camera_id, camera_desc)

    def test_second_camera_info(self):
        """Obtiene información de la segunda cámara seleccionada."""
        if self.input_type_combo.currentIndex() != 1:
            self.status_message.emit("Cambie a 'Cámara en vivo' para obtener info de la cámara móvil.", 3000)
            return

        if self.second_camera_combo.count() <= 1: # Solo "Ninguna" o ninguna cámara
            self.refresh_cameras() # Intenta refrescar por si acaso
            if self.second_camera_combo.count() <= 1:
                self.status_message.emit("No hay cámaras móviles disponibles para probar.", 3000)
                return
        
        current_idx = self.second_camera_combo.currentIndex()
        if current_idx == 0: # "Ninguna" seleccionada
            self.status_message.emit("Seleccione una cámara móvil para obtener información.", 3000)
            return

        camera_id = self.second_camera_combo.currentData()
        camera_desc = self.second_camera_combo.currentText()

        if camera_id is None or camera_id == -1: # Doble chequeo por si acaso
            self.status_message.emit("Ninguna cámara móvil seleccionada para probar.", 3000)
            return

        self.status_message.emit(f"Obteniendo info de {camera_desc} (móvil)...", 0)
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            error_msg = f"Error: No se pudo abrir {camera_desc} (móvil)"
            self._update_second_camera_info_from_thread(error_msg) # Actualiza la parte móvil del label
            self.status_message.emit(error_msg, 3000)
            return

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        
        info_text = f"{camera_desc}: {width}x{height} @ {fps:.2f} FPS"
        self._update_second_camera_info_from_thread(info_text)
        self.status_message.emit(f"Info de {camera_desc} (móvil) obtenida.", 3000)
        
        if not (self.second_camera_thread and self.second_camera_thread.isRunning() and \
                self.second_camera_thread.camera_id == camera_id):
            self.iniciar_segunda_previsualizacion_camara(camera_id, camera_desc)

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
        """Obtiene el ID de la cámara fija seleccionada."""
        if self.input_type_combo.currentIndex() == 1 and self.camera_combo.count() > 0:
            return self.camera_combo.currentData()
        return None

    def get_selected_second_camera_id(self):
        """Obtiene el ID de la segunda cámara (móvil) seleccionada."""
        if self.input_type_combo.currentIndex() == 1 and self.second_camera_combo.count() > 0:
            cam_id = self.second_camera_combo.currentData()
            return cam_id if cam_id != -1 else None # Retorna None si es "Ninguna"
        return None

    def get_selected_camera_description(self):
        """Obtiene la descripción de la cámara fija seleccionada."""
        if self.input_type_combo.currentIndex() == 1 and self.camera_combo.count() > 0:
            return self.camera_combo.currentText()
        return "N/A"

    def get_selected_second_camera_description(self):
        """Obtiene la descripción de la segunda cámara (móvil) seleccionada."""
        if self.input_type_combo.currentIndex() == 1 and self.second_camera_combo.count() > 0:
            if self.second_camera_combo.currentData() != -1:
                return self.second_camera_combo.currentText()
        return "Ninguna"

    def _find_form_row_by_label_text(self, label_text):
        """Encuentra el índice de una fila en el QFormLayout por el texto de su etiqueta."""
        for i in range(self.form_layout.rowCount()):
            label_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            if label_item and label_item.widget() and label_item.widget().text() == label_text:
                return i
        return -1 # Retorna -1 si no se encuentra

    def _set_form_row_visible(self, label_text, visible):
        """Muestra u oculta una fila completa en el QFormLayout (etiqueta y campo)."""
        row_index = self._find_form_row_by_label_text(label_text)
        if row_index != -1:
            label_widget = self.form_layout.itemAt(row_index, QFormLayout.ItemRole.LabelRole).widget()
            field_widget = self.form_layout.itemAt(row_index, QFormLayout.ItemRole.FieldRole).widget()
            if label_widget:
                label_widget.setVisible(visible)
            if field_widget:
                field_widget.setVisible(visible)
    
    def _update_form_row_label_text(self, widget, new_label_text):
        """Actualiza el texto de la etiqueta de una fila en el QFormLayout."""
        for i in range(self.form_layout.rowCount()):
            label_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            field_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if field_item and field_item.widget() == widget:
                if label_item and label_item.widget():
                    label_item.widget().setText(new_label_text)
                break
    
    def closeEvent(self, event):
        self.detener_previsualizacion()
        self.detener_segunda_previsualizacion()
        super().closeEvent(event)

    # Funciones para ser llamadas desde MainWindow si es necesario
    def get_all_settings(self):
        settings = {
            "input_type": self.input_type_combo.currentIndex(),
            "video_path": self.video_path_edit.text() if self.input_type_combo.currentIndex() == 0 else None,
            "camera_id": self.get_selected_camera_id() if self.input_type_combo.currentIndex() == 1 else None,
            "second_camera_id": self.get_selected_second_camera_id() if self.input_type_combo.currentIndex() == 1 else None,
        }
        return settings

    def set_all_settings(self, settings):
        input_type = settings.get("input_type", 0)
        self.input_type_combo.setCurrentIndex(input_type)
        self._on_input_type_changed(input_type) # Asegura que la UI se actualice

        if input_type == 0: # Archivo
            video_path = settings.get("video_path")
            if video_path:
                self.video_path_edit.setText(video_path)
                self.update_video_info(video_path)
        else: # Cámara
            cam_id = settings.get("camera_id")
            if cam_id is not None:
                for i in range(self.camera_combo.count()):
                    if self.camera_combo.itemData(i) == cam_id:
                        self.camera_combo.setCurrentIndex(i)
                        # self._on_camera_selection_changed(i) # Ya se llama desde _on_input_type_changed
                        break
            
            second_cam_id = settings.get("second_camera_id")
            if second_cam_id is not None and second_cam_id != -1:
                 for i in range(self.second_camera_combo.count()):
                    if self.second_camera_combo.itemData(i) == second_cam_id:
                        self.second_camera_combo.setCurrentIndex(i)
                        # self._on_second_camera_selection_changed(i) # Ya se llama desde _on_input_type_changed
                        break
            elif second_cam_id == -1 : # "Ninguna"
                self.second_camera_combo.setCurrentIndex(0)
