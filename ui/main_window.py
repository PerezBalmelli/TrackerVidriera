"""
Módulo principal para la interfaz de usuario de TrackerVidriera.
Implementa la ventana principal y todos los controles de la aplicación.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QFileDialog, QComboBox,
    QDoubleSpinBox, QSpinBox, QGroupBox, QFormLayout,
    QLineEdit, QApplication, QSlider, QStatusBar
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont, QDoubleValidator

import sys
import os
from pathlib import Path
import glob

# Importamos módulos del proyecto
from config.settings import settings
from core.video_output import VideoOutputManager


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación TrackerVidriera."""
    
    def __init__(self):
        super().__init__()
        
        # Configuración básica de la ventana
        self.setWindowTitle("TrackerVidriera")
        self.setMinimumSize(800, 600)
        
        # Inicializar instancias
        self.video_output = VideoOutputManager()
        
        # Mapa de códecs a extensiones de archivo
        self.codec_extension_map = {
            "XVID": ".avi",
            "MP4V": ".mp4",
            "MJPG": ".avi",
            "H264": ".mp4",
            "AVC1": ".mp4"
        }
        
        # Lista de cámaras disponibles
        self.available_cameras = []
        
        # Crear barra de estado antes que la interfaz
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo")
        
        # Crear interfaz
        self.init_ui()
        
        # Cargar configuraciones previas
        self.load_settings_to_ui()
    
    def init_ui(self):
        """Inicializa todos los componentes de la interfaz de usuario."""
        # Widget central
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # Panel superior con título
        header_layout = QHBoxLayout()
        title_label = QLabel("TrackerVidriera")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        
        # Contenedor principal (panel izquierdo de configuración y panel derecho de visualización)
        content_layout = QHBoxLayout()
        
        # Panel izquierdo - Configuraciones
        config_panel = QWidget()
        config_layout = QVBoxLayout(config_panel)
        config_layout.setSpacing(10)
        
        # Grupo de configuración de entrada
        self.create_input_config_group(config_layout)
        
        # Grupo de configuración del modelo
        self.create_model_config_group(config_layout)
        
        # Grupo de configuración de salida
        self.create_output_config_group(config_layout)
        
        # Botones de acción
        self.create_action_buttons(config_layout)
        
        # Añadir espacio al final
        config_layout.addStretch()
        
        # Añadir panel de configuración al contenedor principal
        content_layout.addWidget(config_panel, 1)  # Proporción 1
        
        # Añadir el contenedor principal al layout principal
        main_layout.addLayout(content_layout)
        
        # Establecer widget central
        self.setCentralWidget(central_widget)
    
    def create_input_config_group(self, parent_layout):
        """Crea el grupo de configuración de entrada de video."""
        input_group = QGroupBox("Configuración de entrada")
        input_layout = QFormLayout()
        
        # Selector de tipo de entrada (archivo o cámara)
        self.input_type_combo = QComboBox()
        self.input_type_combo.addItems(["Archivo de video", "Cámara en vivo"])
        self.input_type_combo.currentIndexChanged.connect(self.toggle_input_type)
        input_layout.addRow("Tipo de entrada:", self.input_type_combo)
        
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
        
        # Panel para cámara
        self.camera_panel = QWidget()
        camera_layout = QHBoxLayout(self.camera_panel)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        
        # Reemplazar el QSpinBox por un QComboBox para las cámaras
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(250)
        self.camera_combo.setToolTip("Seleccione la cámara a utilizar")
        
        # Botón para refrescar la lista de cámaras
        refresh_cameras_button = QPushButton("🔄")
        refresh_cameras_button.setToolTip("Actualizar lista de cámaras")
        refresh_cameras_button.setFixedWidth(30)
        refresh_cameras_button.clicked.connect(self.refresh_cameras)
        
        self.test_camera_button = QPushButton("Probar cámara")
        self.test_camera_button.clicked.connect(self.test_camera)
        
        camera_layout.addWidget(self.camera_combo)
        camera_layout.addWidget(refresh_cameras_button)
        camera_layout.addWidget(self.test_camera_button)
        
        # Añadir paneles al layout principal, inicialmente solo mostramos el de archivo
        input_layout.addRow("Archivo:", self.file_panel)
        input_layout.addRow("Cámara:", self.camera_panel)
        self.camera_panel.setVisible(False)
        
        # Información del video/cámara
        self.video_info_label = QLabel("No hay entrada seleccionada")
        input_layout.addRow("Información:", self.video_info_label)
        
        input_group.setLayout(input_layout)
        parent_layout.addWidget(input_group)
        
    def refresh_cameras(self):
        """Detecta y actualiza la lista de cámaras disponibles."""
        self.status_bar.showMessage("Buscando cámaras disponibles...", 0)
        self.camera_combo.clear()
        
        # Detectar cámaras
        cameras = self.detect_available_cameras(max_cameras=5)  # Limitamos a 5 para que sea rápido
        
        if not cameras:
            self.camera_combo.addItem("Cámara 0 (predeterminada)")
            self.status_bar.showMessage("No se detectaron cámaras. Usando ID 0 por defecto.", 3000)
        else:
            # Añadir las cámaras detectadas al combo
            for camera_id, description in cameras:
                self.camera_combo.addItem(description, camera_id)
            self.status_bar.showMessage(f"Se encontraron {len(cameras)} cámaras", 3000)
    
    def create_model_config_group(self, parent_layout):
        """Crea el grupo de configuración del modelo de detección."""
        model_group = QGroupBox("Configuración del modelo")
        model_layout = QFormLayout()
        
        # Selector de modelo - Detectar modelos disponibles
        self.model_path_combo = QComboBox()
        self.populate_model_combo()
        model_layout.addRow("Modelo:", self.model_path_combo)
        
        # Umbral de confianza
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.1, 1.0)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setValue(0.6)
        model_layout.addRow("Umbral de confianza:", self.confidence_spin)
        
        # Frames de espera
        self.frames_wait_spin = QSpinBox()
        self.frames_wait_spin.setRange(1, 30)
        self.frames_wait_spin.setValue(10)
        model_layout.addRow("Frames de espera:", self.frames_wait_spin)
        
        model_group.setLayout(model_layout)
        parent_layout.addWidget(model_group)
    
    def populate_model_combo(self):
        """Busca y añade los modelos disponibles al combo box."""
        # Limpiar el combo
        self.model_path_combo.clear()
        
        # Buscar modelos en la carpeta models/
        models_dir = Path(__file__).parent.parent / "models"
        models_root = Path(__file__).parent.parent
        
        # Buscar archivos .pt en la carpeta models/ y en la raíz del proyecto
        model_files = []
        
        # Buscar en la carpeta models/ si existe
        if models_dir.exists() and models_dir.is_dir():
            model_files.extend(list(models_dir.glob("*.pt")))
        
        # Buscar también en la raíz del proyecto
        model_files.extend(list(models_root.glob("*.pt")))
        
        # Convertir a rutas relativas y ordenar alfabéticamente
        model_names = sorted([model.name for model in model_files])
        
        if not model_names:
            # Si no se encuentran modelos, añadir opciones predeterminadas
            model_names = ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt"]
            self.status_bar.showMessage("No se encontraron modelos en la carpeta 'models/', usando valores predeterminados", 3000)
        else:
            self.status_bar.showMessage(f"Se encontraron {len(model_names)} modelos", 3000)
        
        # Añadir al combo
        self.model_path_combo.addItems(model_names)
    
    def create_output_config_group(self, parent_layout):
        """Crea el grupo de configuración de salida de video."""
        output_group = QGroupBox("Configuración de salida")
        output_layout = QFormLayout()
        
        # Ruta de salida
        self.output_path_edit = QLineEdit("salida.avi")
        output_save_button = QPushButton("Guardar como...")
        output_save_button.clicked.connect(self.set_output_file)
        
        output_path_layout = QHBoxLayout()
        output_path_layout.addWidget(self.output_path_edit)
        output_path_layout.addWidget(output_save_button)
        
        output_layout.addRow("Archivo de salida:", output_path_layout)
        
        # Formato de salida (códec)
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["XVID", "MP4V", "MJPG", "H264", "AVC1"])
        output_layout.addRow("Formato:", self.codec_combo)
        
        output_group.setLayout(output_layout)
        parent_layout.addWidget(output_group)
    
    def create_action_buttons(self, parent_layout):
        """Crea los botones de acción principales."""
        buttons_layout = QHBoxLayout()
        
        # Botón de procesar video
        self.process_button = QPushButton("Procesar video")
        self.process_button.setMinimumHeight(40)
        self.process_button.setEnabled(False)  # Deshabilitado hasta que se seleccione un video
        self.process_button.clicked.connect(self.process_video)
        
        # Botón de guardar configuración
        self.save_config_button = QPushButton("Guardar configuración")
        self.save_config_button.clicked.connect(self.save_settings_from_ui)
        
        buttons_layout.addWidget(self.process_button)
        buttons_layout.addWidget(self.save_config_button)
        
        parent_layout.addLayout(buttons_layout)
    
    def browse_video_file(self):
        """Abre un diálogo para seleccionar un archivo de video."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar video", "", 
            "Archivos de video (*.mp4 *.avi *.mov *.mkv);;Todos los archivos (*)"
        )
        
        if file_path:
            self.video_path_edit.setText(file_path)
            self.update_video_info(file_path)
            self.process_button.setEnabled(True)
    
    def update_video_info(self, video_path):
        """Actualiza la información del video seleccionado."""
        import cv2
        
        # Obtener información del video
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
            self.video_info_label.setText(f"Error al leer información: {str(e)}")
    
    def set_output_file(self):
        """Abre un diálogo para seleccionar la ubicación del archivo de salida."""
        # Obtener el códec seleccionado para sugerir la extensión correcta
        codec = self.codec_combo.currentText()
        recommended_ext = self._get_recommended_extension(codec)
        
        # Crear nombre predeterminado con la extensión correcta
        if self.output_path_edit.text():
            base_name = os.path.splitext(Path(self.output_path_edit.text()).name)[0]
        else:
            base_name = "salida"
        
        default_name = f"{base_name}{recommended_ext}"
        
        # Configurar el filtro adecuado basado en el códec
        if recommended_ext == ".avi":
            filter_str = "AVI (*.avi);;MP4 (*.mp4);;MKV (*.mkv);;Todos los archivos (*)"
        elif recommended_ext == ".mp4":
            filter_str = "MP4 (*.mp4);;AVI (*.avi);;MKV (*.mkv);;Todos los archivos (*)"
        else:
            filter_str = "AVI (*.avi);;MP4 (*.mp4);;MKV (*.mkv);;Todos los archivos (*)"
        
        # Mostrar diálogo
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Guardar video como", default_name, filter_str
        )
        
        if file_path:
            # Asegurar que la extensión esté presente
            file_ext = os.path.splitext(file_path)[1].lower()
            if not file_ext:
                file_path += recommended_ext
                file_ext = recommended_ext
            
            self.output_path_edit.setText(file_path)
            
            # Actualizar el códec según la extensión seleccionada por el usuario
            self._update_codec_for_extension(file_ext)
    def save_settings_from_ui(self):
        """Guarda la configuración actual de la UI en el objeto de configuración."""
        # Actualizar configuraciones desde la UI
        settings.model_path = self.model_path_combo.currentText()
        settings.confidence_threshold = self.confidence_spin.value()
        settings.frames_espera = self.frames_wait_spin.value()
        settings.output_path = self.output_path_edit.text()
        settings.output_format = self.codec_combo.currentText()
        
        # Guardar configuraciones
        success = settings.save_settings()
        
        if success:
            self.status_bar.showMessage("Configuración guardada correctamente", 3000)
        else:
            self.status_bar.showMessage("Error al guardar la configuración", 3000)
    
    def load_settings_to_ui(self):
        """Carga la configuración desde el objeto de configuración a la UI."""
        index = self.model_path_combo.findText(settings.model_path)
        if index >= 0:
            self.model_path_combo.setCurrentIndex(index)
        
        self.confidence_spin.setValue(settings.confidence_threshold)
        self.frames_wait_spin.setValue(settings.frames_espera)
        self.output_path_edit.setText(settings.output_path)
        
        index = self.codec_combo.findText(settings.output_format)
        if index >= 0:
            self.codec_combo.setCurrentIndex(index)
    
    def process_video(self):
        """Procesa el video seleccionado utilizando la lógica de rastreo."""
        # Importar funciones de rastreo.py
        from rastreo import (
            inicializar_modelo, detectar_personas, 
            extraer_ids, actualizar_rastreo, dibujar_anotaciones
        )
        import cv2
        
        # Obtener parámetros de configuración
        params = self._get_processing_parameters()
        if not params:
            return
            
        # Iniciar procesamiento
        self.status_bar.showMessage(f"Procesando video: {params['video_path']}...", 0)
        
        try:
            # Inicializar el modelo
            model = inicializar_modelo(str(params['model_path']))
            
            # Configurar video de entrada y salida
            cap, out, total_frames = self._setup_video_io(params)
            if not cap or not out:
                return
                
            # Realizar el procesamiento del video utilizando funciones de rastreo.py
            self._process_video_with_tracking(
                model, cap, out, params['confidence'], 
                params['frames_espera'], total_frames,
                detectar_personas, extraer_ids, 
                actualizar_rastreo, dibujar_anotaciones
            )
            
            # Liberar recursos
            cap.release()
            out.release()
            
            self.status_bar.showMessage(
                f"Video procesado correctamente. Guardado en: {params['output_path']}", 5000
            )
            
        except Exception as e:
            self.status_bar.showMessage(f"Error durante el procesamiento: {str(e)}", 5000)
            import traceback
            traceback.print_exc()
    
    def _get_processing_parameters(self):
        """Obtiene y valida los parámetros de procesamiento desde la UI."""
        model_name = self.model_path_combo.currentText()
        confidence = self.confidence_spin.value()
        frames_espera = self.frames_wait_spin.value()
        output_path = self.output_path_edit.text()
        codec = self.codec_combo.currentText()
        
        # Asegurar que la extensión del archivo coincida con el códec seleccionado
        output_path = self._ensure_valid_extension(output_path, codec)
        
        # Determinar el tipo de entrada (archivo o cámara)
        is_camera = self.input_type_combo.currentIndex() == 1
        
        if is_camera:
            # Si no hay cámaras detectadas, intentar buscarlas primero
            if self.camera_combo.count() == 0:
                self.refresh_cameras()
                if self.camera_combo.count() == 0:
                    self.status_bar.showMessage("Error: No se detectaron cámaras", 3000)
                    return None
            
            # Entrada desde cámara - obtener ID del ComboBox
            camera_id = self.camera_combo.currentData()
            if camera_id is None:
                # Usar índice 0 como fallback si no hay datos asociados
                camera_id = 0
                
            video_path = camera_id  # Guardamos el ID de la cámara
        else:
            # Entrada desde archivo
            video_path = self.video_path_edit.text()
            if not video_path:
                self.status_bar.showMessage("Error: No se ha seleccionado ningún video", 3000)
                return None
            
        # Verificar que el modelo existe
        models_dir = Path(__file__).parent.parent / "models"
        model_path = models_dir / model_name
        if not model_path.exists():
            model_path = Path(__file__).parent.parent / model_name
            if not model_path.exists():
                self.status_bar.showMessage(f"Error: No se encuentra el modelo {model_name}", 3000)
                return None
                
        return {
            'video_path': video_path,
            'is_camera': is_camera,
            'model_path': model_path,
            'confidence': confidence,
            'frames_espera': frames_espera,
            'output_path': output_path,
            'codec': codec
        }
    
    def _setup_video_io(self, params):
        """Configura el video de entrada y salida para el procesamiento."""
        import cv2
        import os
        
        try:
            # Abrir video o cámara
            if params['is_camera']:
                # Es una cámara
                camera_id = params['video_path']  # El ID de la cámara
                cap = cv2.VideoCapture(camera_id)
                if not cap.isOpened():
                    self.status_bar.showMessage(f"Error: No se pudo abrir la cámara ID {camera_id}", 3000)
                    return None, None, 0
                
                # Para cámaras en vivo, no hay total_frames, usamos valor especial -1
                total_frames = -1
            else:
                # Es un archivo de video
                video_path = params['video_path']
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    self.status_bar.showMessage(f"Error: No se pudo abrir el video {video_path}", 3000)
                    return None, None, 0
                
                # Para archivos, obtenemos el número total de frames
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                
            # Obtener propiedades del video/cámara
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Si la cámara reporta fps = 0 (común en algunas webcams), usar un valor predeterminado
            if fps <= 0:
                fps = 30.0
                
            # Configurar el escritor de video
            # Asegurar que la extensión del archivo coincida con el códec seleccionado
            output_path = self._ensure_valid_extension(params['output_path'], params['codec'])
            params['output_path'] = output_path  # Actualizar en los parámetros
            
            # Configurar el escritor de video con el códec correcto
            fourcc = cv2.VideoWriter_fourcc(*params['codec'])
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
            
            if not out.isOpened():
                self.status_bar.showMessage("Error: No se pudo crear el archivo de salida. Verificando compatibilidad...", 3000)
                # Intentar con un códec alternativo si falla
                if params['codec'] == "MP4V" and os.path.splitext(output_path)[1].lower() == ".mp4":
                    alternate_codec = "H264"
                    self.status_bar.showMessage(f"Intentando con códec alternativo: {alternate_codec}", 3000)
                    fourcc = cv2.VideoWriter_fourcc(*alternate_codec)
                    out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
            
            return cap, out, total_frames
        except Exception as e:
            self.status_bar.showMessage(f"Error al configurar el procesamiento: {str(e)}", 3000)
            return None, None, 0
    
    def _process_video_with_tracking(self, model, cap, out, confidence, frames_espera, 
                                    total_frames, detectar_personas, extraer_ids,
                                    actualizar_rastreo, dibujar_anotaciones):
        """
        Procesa cada frame del video utilizando las funciones importadas de rastreo.py.
        """
        import cv2
        
        # Variables para el rastreo
        primer_id = None
        rastreo_id = None
        ids_globales = set()
        ultima_coords = None
        frames_perdidos = 0
        frame_count = 0
        
        # Para modo de cámara en vivo, mostrar el proceso en tiempo real
        is_live_camera = total_frames == -1
        window_name = "TrackerVidriera - Procesamiento en vivo"
        
        # Determinar si debemos controlar el servo (solo para cámara en vivo)
        controlar_servo = is_live_camera
        
        if is_live_camera:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            self.status_bar.showMessage(f"Procesando cámara en vivo. {'Controlando servo. ' if controlar_servo else ''}Presione 'q' para detener.", 0)
        else:
            self.status_bar.showMessage("Procesando archivo de video (sin control de servo)...", 0)
        
        # Procesar frame por frame
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Actualizar barra de estado con progreso
            frame_count += 1
            if not is_live_camera and total_frames > 0:
                progress = int((frame_count / total_frames) * 100)
                self.status_bar.showMessage(f"Procesando video: {progress}% completado", 0)
            elif frame_count % 30 == 0:  # Actualizar cada 30 frames para cámara en vivo
                self.status_bar.showMessage(f"Frames procesados: {frame_count}", 0)
            
            # Obtener el ancho del frame para pasarlo a dibujar_anotaciones
            frame_width = frame.shape[1]
            
            # Detectar personas usando la función de rastreo.py
            result = detectar_personas(model, frame, confidence)
            if result is None:
                continue
                
            boxes = result.boxes
            
            # Extraer IDs en este frame
            ids_esta_frame = extraer_ids(boxes)
            
            # Actualizar rastreo usando la función de rastreo.py
            primer_id, rastreo_id, reiniciar_coords, frames_perdidos = actualizar_rastreo(
                primer_id, rastreo_id, ids_esta_frame, frames_perdidos, frames_espera
            )
            
            if reiniciar_coords:
                ultima_coords = None
            
            # Dibujar anotaciones usando la función de rastreo.py
            annotated, ultima_coords = dibujar_anotaciones(
                result.plot(), boxes, rastreo_id, ultima_coords, ids_globales,
                frame_width, controlar_servo=controlar_servo  # Controlar servo solo en modo cámara en vivo
            )
            
            # Guardar frame procesado
            out.write(annotated)
            
            # Si es cámara en vivo, mostrar el resultado en tiempo real
            if is_live_camera:
                cv2.imshow(window_name, annotated)
                # Verificar si el usuario quiere detener el proceso (presionando 'q')
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        
        # Cerrar ventanas si estábamos en modo cámara en vivo
        if is_live_camera:
            cv2.destroyAllWindows()
    
    def toggle_input_type(self, index):
        """Cambia entre los modos de entrada: archivo de video o cámara en vivo."""
        # Obtener el layout de formulario del grupo de entrada
        form_layout = self.file_panel.parent().layout()
        
        # Encontrar las filas correspondientes a Archivo y Cámara
        file_row = self._find_form_row(form_layout, self.file_panel)
        camera_row = self._find_form_row(form_layout, self.camera_panel)
        
        if index == 0:  # Archivo de video
            # Mostrar fila de archivo y ocultar fila de cámara
            if file_row >= 0:
                self._set_form_row_visible(form_layout, file_row, True)
            if camera_row >= 0:
                self._set_form_row_visible(form_layout, camera_row, False)
            
            # Actualizar etiqueta de información
            self._update_form_row_label(form_layout, self.video_info_label, "Información:")
            
            # Actualizar información del video si hay uno seleccionado
            if self.video_path_edit.text():
                self.update_video_info(self.video_path_edit.text())
            else:
                self.video_info_label.setText("No hay video seleccionado")
                
            # Habilitar el botón de procesar solo si hay un video seleccionado
            self.process_button.setEnabled(bool(self.video_path_edit.text()))
            self.process_button.setText("Procesar video")
        else:  # Cámara en vivo
            # Ocultar fila de archivo y mostrar fila de cámara
            if file_row >= 0:
                self._set_form_row_visible(form_layout, file_row, False)
            if camera_row >= 0:
                self._set_form_row_visible(form_layout, camera_row, True)
            
            # Actualizar etiqueta de información
            self._update_form_row_label(form_layout, self.video_info_label, "Información cámara:")
            
            self.video_info_label.setText("Sin información (usar 'Probar cámara')")
            
            # Si no hay cámaras detectadas todavía, buscarlas automáticamente
            if self.camera_combo.count() == 0:
                self.refresh_cameras()
            
            # Habilitar el botón de procesar para la cámara
            self.process_button.setEnabled(True)
            self.process_button.setText("Iniciar procesamiento en vivo")

    def test_camera(self):
        """Prueba la cámara seleccionada para verificar que funciona."""
        import cv2
        
        # Si no hay cámaras detectadas, intentar buscarlas primero
        if self.camera_combo.count() == 0:
            self.refresh_cameras()
            if self.camera_combo.count() == 0:
                self.status_bar.showMessage("No se detectaron cámaras disponibles", 3000)
                return
        
        # Obtener el ID de la cámara seleccionada
        camera_id = self.camera_combo.currentData()
        if camera_id is None:
            # Usar el índice como ID si no hay datos asociados (para compatibilidad)
            camera_id = 0
        
        self.status_bar.showMessage(f"Probando cámara {self.camera_combo.currentText()}... Presione ESC para cerrar", 0)
        
        # Intentar abrir la cámara
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            self.status_bar.showMessage(f"Error: No se pudo abrir la cámara seleccionada", 3000)
            self.video_info_label.setText(f"Error: No se pudo abrir la cámara seleccionada")
            return
        
        # Leer un frame para obtener las propiedades
        ret, frame = cap.read()
        if not ret:
            self.status_bar.showMessage(f"Error: No se pudo leer desde la cámara seleccionada", 3000)
            self.video_info_label.setText(f"Error: No se pudo leer desde la cámara seleccionada")
            cap.release()
            return
        
        # Mostrar información de la cámara
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        info_text = f"Cámara: {self.camera_combo.currentText()}, Resolución: {width}x{height}, FPS: {fps:.2f}"
        self.video_info_label.setText(info_text)
        
        # Crear ventana para mostrar la cámara en tiempo real
        window_name = f"Prueba de {self.camera_combo.currentText()}"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        # Bucle para mostrar la cámara en tiempo real
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Mostrar el frame actual
            cv2.imshow(window_name, frame)
            
            # Comprobar si se ha pulsado ESC para salir
            key = cv2.waitKey(1)
            if key == 27:  # ESC
                break
        
        # Liberar recursos
        cap.release()
        cv2.destroyAllWindows()  # Cerrar todas las ventanas de OpenCV
        
        self.status_bar.showMessage(f"Prueba de cámara completada", 3000)
    
    def detect_available_cameras(self, max_cameras=10):
        """
        Detecta las cámaras disponibles en el sistema de manera segura.
        
        Args:
            max_cameras (int): Número máximo de cámaras a comprobar.
            
        Returns:
            list: Lista de tuplas (id, descripción) de las cámaras disponibles.
        """
        import cv2
        import time
        
        self.available_cameras = []
        self.status_bar.showMessage("Detectando cámaras (esto puede tardar unos segundos)...", 0)
        
        # Intentar suprimir los mensajes de error de OpenCV de forma compatible con cualquier versión
        try:
            # Intentar utilizar setLogLevel si está disponible
            if hasattr(cv2, 'setLogLevel') and hasattr(cv2, 'LOG_LEVEL_SILENT'):
                prev_log_level = cv2.getLogLevel()
                cv2.setLogLevel(cv2.LOG_LEVEL_SILENT)
        except Exception:
            # Si no está disponible, simplemente continuamos
            pass
        
        try:
            # En sistemas Windows, las cámaras suelen estar en índices consecutivos
            # empezando desde 0. Intentamos abrir cada índice.
            for i in range(max_cameras):
                try:
                    # Intentar usar CAP_DSHOW si está disponible (mejor en Windows)
                    if hasattr(cv2, 'CAP_DSHOW'):
                        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                    else:
                        cap = cv2.VideoCapture(i)
                    
                    # Darle un poco de tiempo para inicializar
                    time.sleep(0.1)
                    
                    if cap.isOpened():
                        # La cámara está disponible
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            description = f"Cámara {i}: {width}x{height}"
                            self.available_cameras.append((i, description))
                        cap.release()
                        time.sleep(0.1)  # Pequeña pausa entre cámaras
                    
                except Exception as e:
                    # Ignorar errores individuales y continuar con la siguiente cámara
                    pass
        
        finally:
            # Restaurar nivel de log previo si fue cambiado
            try:
                if hasattr(cv2, 'setLogLevel') and hasattr(cv2, 'LOG_LEVEL_SILENT'):
                    cv2.setLogLevel(prev_log_level)
            except Exception:
                pass
        
        if not self.available_cameras:
            self.status_bar.showMessage("No se detectaron cámaras disponibles. Usando ID 0 por defecto.", 3000)
            # Añadir una opción predeterminada de todas formas
            self.available_cameras.append((0, "Cámara 0 (predeterminada)"))
        else:
            self.status_bar.showMessage(f"Se encontraron {len(self.available_cameras)} cámaras", 3000)
            
        return self.available_cameras
    
    # Métodos de utilidad para manejo de extensiones de archivo
    
    def _get_recommended_extension(self, codec):
        """
        Obtiene la extensión de archivo recomendada para un códec.
        
        Args:
            codec (str): El códec de video.
            
        Returns:
            str: La extensión de archivo recomendada.
        """
        return self.codec_extension_map.get(codec, ".avi")
    
    def _ensure_valid_extension(self, file_path, codec, update_ui=True):
        """
        Asegura que el archivo tenga una extensión válida para el códec seleccionado.
        
        Args:
            file_path (str): Ruta del archivo.
            codec (str): Códec seleccionado.
            update_ui (bool): Si se debe actualizar la UI con la nueva ruta.
            
        Returns:
            str: Ruta del archivo con la extensión correcta.
        """
        if not file_path:
            return file_path
            
        current_ext = os.path.splitext(file_path)[1].lower()
        recommended_ext = self._get_recommended_extension(codec)
        
        # Si la extensión no es válida o no coincide con la recomendada
        if current_ext not in [".avi", ".mp4", ".mkv"] or (
            current_ext != recommended_ext and self._is_extension_incompatible(current_ext, codec)
        ):
            # Cambiar la extensión
            new_path = os.path.splitext(file_path)[0] + recommended_ext
            
            if update_ui:
                self.output_path_edit.setText(new_path)
                self.status_bar.showMessage(
                    f"La extensión se cambió a {recommended_ext} para coincidir con el formato {codec}", 3000
                )
                
            return new_path
            
        return file_path
    
    def _is_extension_incompatible(self, extension, codec):
        """
        Verifica si una extensión es incompatible con un códec.
        
        Args:
            extension (str): Extensión del archivo.
            codec (str): Códec seleccionado.
            
        Returns:
            bool: True si la extensión es incompatible con el códec.
        """
        if extension == ".mp4" and codec not in ["MP4V", "H264", "AVC1"]:
            return True
        if extension == ".avi" and codec not in ["XVID", "MJPG"]:
            return True
        return False
    
    def _update_codec_for_extension(self, extension):
        """
        Actualiza el códec en la UI basado en la extensión del archivo.
        
        Args:
            extension (str): Extensión del archivo.
            
        Returns:
            bool: True si se realizó un cambio en el códec.
        """
        extension = extension.lower()
        current_codec = self.codec_combo.currentText()
        
        if extension == ".mp4" and current_codec not in ["MP4V", "H264", "AVC1"]:
            new_codec_index = self.codec_combo.findText("MP4V")
            if new_codec_index >= 0:
                self.codec_combo.setCurrentIndex(new_codec_index)
                self.status_bar.showMessage(
                    f"Formato actualizado a MP4V para compatibilidad con el archivo {extension}", 3000
                )
                return True
                
        elif extension == ".avi" and current_codec not in ["XVID", "MJPG"]:
            new_codec_index = self.codec_combo.findText("XVID")
            if new_codec_index >= 0:
                self.codec_combo.setCurrentIndex(new_codec_index)
                self.status_bar.showMessage(
                    f"Formato actualizado a XVID para compatibilidad con el archivo {extension}", 3000
                )
                return True
                
        return False

    def _find_form_row(self, form_layout, widget):
        """
        Encuentra el índice de fila que contiene un widget específico en un QFormLayout.
        
        Args:
            form_layout: El QFormLayout donde buscar.
            widget: El widget a encontrar.
            
        Returns:
            int: Índice de la fila o -1 si no se encuentra.
        """
        from PyQt6.QtWidgets import QFormLayout
        
        for i in range(form_layout.rowCount()):
            item = form_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if item and item.widget() == widget:
                return i
        return -1
    
    def _set_form_row_visible(self, form_layout, row_index, visible):
        """
        Establece la visibilidad de una fila completa en un QFormLayout.
        
        Args:
            form_layout: El QFormLayout que contiene la fila.
            row_index: Índice de la fila.
            visible: True para mostrar, False para ocultar.
        """
        from PyQt6.QtWidgets import QFormLayout
        
        # Obtener widget de etiqueta
        label_item = form_layout.itemAt(row_index, QFormLayout.ItemRole.LabelRole)
        if label_item and label_item.widget():
            label_item.widget().setVisible(visible)
        
        # Obtener widget de campo
        field_item = form_layout.itemAt(row_index, QFormLayout.ItemRole.FieldRole)
        if field_item and field_item.widget():
            field_item.widget().setVisible(visible)
            
    def _update_form_row_label(self, form_layout, widget, new_label):
        """
        Actualiza la etiqueta de una fila en un QFormLayout.
        
        Args:
            form_layout: El QFormLayout donde se encuentra el widget.
            widget: El widget cuya etiqueta se quiere actualizar.
            new_label: La nueva etiqueta a asignar.
        """
        from PyQt6.QtWidgets import QFormLayout, QLabel
        
        # Encontrar el widget en el layout
        for i in range(form_layout.rowCount()):
            field_item = form_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if field_item and field_item.widget() == widget:
                # Obtener el widget de etiqueta
                label_item = form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
                if label_item and label_item.widget():
                    label_widget = label_item.widget()
                    if isinstance(label_widget, QLabel):
                        label_widget.setText(new_label)