"""
Módulo principal para la interfaz de usuario de TrackerVidriera.
Implementa la ventana principal y todos los controles de la aplicación.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QComboBox,
    QDoubleSpinBox, QSpinBox, QGroupBox, QFormLayout,
    QLineEdit, QApplication, QSlider, QStatusBar,
    QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QImage
from core.serial_manager import serial_manager

import sys
import os
from pathlib import Path
import glob
import cv2 # Make sure cv2 is imported at the top if used globally
import time # For detect_available_cameras

# Importamos módulos del proyecto (Ensure these paths are correct for your project structure)
# Assuming settings and VideoOutputManager are in a directory structure like:
# project_root/
# |-- main_window.py
# |-- config/
# |   |-- settings.py
# |-- core/
# |   |-- video_output.py
# |-- rastreo.py
# |-- models/
try:
    from config.settings import settings
    from core.video_output import VideoOutputManager
except ImportError:
    print("Warning: Could not import 'settings' or 'VideoOutputManager'. Ensure they are in the correct path.")
    # Provide dummy implementations if needed for the script to run without them for testing UI
    class DummySettings:
        def __init__(self):
            self.model_path = "yolov8n.pt"
            self.confidence_threshold = 0.6
            self.frames_espera = 10
            self.output_path = "salida.avi"
            self.output_format = "XVID"
        def save_settings(self): return True
        def load_settings(self): pass
    settings = DummySettings()

    class DummyVideoOutputManager:
        pass
    VideoOutputManager = DummyVideoOutputManager


class CameraThread(QThread):
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
            if fps <= 0: fps = 30.0 # Default FPS if camera doesn't report
            info_text = f"Cámara ID {self.camera_id}: {width}x{height} @ {fps:.2f} FPS"
            self.camera_info_signal.emit(info_text)

            self.running = True
            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    self.frame_received.emit(frame)
                else:
                    # Could indicate camera disconnected or end of a video file if misconfigured
                    self.msleep(100) # Wait a bit before retrying or breaking
                    # self.running = False # Optionally stop if read fails consistently
                self.msleep(int(1000/fps)) # Adjust delay based on actual FPS

        except Exception as e:
            self.camera_error_signal.emit(f"Error en CameraThread: {str(e)}")
        finally:
            if self.cap:
                self.cap.release()

    def stop(self):
        self.running = False
        self.wait(1000) # Wait for thread to finish
        if self.cap and self.cap.isOpened():
             self.cap.release()
        self.cap = None


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación TrackerVidriera."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("TrackerVidriera")
        self.setMinimumSize(800, 600) # Adjusted minimum size for preview

        self.video_output = VideoOutputManager()
        self.codec_extension_map = {
            "XVID": ".avi", "MP4V": ".mp4", "MJPG": ".avi",
            "H264": ".mp4", "AVC1": ".mp4"
        }
        self.available_cameras = []
        self.camera_thread = None
        self.procesando = False

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo")

        self.init_ui()
        self.load_settings_to_ui()
        self.toggle_input_type(self.input_type_combo.currentIndex()) # Initialize UI state


    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        header_layout = QHBoxLayout()
        title_label = QLabel("TrackerVidriera")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        content_layout = QHBoxLayout()
        config_panel = QWidget()
        config_layout = QVBoxLayout(config_panel)
        config_layout.setSpacing(10)

        self.create_input_config_group(config_layout)
        self.create_model_config_group(config_layout)
        self.create_output_config_group(config_layout)
        
        # Grupo de configuración de comunicación serial
        self.create_serial_config_group(config_layout)
        
        # Botones de acción
        self.create_action_buttons(config_layout)
        config_layout.addStretch()

        content_layout.addWidget(config_panel, 1)

        # Panel derecho - Visualización de video
        self.video_display_label = QLabel("Vista previa no disponible") # Placeholder text
        self.video_display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_display_label.setMinimumSize(480, 360) # Minimum size for video preview
        self.video_display_label.setStyleSheet("background-color: black; color: white;")
        content_layout.addWidget(self.video_display_label, 2) # Give more space to video

        main_layout.addLayout(content_layout)
        self.setCentralWidget(central_widget)

    def create_input_config_group(self, parent_layout):
        input_group = QGroupBox("Configuración de entrada")
        self.input_form_layout = QFormLayout() # Store for easy access by helpers

        self.input_type_combo = QComboBox()
        self.input_type_combo.addItems(["Archivo de video", "Cámara en vivo"])
        self.input_type_combo.currentIndexChanged.connect(self.toggle_input_type)
        self.input_form_layout.addRow("Tipo de entrada:", self.input_type_combo)

        # Panel para archivo de video
        self.file_panel = QWidget()
        file_layout = QHBoxLayout(self.file_panel)
        file_layout.setContentsMargins(0, 0, 0, 0)
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setReadOnly(True)
        browse_button = QPushButton("Explorar...")
        browse_button.clicked.connect(self.browse_video_file)
        file_layout.addWidget(self.video_path_edit)
        file_layout.addWidget(browse_button)
        self.input_form_layout.addRow("Archivo:", self.file_panel)

        # Panel para cámara
        self.camera_panel = QWidget()
        camera_layout = QHBoxLayout(self.camera_panel)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(200) # Adjusted width
        self.camera_combo.setToolTip("Seleccione la cámara a utilizar")
        self.camera_combo.currentIndexChanged.connect(self.on_camera_selection_changed)
        refresh_cameras_button = QPushButton("🔄")
        refresh_cameras_button.setToolTip("Actualizar lista de cámaras")
        refresh_cameras_button.setFixedWidth(30)
        refresh_cameras_button.clicked.connect(self.refresh_cameras)
        self.test_camera_button = QPushButton("Info Cámara") # Changed label
        self.test_camera_button.clicked.connect(self.test_camera_info) # Renamed method
        camera_layout.addWidget(self.camera_combo)
        camera_layout.addWidget(refresh_cameras_button)
        camera_layout.addWidget(self.test_camera_button)
        self.input_form_layout.addRow("Cámara:", self.camera_panel)

        self.video_info_label = QLabel("No hay entrada seleccionada")
        self.input_form_layout.addRow("Información:", self.video_info_label)

        input_group.setLayout(self.input_form_layout)
        parent_layout.addWidget(input_group)

    def create_model_config_group(self, parent_layout):
        model_group = QGroupBox("Configuración del modelo")
        model_layout = QFormLayout()
        self.model_path_combo = QComboBox()
        self.populate_model_combo()
        model_layout.addRow("Modelo:", self.model_path_combo)
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.1, 1.0); self.confidence_spin.setSingleStep(0.05); self.confidence_spin.setValue(0.6)
        model_layout.addRow("Umbral de confianza:", self.confidence_spin)
        self.frames_wait_spin = QSpinBox()
        self.frames_wait_spin.setRange(1, 30); self.frames_wait_spin.setValue(10)
        model_layout.addRow("Frames de espera:", self.frames_wait_spin)
        model_group.setLayout(model_layout)
        parent_layout.addWidget(model_group)

    def create_output_config_group(self, parent_layout):
        output_group = QGroupBox("Configuración de salida")
        output_layout = QFormLayout()
        self.output_path_edit = QLineEdit("salida.avi")
        output_save_button = QPushButton("Guardar como...")
        output_save_button.clicked.connect(self.set_output_file)
        output_path_layout = QHBoxLayout()
        output_path_layout.addWidget(self.output_path_edit); output_path_layout.addWidget(output_save_button)
        output_layout.addRow("Archivo de salida:", output_path_layout)
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["XVID", "MP4V", "MJPG", "H264", "AVC1"])
        output_layout.addRow("Formato:", self.codec_combo)
        output_group.setLayout(output_layout)
        parent_layout.addWidget(output_group)
    
    def create_serial_config_group(self, parent_layout):
        """Crea el grupo de configuración de comunicación serial para ESP32."""
        serial_group = QGroupBox("Comunicación Serial ESP32")
        serial_layout = QFormLayout()
        
        # Panel para selección de puerto COM
        port_panel = QWidget()
        port_layout = QHBoxLayout(port_panel)
        port_layout.setContentsMargins(0, 0, 0, 0)
        
        # Combo para selección de puertos
        self.serial_port_combo = QComboBox()
        self.serial_port_combo.setMinimumWidth(200)
        self.serial_port_combo.setToolTip("Seleccione el puerto COM del ESP32")
        
        # Botón para refrescar lista de puertos
        refresh_ports_button = QPushButton("🔄")
        refresh_ports_button.setToolTip("Actualizar lista de puertos COM")
        refresh_ports_button.setFixedWidth(30)
        refresh_ports_button.clicked.connect(self.refresh_serial_ports)
        
        # Botón para probar la conexión serial
        self.test_serial_button = QPushButton("Probar Conexión")
        self.test_serial_button.clicked.connect(self.test_serial_connection)
        
        port_layout.addWidget(self.serial_port_combo)
        port_layout.addWidget(refresh_ports_button)
        port_layout.addWidget(self.test_serial_button)
        
        # Velocidad de comunicación
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        # Seleccionar 115200 por defecto
        index = self.baudrate_combo.findText("115200")
        if index >= 0:
            self.baudrate_combo.setCurrentIndex(index)
        
        # CheckBox para habilitar/deshabilitar comunicación serial
        self.serial_enabled_check = QCheckBox("Activo")
        self.serial_enabled_check.setChecked(True)
        
        # Layout para baudrate y checkbox
        baudrate_panel = QWidget()
        baudrate_layout = QHBoxLayout(baudrate_panel)
        baudrate_layout.setContentsMargins(0, 0, 0, 0)
        baudrate_layout.addWidget(self.baudrate_combo)
        baudrate_layout.addWidget(self.serial_enabled_check)
        
        # Añadir al layout principal
        serial_layout.addRow("Puerto COM:", port_panel)
        serial_layout.addRow("Velocidad:", baudrate_panel)
        
        # Estado de la conexión
        self.serial_status_label = QLabel("Sin conectar")
        serial_layout.addRow("Estado:", self.serial_status_label)
        
        serial_group.setLayout(serial_layout)
        parent_layout.addWidget(serial_group)
        
        # Cargar puertos disponibles
        self.refresh_serial_ports()
    
    def refresh_serial_ports(self):
        """Detecta y actualiza la lista de puertos seriales disponibles."""
        self.status_bar.showMessage("Buscando puertos ESP32 disponibles...", 2000)
        self.serial_port_combo.clear()
        
        # Obtener descripciones de puertos ESP32 desde el gestor serial
        # Asumiendo que serial_manager está disponible como self.serial_manager o global
        port_descriptions = serial_manager.get_port_descriptions() 
        
        if not port_descriptions:
            self.serial_port_combo.addItem("COM3 (predeterminado)", "COM3") # Añadir dato de usuario 'COM3'
            self.status_bar.showMessage("No se detectaron dispositivos ESP32. Usando COM3 por defecto.", 3000)
            self.serial_status_label.setText("Sin conectar")
        else:
            # Añadir los puertos detectados al combo
            for port, description in port_descriptions:
                self.serial_port_combo.addItem(description, port) # Guardar el nombre del puerto como dato
            self.status_bar.showMessage(f"Se encontraron {len(port_descriptions)} puertos ESP32", 3000)
            # Intentar seleccionar el puerto guardado en la configuración si existe
            saved_port = settings.serial_port
            if saved_port:
                index = self.serial_port_combo.findData(saved_port)
                if index >= 0:
                    self.serial_port_combo.setCurrentIndex(index)

    def test_serial_connection(self):
        """Prueba la conexión con el ESP32 seleccionado."""
        # Obtener el puerto del currentData del QComboBox
        port = self.serial_port_combo.currentData() 
        if not port:
            self.status_bar.showMessage("Error: Seleccione un puerto válido", 3000)
            self.serial_status_label.setText("Error: Puerto no seleccionado")
            return
            
        try:
            baudrate = int(self.baudrate_combo.currentText())
        except ValueError:
            self.status_bar.showMessage("Error: Baudrate inválido", 3000)
            self.serial_status_label.setText("Error: Baudrate inválido")
            return
        
        self.status_bar.showMessage(f"Intentando conectar a {port} a {baudrate} baudios...", 0)
        self.serial_status_label.setText(f"Probando {port}...")
        
        # Intentar establecer la conexión usando el serial_manager
        # Asumiendo que serial_manager está disponible como self.serial_manager o global
        if serial_manager.connect(port, baudrate, timeout=1.0, retries=1): # 1 intento para prueba rápida
            self.serial_status_label.setText(f"Conectado a {port}")
            self.status_bar.showMessage(f"Conexión establecida con {port} a {baudrate} baudios", 3000)
            
            # Desconectar después de la prueba para liberar el puerto
            serial_manager.disconnect()
            self.serial_status_label.setText(f"Desconectado (Prueba OK)")
        else:
            self.serial_status_label.setText("Error de conexión")
            self.status_bar.showMessage(f"No se pudo conectar a {port}. Verifique la conexión y los permisos.", 5000)
    
    def create_action_buttons(self, parent_layout):
        buttons_layout = QHBoxLayout()
        self.process_button = QPushButton("Procesar video")
        self.process_button.setMinimumHeight(40)
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self.process_video)
        self.save_config_button = QPushButton("Guardar configuración")
        self.save_config_button.clicked.connect(self.save_settings_from_ui)
        self.stop_button = QPushButton("Detener")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.detener_procesamiento)
        buttons_layout.addWidget(self.process_button)
        buttons_layout.addWidget(self.stop_button)
        buttons_layout.addWidget(self.save_config_button)
        parent_layout.addLayout(buttons_layout)

    def populate_model_combo(self):
        self.model_path_combo.clear()
        models_dir = Path(__file__).parent.parent / "models"
        models_root = Path(__file__).parent.parent
        model_files = []
        if models_dir.exists() and models_dir.is_dir():
            model_files.extend(list(models_dir.glob("*.pt")))
        model_files.extend(list(models_root.glob("*.pt"))) # Also check project root

        model_names = sorted([model.name for model in model_files if model.is_file()]) # Ensure it's a file

        if not model_names:
            model_names = ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt"] # Defaults
            self.status_bar.showMessage("No se encontraron modelos .pt, usando predeterminados.", 3000)
        else:
            self.status_bar.showMessage(f"Se encontraron {len(model_names)} modelos.", 3000)
        self.model_path_combo.addItems(model_names)

    def browse_video_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar video", "",
            "Archivos de video (*.mp4 *.avi *.mov *.mkv);;Todos los archivos (*)")
        if file_path:
            self.video_path_edit.setText(file_path)
            self.update_video_info(file_path)
            self.process_button.setEnabled(True)
            self.detener_previsualizacion() # Stop camera preview if a file is selected
            self.mostrar_frame_en_label(None) # Clear preview

    def update_video_info(self, video_path):
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

    def set_output_file(self):
        codec = self.codec_combo.currentText()
        recommended_ext = self._get_recommended_extension(codec)
        base_name = os.path.splitext(Path(self.output_path_edit.text()).name)[0] if self.output_path_edit.text() else "salida"
        default_name = f"{base_name}{recommended_ext}"
        filter_str = "MP4 (*.mp4);;AVI (*.avi);;MKV (*.mkv);;Todos los archivos (*)"
        if recommended_ext == ".avi":
            filter_str = "AVI (*.avi);;MP4 (*.mp4);;MKV (*.mkv);;Todos los archivos (*)"

        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar video como", default_name, filter_str)
        if file_path:
            file_ext = os.path.splitext(file_path)[1].lower()
            if not file_ext: file_path += recommended_ext; file_ext = recommended_ext
            self.output_path_edit.setText(file_path)
            self._update_codec_for_extension(file_ext)

    def save_settings_from_ui(self):
        settings.model_path = self.model_path_combo.currentText()
        settings.confidence_threshold = self.confidence_spin.value()
        settings.frames_espera = self.frames_wait_spin.value()
        settings.output_path = self.output_path_edit.text()
        settings.output_format = self.codec_combo.currentText()
        
        # Configuración serial
        settings.serial_port = self.serial_port_combo.currentData() or "COM3"
        settings.serial_baudrate = int(self.baudrate_combo.currentText())
        settings.serial_enabled = self.serial_enabled_check.isChecked()
        
        # Guardar configuraciones
        success = settings.save_settings()
        
        if success:
            self.status_bar.showMessage("Configuración guardada correctamente", 3000)
        else:
            self.status_bar.showMessage("Error al guardar configuración.", 3000)

    def load_settings_to_ui(self):
        settings.load_settings() # Ensure settings are loaded before accessing them
        index = self.model_path_combo.findText(settings.model_path)
        if index >= 0: self.model_path_combo.setCurrentIndex(index)
        self.confidence_spin.setValue(settings.confidence_threshold)
        self.frames_wait_spin.setValue(settings.frames_espera)
        self.output_path_edit.setText(settings.output_path)
        index = self.codec_combo.findText(settings.output_format)
        if index >= 0:
            self.codec_combo.setCurrentIndex(index)
        
        # Cargar configuración serial
        self.serial_enabled_check.setChecked(settings.serial_enabled)
        
        # Buscar puerto guardado en la lista desplegable
        port_found = False
        for i in range(self.serial_port_combo.count()):
            if self.serial_port_combo.itemData(i) == settings.serial_port:
                self.serial_port_combo.setCurrentIndex(i)
                port_found = True
                break
        
        if not port_found and settings.serial_port:
            # Si el puerto guardado no está en la lista, lo agregamos
            self.serial_port_combo.addItem(
                f"{settings.serial_port} (manual)", settings.serial_port
            )
            self.serial_port_combo.setCurrentIndex(self.serial_port_combo.count() - 1)
        
        # Seleccionar baudrate
        index = self.baudrate_combo.findText(str(settings.serial_baudrate))
        if index >= 0:
            self.baudrate_combo.setCurrentIndex(index)

    def reproducir_video_salida(self, path):
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            self.status_bar.showMessage(f"No se pudo abrir el video procesado: {path}", 5000)
            return

        self.status_bar.showMessage("Mostrando video procesado...", 3000)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            self.mostrar_frame_en_label(frame)
            QApplication.processEvents()
            time.sleep(1 / max(1, cap.get(cv2.CAP_PROP_FPS)))  # Evita división por cero

        cap.release()
        self.status_bar.showMessage("Visualización finalizada.", 3000)

    def process_video(self):
        try:  # Add try-except for rastreo import
            from rastreo import (
                inicializar_modelo, detectar_personas,
                extraer_ids, actualizar_rastreo, dibujar_anotaciones
            )
        except ImportError:
            self.status_bar.showMessage("Error: Módulo 'rastreo.py' no encontrado.", 5000)
            return

        params = self._get_processing_parameters()
        if not params:
            return

        self.procesando = True
        self.stop_button.setEnabled(True)
        self.process_button.setEnabled(False)
        self.status_bar.showMessage(f"Procesando: {params['video_path_display']}...", 0)

        try:
            model = inicializar_modelo(str(params['model_path']))
            cap, out, total_frames = self._setup_video_io(params)
            if not cap or (not out and not params['is_camera']):  # 'out' might be None if only previewing camera
                self.detener_procesamiento()
                return

            self._process_video_with_tracking(
                model, cap, out, params,
                detectar_personas, extraer_ids,
                actualizar_rastreo, dibujar_anotaciones,
                total_frames
            )

            if cap:
                cap.release()
            if out:
                out.release()

            if self.procesando:  # If not stopped by user
                if not params['is_camera']:
                    self.status_bar.showMessage(f"Procesado. Mostrando: {params['output_path']}", 3000)
                    self.reproducir_video_salida(params['output_path'])
                else:
                    self.status_bar.showMessage("Procesamiento en vivo finalizado.", 5000)

        except Exception as e:
            self.status_bar.showMessage(f"Error en procesamiento: {str(e)}", 5000)
            import traceback
            traceback.print_exc()

        finally:
            self.detener_procesamiento()  # Ensure state is reset

    def detener_procesamiento(self):
        self.procesando = False
        if self.camera_thread and self.input_type_combo.currentIndex() == 1: # If live camera processing was ongoing
             pass # CameraThread stop is handled by toggle_input_type or on_camera_selection_changed or closeEvent
        self.stop_button.setEnabled(False)
        self.process_button.setEnabled(True) # Re-enable process button based on input
        if self.input_type_combo.currentIndex() == 0: # File
            self.process_button.setEnabled(bool(self.video_path_edit.text()))
        else: # Camera
            self.process_button.setEnabled(True)

        self.status_bar.showMessage("Procesamiento detenido.", 3000)


    def _get_processing_parameters(self):
        model_name = self.model_path_combo.currentText()
        confidence = self.confidence_spin.value()
        frames_espera = self.frames_wait_spin.value()
        output_path = self.output_path_edit.text()
        codec = self.codec_combo.currentText()
        output_path = self._ensure_valid_extension(output_path, codec)
        is_camera = self.input_type_combo.currentIndex() == 1
        video_path_display = "Cámara en vivo"

        if is_camera:
            if self.camera_combo.count() == 0: self.refresh_cameras()
            if self.camera_combo.count() == 0:
                self.status_bar.showMessage("Error: No se detectaron cámaras.", 3000); return None
            camera_id = self.camera_combo.currentData()
            if camera_id is None: camera_id = 0 # Fallback
            video_path = camera_id
            video_path_display = self.camera_combo.currentText()
        else:
            video_path = self.video_path_edit.text()
            if not video_path:
                self.status_bar.showMessage("Error: No video seleccionado.", 3000); return None
            video_path_display = Path(video_path).name

        models_dir = Path(__file__).parent.parent / "models"
        model_path = models_dir / model_name
        if not model_path.exists():
            model_path = Path(__file__).parent.parent / model_name # Check root
            if not model_path.exists():
                self.status_bar.showMessage(f"Error: Modelo {model_name} no encontrado.", 3000); return None

        return {
            'video_path': video_path, 'is_camera': is_camera, 'model_path': model_path,
            'confidence': confidence, 'frames_espera': frames_espera,
            'output_path': output_path, 'codec': codec, 'video_path_display': video_path_display
        }

    def _setup_video_io(self, params):
        cap = None
        out = None
        total_frames = 0
        try:
            if params['is_camera']:
                # For live camera processing, VideoCapture is handled by CameraThread if just previewing,
                # or here if processing directly. For this merged version, _process_video_with_tracking will get frames.
                # If processing live to a file, we need a new VideoCapture instance.
                cap = cv2.VideoCapture(params['video_path'])
                if not cap.isOpened():
                    self.status_bar.showMessage(f"Error: No se pudo abrir la cámara ID {params['video_path']}", 3000)
                    return None, None, 0
                total_frames = -1 # Live camera
            else: # File
                cap = cv2.VideoCapture(params['video_path'])
                if not cap.isOpened():
                    self.status_bar.showMessage(f"Error: No se pudo abrir video {params['video_path']}", 3000)
                    return None, None, 0
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0: fps = 30.0

            # Setup output writer only if not just previewing camera
            # If it's a camera and we want to save the processed output:
            if not params['is_camera'] or (params['is_camera'] and params['output_path']):
                output_path = self._ensure_valid_extension(params['output_path'], params['codec'])
                params['output_path'] = output_path # Update params
                fourcc = cv2.VideoWriter_fourcc(*params['codec'])
                output_dir = os.path.dirname(output_path)
                if output_dir and not os.path.exists(output_dir): os.makedirs(output_dir)

                out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
                if not out.isOpened():
                    self.status_bar.showMessage("Error al crear archivo de salida. Intentando H264 para MP4...", 3000)
                    if params['codec'] == "MP4V" and os.path.splitext(output_path)[1].lower() == ".mp4":
                        fourcc = cv2.VideoWriter_fourcc(*"H264")
                        out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
                        if not out.isOpened():
                             self.status_bar.showMessage("Error al crear archivo de salida incluso con H264.", 3000)
                             if cap: cap.release()
                             return None, None, 0
            return cap, out, total_frames
        except Exception as e:
            self.status_bar.showMessage(f"Error en setup I/O: {str(e)}", 3000)
            if cap: cap.release()
            if out: out.release()
            return None, None, 0

    def _process_video_with_tracking(self, model, cap, out, params,
                                     detectar_personas, extraer_ids,
                                     actualizar_rastreo, dibujar_anotaciones, total_frames):
        primer_id, rastreo_id, ultima_coords, frames_perdidos = None, None, None, 0
        ids_globales = set()
        frame_count = 0
        controlar_servo = params['is_camera']  # Ejemplo: controlar servo solo para cámara en vivo

        while self.procesando:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            if not params['is_camera'] and total_frames > 0:
                progress = int((frame_count / total_frames) * 100)
                self.status_bar.showMessage(f"Procesando: {progress}%", 0)
            elif params['is_camera'] and frame_count % 30 == 0:
                self.status_bar.showMessage(f"Frames procesados (en vivo): {frame_count}", 0)

            frame_width = frame.shape[1]
            result = detectar_personas(model, frame, params['confidence'])
            if result is None:
                self.mostrar_frame_en_label(frame)  # Mostrar frame original si no se detecta nada
                if out:
                    out.write(frame)
                QApplication.processEvents()
                continue

            boxes = result.boxes
            ids_esta_frame = extraer_ids(boxes)

            primer_id, rastreo_id, reiniciar_coords, frames_perdidos = actualizar_rastreo(
                primer_id, rastreo_id, ids_esta_frame, frames_perdidos, params['frames_espera']
            )
            if reiniciar_coords:
                ultima_coords = None

            # Anotar frame procesado
            annotated_frame, ultima_coords = dibujar_anotaciones(
                result.plot(), boxes, rastreo_id, ultima_coords, ids_globales,
                frame_width, controlar_servo=controlar_servo
            )

            # Guardar salida si se desea
            if out:
                out.write(annotated_frame)

            # Mostrar en interfaz (siempre, sea cámara o video)
            self.mostrar_frame_en_label(annotated_frame)
            QApplication.processEvents()

        # Limpieza final se maneja en process_video o detener_procesamiento

    def toggle_input_type(self, index):
        # Use helper methods to manage visibility of QFormLayout rows
        file_row_idx = self._find_form_row_by_label_text("Archivo:")
        camera_row_idx = self._find_form_row_by_label_text("Cámara:")

        if index == 0:  # Archivo de video
            if file_row_idx != -1: self._set_form_row_visible(self.input_form_layout, file_row_idx, True)
            if camera_row_idx != -1: self._set_form_row_visible(self.input_form_layout, camera_row_idx, False)
            self.detener_previsualizacion()
            self.mostrar_frame_en_label(None) # Clear preview

            self._update_form_row_label_text(self.video_info_label, "Información:")
            if self.video_path_edit.text():
                self.update_video_info(self.video_path_edit.text())
            else:
                self.video_info_label.setText("No hay video seleccionado")

            self.process_button.setEnabled(bool(self.video_path_edit.text()))
            self.process_button.setText("Procesar video")
        else:  # Cámara en vivo
            if file_row_idx != -1: self._set_form_row_visible(self.input_form_layout, file_row_idx, False)
            if camera_row_idx != -1: self._set_form_row_visible(self.input_form_layout, camera_row_idx, True)

            self._update_form_row_label_text(self.video_info_label, "Info Cámara:")
            if self.camera_combo.count() == 0:
                self.refresh_cameras() # Auto-refresh if list is empty

            # Start preview with the currently selected (or first) camera
            self.on_camera_selection_changed(self.camera_combo.currentIndex())

            self.process_button.setEnabled(True)
            self.process_button.setText("Procesar en vivo")

    def on_camera_selection_changed(self, index):
        if self.input_type_combo.currentIndex() == 1: # Only if in "Cámara en vivo" mode
            if index >= 0 and self.camera_combo.count() > 0:
                camera_id = self.camera_combo.itemData(index)
                if camera_id is not None:
                    self.iniciar_previsualizacion_camara(camera_id, self.camera_combo.itemText(index))
            else:
                self.detener_previsualizacion()
                self.video_info_label.setText("Ninguna cámara seleccionada.")
                self.mostrar_frame_en_label(None)


    def iniciar_previsualizacion_camara(self, camera_id, camera_description=""):
        self.detener_previsualizacion() # Stop any existing thread
        self.camera_thread = CameraThread(camera_id)
        self.camera_thread.frame_received.connect(self.mostrar_frame_en_label)
        self.camera_thread.camera_info_signal.connect(self.update_camera_info_label_from_thread)
        self.camera_thread.camera_error_signal.connect(self.handle_camera_error_from_thread)
        self.camera_thread.start()
        self.video_info_label.setText(f"Iniciando {camera_description}...")
        self.status_bar.showMessage(f"Iniciando previsualización de {camera_description}", 2000)

    def update_camera_info_label_from_thread(self, info_text):
        self.video_info_label.setText(info_text)

    def handle_camera_error_from_thread(self, error_text):
        self.video_info_label.setText(error_text)
        self.status_bar.showMessage(error_text, 5000)
        self.mostrar_frame_en_label(None) # Clear preview on error

    def detener_previsualizacion(self):
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread.frame_received.disconnect(self.mostrar_frame_en_label)
            self.camera_thread.camera_info_signal.disconnect(self.update_camera_info_label_from_thread)
            self.camera_thread.camera_error_signal.disconnect(self.handle_camera_error_from_thread)
            self.camera_thread = None
        # self.video_display_label.clear() # Cleared by mostrar_frame_en_label(None)
        # self.video_display_label.setText("Vista previa detenida.")


    def refresh_cameras(self):
        self.status_bar.showMessage("Buscando cámaras...", 0)
        QApplication.processEvents() # Update UI
        self.camera_combo.clear()
        self.available_cameras = self.detect_available_cameras(max_cameras=5)
        if not self.available_cameras or (len(self.available_cameras) == 1 and self.available_cameras[0][0] == 0 and "predeterminada" in self.available_cameras[0][1]): # Check if only default was added
             # Add a default entry if detection truly finds nothing or only the placeholder
            if not any(cam[0] == 0 for cam in self.available_cameras): # ensure default isn't duplicated
                 self.camera_combo.addItem("Cámara 0 (predeterminada)", 0)
            if not self.available_cameras : self.status_bar.showMessage("No se detectaron cámaras. Usando ID 0.", 3000)

        for cam_id, desc in self.available_cameras:
            self.camera_combo.addItem(desc, cam_id)

        if self.available_cameras:
            self.status_bar.showMessage(f"Se encontraron {len(self.available_cameras)} cámaras.", 3000)
            if self.input_type_combo.currentIndex() == 1: # If in camera mode, start preview for the first one
                self.on_camera_selection_changed(0)
        elif self.camera_combo.count() > 0 and self.input_type_combo.currentIndex() == 1 : # Default was added
             self.on_camera_selection_changed(0)


    def test_camera_info(self): # Renamed from test_camera
        if self.input_type_combo.currentIndex() != 1:
             self.status_bar.showMessage("Cambie a 'Cámara en vivo' para obtener info.",3000)
             return

        if self.camera_combo.count() == 0:
            self.refresh_cameras()
            if self.camera_combo.count() == 0:
                self.video_info_label.setText("No hay cámaras disponibles para probar.")
                self.status_bar.showMessage("No hay cámaras disponibles.", 3000)
                return

        camera_id = self.camera_combo.currentData()
        camera_desc = self.camera_combo.currentText()
        if camera_id is None:
            self.video_info_label.setText("Ninguna cámara seleccionada para probar.")
            return

        self.status_bar.showMessage(f"Obteniendo info de {camera_desc}...", 0)
        # Attempt to open camera just for info - preview is handled by CameraThread
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            info_text = f"Error: No se pudo abrir {camera_desc}"
            self.video_info_label.setText(info_text)
            self.status_bar.showMessage(info_text, 3000)
            return

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        info_text = f"{camera_desc}: {width}x{height} @ {fps:.2f} FPS"
        self.video_info_label.setText(info_text)
        self.status_bar.showMessage(f"Info de {camera_desc} obtenida.", 3000)
        # If live preview isn't already running for this camera, start it
        if not (self.camera_thread and self.camera_thread.isRunning() and self.camera_thread.camera_id == camera_id):
            self.iniciar_previsualizacion_camara(camera_id, camera_desc)


    def detect_available_cameras(self, max_cameras=10):
        detected_cameras = []
        self.status_bar.showMessage("Detectando cámaras (puede tardar)...", 0)
        QApplication.processEvents()

        # Try to suppress OpenCV error messages during probing
        prev_log_level = None
        try:
            if hasattr(cv2, 'setLogLevel') and hasattr(cv2, 'LOG_LEVEL_SILENT'):
                prev_log_level = cv2.getLogLevel()
                cv2.setLogLevel(cv2.LOG_LEVEL_SILENT)
        except Exception: pass

        for i in range(max_cameras):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if sys.platform == "win32" else None)
                time.sleep(0.1) # Allow time for camera to initialize
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
                if cap: cap.release() # Ensure release on error
                continue

        # Restore previous log level
        try:
            if prev_log_level is not None and hasattr(cv2, 'setLogLevel'):
                cv2.setLogLevel(prev_log_level)
        except Exception: pass

        if not detected_cameras:
            # self.status_bar.showMessage("No se detectaron cámaras. Usando ID 0 por defecto.", 3000)
            # detected_cameras.append((0, "Cámara 0 (predeterminada)")) # Let refresh_cameras handle default
            pass
        return detected_cameras


    def mostrar_frame_en_label(self, frame):
        if frame is None:
            self.video_display_label.clear()
            self.video_display_label.setText("Vista previa no disponible" if self.input_type_combo.currentIndex() == 1 else "Video no cargado")
            return

        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            # Scale pixmap to fit label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(self.video_display_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.video_display_label.setPixmap(scaled_pixmap)
        except Exception as e:
            # print(f"Error displaying frame: {e}")
            self.video_display_label.setText(f"Error al mostrar frame:\n{e}")


    def _get_recommended_extension(self, codec):
        return self.codec_extension_map.get(codec.upper(), ".avi")

    def _ensure_valid_extension(self, file_path, codec, update_ui=True):
        if not file_path: return file_path
        current_ext = os.path.splitext(file_path)[1].lower()
        recommended_ext = self._get_recommended_extension(codec)
        if current_ext not in [".avi", ".mp4", ".mkv"] or \
           (current_ext != recommended_ext and self._is_extension_incompatible(current_ext, codec)):
            new_path = os.path.splitext(file_path)[0] + recommended_ext
            if update_ui:
                self.output_path_edit.setText(new_path)
                self.status_bar.showMessage(f"Extensión cambiada a {recommended_ext} para {codec}.", 3000)
            return new_path
        return file_path

    def _is_extension_incompatible(self, extension, codec):
        codec = codec.upper()
        if extension == ".mp4" and codec not in ["MP4V", "H264", "AVC1"]: return True
        if extension == ".avi" and codec not in ["XVID", "MJPG"]: return True
        return False

    def _update_codec_for_extension(self, extension):
        extension = extension.lower()
        current_codec = self.codec_combo.currentText()
        new_codec_str = None
        if extension == ".mp4" and current_codec not in ["MP4V", "H264", "AVC1"]: new_codec_str = "MP4V"
        elif extension == ".avi" and current_codec not in ["XVID", "MJPG"]: new_codec_str = "XVID"

        if new_codec_str:
            new_codec_index = self.codec_combo.findText(new_codec_str)
            if new_codec_index >= 0:
                self.codec_combo.setCurrentIndex(new_codec_index)
                self.status_bar.showMessage(f"Formato act. a {new_codec_str} para {extension}.", 3000)
                return True
        return False

    # QFormLayout helper methods
    def _find_form_row_by_label_text(self, label_text):
        """Finds a row index in self.input_form_layout by the QLabel's text."""
        if not hasattr(self, 'input_form_layout'): return -1
        for i in range(self.input_form_layout.rowCount()):
            label_item = self.input_form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            if label_item and label_item.widget() and isinstance(label_item.widget(), QLabel):
                if label_item.widget().text() == label_text:
                    return i
        return -1

    def _set_form_row_visible(self, form_layout, row_index, visible):
        if row_index < 0 or row_index >= form_layout.rowCount(): return
        label_item = form_layout.itemAt(row_index, QFormLayout.ItemRole.LabelRole)
        if label_item and label_item.widget(): label_item.widget().setVisible(visible)
        field_item = form_layout.itemAt(row_index, QFormLayout.ItemRole.FieldRole)
        if field_item and field_item.widget(): field_item.widget().setVisible(visible)

    def _update_form_row_label_text(self, target_field_widget, new_label_text):
        """Updates the label text for a row containing target_field_widget in self.input_form_layout."""
        if not hasattr(self, 'input_form_layout'): return
        for i in range(self.input_form_layout.rowCount()):
            field_item = self.input_form_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if field_item and field_item.widget() == target_field_widget:
                label_item = self.input_form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
                if label_item and label_item.widget() and isinstance(label_item.widget(), QLabel):
                    label_item.widget().setText(new_label_text)
                    return

    def closeEvent(self, event):
        self.detener_previsualizacion()
        self.detener_procesamiento() # Ensure processing stops if ongoing
        # Any other cleanup
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Apply a style (optional)
    # app.setStyle("Fusion")
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())