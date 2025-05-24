"""
Módulo principal para la interfaz de usuario de TrackerVidriera.
Implementa la ventana principal y todos los controles de la aplicación.
"""
import sys
import os
import traceback
import cv2
import numpy as np
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStatusBar, QApplication, QPushButton
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

from ui.widgets.input_config_widget import InputConfigWidget
from ui.widgets.model_config_widget import ModelConfigWidget
from ui.widgets.output_config_widget import OutputConfigWidget
from ui.widgets.serial_config_widget import SerialConfigWidget
from ui.widgets.video_display_widget import VideoDisplayWidget
from ui.widgets.action_buttons_widget import ActionButtonsWidget

from core.serial_manager import serial_manager
from core.person_tracking_manager import PersonTrackingManager

try:
    from config.settings import settings
    from core.video_output import VideoOutputManager
except ImportError:
    print("Warning: Could not import 'settings' or 'VideoOutputManager'. Ensure they are in the correct path.")

    class DummySettings:
        def __init__(self):
            self.model_path = "yolov8n.pt"
            self.confidence_threshold = 0.6
            self.frames_espera = 10
            self.output_path = "salida.avi"
            self.output_format = "XVID"
            self.serial_port = "COM3"
            self.serial_baudrate = 115200
            self.serial_enabled = True
        def save_settings(self): return True
        def load_settings(self): pass
    settings = DummySettings()

    class DummyVideoOutputManager:
        pass
    VideoOutputManager = DummyVideoOutputManager


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación TrackerVidriera."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("TrackerVidriera")
        self.setMinimumSize(800, 600)

        self.procesando = False
        self.config_panel_width = 300  # Default width de config panel

        self.video_output = VideoOutputManager()
        self.person_tracker = PersonTrackingManager()  # Instancia para tracking y servo

        # Crear barra de estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo")

        # Inicializar la interfaz
        self.init_ui()

        # Ahora que la UI está construida, mostrar la ventana maximizada
        self.showMaximized()
        
        # Cargar configuración en los widgets de la UI
        self.load_settings_to_ui()
        
        # Configurar estado inicial basado en los widgets de la UI
        self.toggle_input_type(self.input_widget.get_input_type())

    def init_ui(self):
        """Inicializa la interfaz de usuario."""
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        # Encabezado
        header_layout = QHBoxLayout()
        title_label = QLabel("TrackerVidriera")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Boton rojo de stop (inicialmente oculto)
        self.new_stop_button_main = QPushButton("Stop")
        self.new_stop_button_main.setMinimumHeight(40)
        self.new_stop_button_main.setStyleSheet("background-color: red; color: white;")
        self.new_stop_button_main.clicked.connect(self.detener_procesamiento)
        self.new_stop_button_main.hide()
        header_layout.addWidget(self.new_stop_button_main)

        main_layout.addLayout(header_layout)

        # Contenido principal (panel de config + visualización)
        self.content_layout = QHBoxLayout()
        
        # Panel izquierdo - Configuración
        self.config_panel = QWidget()
        config_layout = QVBoxLayout(self.config_panel)
        config_layout.setSpacing(10)
        
        # Crear widgets de configuración
        self.input_widget = InputConfigWidget()
        self.model_widget = ModelConfigWidget()
        self.output_widget = OutputConfigWidget()
        self.serial_widget = SerialConfigWidget(serial_manager)
        self.action_buttons = ActionButtonsWidget()
        
        self.video_display = VideoDisplayWidget()

        # Conectar señales
        self.connect_widget_signals()
        
        # Añadir widgets al panel de configuración
        config_layout.addWidget(self.input_widget)
        config_layout.addWidget(self.model_widget)
        config_layout.addWidget(self.output_widget)
        config_layout.addWidget(self.serial_widget)
        config_layout.addWidget(self.action_buttons)
        config_layout.addStretch()
        
        self.content_layout.addWidget(self.config_panel, 1)
        
        # Panel derecho - Visualización de video
        self.content_layout.addWidget(self.video_display, 2)  # Proporción 2:1 para dar más espacio al video
        
        main_layout.addLayout(self.content_layout)
        self.setCentralWidget(central_widget)
        
        # Configurar atajo de teclado para alternar panel (Ctrl+B)
        shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        shortcut.activated.connect(self.toggle_config_panel)
    
    def connect_widget_signals(self):
        """Conecta las señales de los widgets."""
        # Input widget
        self.input_widget.input_type_changed.connect(self.toggle_input_type)
        self.input_widget.video_file_selected.connect(self.on_video_file_selected)
        self.input_widget.status_message.connect(self.show_status_message)
        self.input_widget.frame_received.connect(self.video_display.display_frame)
        self.input_widget.second_frame_received.connect(self.video_display.display_second_frame) # Conectar nueva señal
        self.input_widget.camera_selected.connect(self.on_main_camera_selected) # Para la cámara principal
        self.input_widget.second_camera_selected.connect(self.on_second_camera_selected) # Para la segunda cámara
        
        # Model widget
        self.model_widget.status_message.connect(self.show_status_message)
        
        # Serial widget
        self.serial_widget.status_message.connect(self.show_status_message)
        
        # Action buttons
        self.action_buttons.process_clicked.connect(self.process_video)
        self.action_buttons.stop_clicked.connect(self.detener_procesamiento)
        self.action_buttons.save_config_clicked.connect(self.save_settings_from_ui)
    
    def toggle_input_type(self, index):
        """Ajusta la UI según el tipo de entrada seleccionado."""
        if index == 0:  # Archivo de video
            self.action_buttons.enable_process_button(
                enabled=bool(self.input_widget.get_video_path()),
                text="Procesar video"
            )
        else:  # Cámara en vivo
            self.action_buttons.enable_process_button(True, "Procesar en vivo")
    
    def on_video_file_selected(self, file_path):
        """Maneja la selección de un archivo de video."""
        if file_path and self.input_widget.get_input_type() == 0:  # Si es tipo archivo
            self.action_buttons.enable_process_button(True)
            self.video_display.display_second_frame(None) # Limpiar la segunda vista previa si se cambia a video

    def on_main_camera_selected(self, camera_id, camera_description):
        """Maneja la selección de la cámara principal."""
        # Esta función podría usarse para lógica adicional si es necesario
        # cuando se selecciona la cámara principal.
        # Por ahora, la previsualización ya se maneja en InputConfigWidget.
        self.show_status_message(f"Cámara principal seleccionada: {camera_description}", 2000)

    def on_second_camera_selected(self, camera_id, camera_description):
        """Maneja la selección de la segunda cámara."""
        if camera_id != -1:
            self.show_status_message(f"Segunda cámara seleccionada: {camera_description}", 2000)
        else:
            self.show_status_message("Segunda cámara deshabilitada.", 2000)
            self.video_display.display_second_frame(None) # Limpiar la segunda vista previa
    
    def show_status_message(self, message, timeout=0):
        """Muestra un mensaje en la barra de estado."""
        self.status_bar.showMessage(message, timeout)
    
    def load_settings_to_ui(self):
        """Carga la configuración guardada en la interfaz."""
        settings.load_settings()
        
        # Configurar widgets con la configuración cargada
        # ... (Input widget settings - esto se hará a través de su propio método)
        self.input_widget.set_all_settings({
            "input_type": getattr(settings, 'input_type', 0), # Default a archivo si no existe
            "video_path": getattr(settings, 'video_path', None),
            "camera_id": getattr(settings, 'camera_id', 0),
            "second_camera_id": getattr(settings, 'second_camera_id', -1) # Default a Ninguna
        })

        self.model_widget.set_model_path(settings.model_path)
        self.model_widget.set_confidence(settings.confidence_threshold)
        self.model_widget.set_frames_wait(settings.frames_espera)
        
        self.output_widget.set_output_path(settings.output_path)
        self.output_widget.set_codec(settings.output_format)
        
        self.serial_widget.set_serial_port(settings.serial_port)
        self.serial_widget.set_baudrate(settings.serial_baudrate)
        self.serial_widget.set_serial_enabled(settings.serial_enabled)
        
        # Aplicar estado del panel guardado después de que la UI se haya inicializado completamente
        QTimer.singleShot(100, self._apply_panel_state)
    
    def _apply_panel_state(self):
        """Aplica el estado guardado del panel de configuración."""
        if not hasattr(self, 'config_panel_width') or self.config_panel_width <= 0:
            if hasattr(self, 'config_panel') and self.config_panel.width() > 0:
                self.config_panel_width = self.config_panel.width()
            else:
                self.config_panel_width = 300 # Fallback if panel not yet sized

        if settings.config_panel_collapsed:
            if self.config_panel.maximumWidth() > 0:
                 self.collapse_config_panel()
            else:
                self.config_panel.setMaximumWidth(0)
                if hasattr(self, 'expand_button'): # Show expand button if needed
                    self.expand_button.show()
        else:
            if self.config_panel.maximumWidth() == 0:
                self.expand_config_panel()

    def save_settings_from_ui(self):
        """Guarda la configuración actual."""
        input_settings = self.input_widget.get_all_settings()
        settings.input_type = input_settings.get("input_type")
        settings.video_path = input_settings.get("video_path")
        settings.camera_id = input_settings.get("camera_id")
        settings.second_camera_id = input_settings.get("second_camera_id")

        settings.model_path = self.model_widget.get_model_path()
        settings.confidence_threshold = self.model_widget.get_confidence()
        settings.frames_espera = self.model_widget.get_frames_wait()
        
        settings.output_path = self.output_widget.get_output_path()
        settings.output_format = self.output_widget.get_codec()
        
        settings.serial_port = self.serial_widget.get_serial_port()
        settings.serial_baudrate = self.serial_widget.get_baudrate()
        settings.serial_enabled = self.serial_widget.is_serial_enabled()
        
        # Guardar estado del panel de configuración
        if hasattr(self, 'config_panel'):
            settings.config_panel_collapsed = self.config_panel.width() <= 50
        
        success = settings.save_settings()
        
        if success:
            self.show_status_message("Configuración guardada correctamente", 3000)
        else:
            self.show_status_message("Error al guardar configuración.", 3000)

    def process_video(self):
        """Inicia el procesamiento del video o la cámara usando PersonTrackingManager."""
        params = self._get_processing_parameters()
        if not params:
            return

        self.procesando = True
        is_live_camera_mode = self.input_widget.get_input_type() == 1
        self.action_buttons.set_processing_mode(True, is_live_camera_mode)
        self.collapse_config_panel()
        self.show_status_message(f"Procesando: {params['video_path_display']}...", 0)

        try:
            # Inicializar modelo y parámetros en el manager
            self.person_tracker.inicializar_modelo(str(params['model_path']))
            self.person_tracker.detector.set_confidence(params['confidence'])
            self.person_tracker.tracker.set_frames_espera(params['frames_espera'])

            cap, second_cap, main_out, mobile_out, total_frames = self._setup_video_io(params)
            # Cancelar si no se pudo abrir la cámara o el archivo de video
            if not cap:
                self.detener_procesamiento()
                return

            # Si es archivo y no hay salida (porque no tildó ningún checkbox), no tiene sentido procesar
            if not params['is_camera'] and not main_out and not mobile_out:
                self.show_status_message("Debe tildar al menos una salida para guardar video de archivo.", 4000)
                self.detener_procesamiento()
                return

            self._process_video_with_tracking(cap, second_cap, main_out, mobile_out, params, total_frames)            
            if cap:
                cap.release()
            if second_cap:
                second_cap.release()
            if main_out:
                main_out.release()

            if self.procesando:
                output_msg = f"Procesado. Guardado en: {params['output_path']}" if not params['is_camera'] else "Procesamiento en vivo finalizado."
                self.show_status_message(output_msg, 5000)
        except Exception as e:
            self.show_status_message(f"Error en procesamiento: {str(e)}", 5000)
            traceback.print_exc()
        finally:
            self.detener_procesamiento()

    def detener_procesamiento(self):
        """Detiene el procesamiento en curso."""
        self.procesando = False
        self.action_buttons.set_processing_mode(
            False, 
            self.input_widget.get_input_type() == 1
        )
        # Expandir el panel de configuración al detener el procesamiento
        self.expand_config_panel()
        self.show_status_message("Procesamiento detenido.", 3000)

    def _get_processing_parameters(self):
        """Obtiene los parámetros de procesamiento de la interfaz."""
        model_name = self.model_widget.get_model_path()
        confidence = self.model_widget.get_confidence()
        frames_espera = self.model_widget.get_frames_wait()
        output_path = self.output_widget.get_output_path()
        codec = self.output_widget.get_codec()
        is_camera = self.input_widget.get_input_type() == 1
        video_path_display = "Cámara en vivo"

        if is_camera:
            camera_id = self.input_widget.get_selected_camera_id()
            second_camera_id = self.input_widget.get_selected_second_camera_id()
            if camera_id is None:
                self.show_status_message("Error: Cámara principal no seleccionada.", 3000)
                return None
            video_path = camera_id
            video_path_display = self.input_widget.get_selected_camera_description()
        else:
            video_path = self.input_widget.get_video_path()
            if not video_path:
                self.show_status_message("Error: No video seleccionado.", 3000)
                return None
            video_path_display = Path(video_path).name

        models_dir = Path(__file__).parent.parent / "models"
        model_path = models_dir / model_name
        if not model_path.exists():
            model_path = Path(__file__).parent.parent / model_name
            if not model_path.exists():
                self.show_status_message(f"Error: Modelo {model_name} no encontrado.", 3000)
                return None        # Si estamos en modo cámara, guardar también la info de la segunda cámara
        result = {
            'video_path': video_path, 
            'is_camera': is_camera, 
            'model_path': model_path,
            'confidence': confidence, 
            'frames_espera': frames_espera,
            'output_path': output_path, 
            'codec': codec, 
            'video_path_display': video_path_display,
        }
        result['save_main'] = self.output_widget.should_save_main_camera()
        result['save_mobile'] = self.output_widget.should_save_mobile_camera()
        if is_camera:
            # Añadir info de la segunda cámara si está habilitada
            second_camera_id = self.input_widget.get_selected_second_camera_id()
            if second_camera_id is not None and second_camera_id != -1:
                result['second_camera_id'] = second_camera_id
                result['second_camera_display'] = self.input_widget.get_selected_second_camera_description()
        
        return result    
    # def _setup_video_io(self, params):
    #     """Configura la entrada y salida de video."""
    #     cap = None
    #     second_cap = None
    #     main_out = None
    #     mobile_out = None
    #     total_frames = 0
    #     try:
    #         if params['is_camera']:
    #             # Configuración de la cámara principal
    #             cap = cv2.VideoCapture(params['video_path'])
    #             if not cap.isOpened():
    #                 self.show_status_message(f"Error: No se pudo abrir la cámara ID {params['video_path']}", 3000)
    #                 return None, None, None, 0
                
    #             # Configuración de la segunda cámara si está disponible
    #             if 'second_camera_id' in params:
    #                 second_cap = cv2.VideoCapture(params['second_camera_id'])
    #                 if not second_cap.isOpened():
    #                     self.show_status_message(f"Advertencia: No se pudo abrir la segunda cámara ID {params['second_camera_id']}", 3000)
    #                     second_cap = None
                
    #             total_frames = -1  # Live camera
    #             total_frames = -1  # Live camera
    #         else:
    #             cap = cv2.VideoCapture(params['video_path'])
    #             if not cap.isOpened():
    #                 self.show_status_message(f"Error: No se pudo abrir video {params['video_path']}", 3000)
    #                 return None, None, 0
    #             total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    #         frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    #         frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    #         fps = cap.get(cv2.CAP_PROP_FPS)
    #         if fps <= 0:
    #             fps = 30.0

    #         ext = os.path.splitext(params['output_path'])[1]
    #         base_path = os.path.splitext(params['output_path'])[0]
    #         fourcc = cv2.VideoWriter_fourcc(*params['codec'])

    #         if params.get('save_main'):
    #             main_out_path = base_path + "_main" + ext
    #             main_out = cv2.VideoWriter(main_out_path, fourcc, fps, (frame_width, frame_height))

    #         if params.get('save_mobile'):
    #             mobile_out_path = base_path + "_mobile" + ext
    #             mobile_out = cv2.VideoWriter(mobile_out_path, fourcc, fps, (frame_width, frame_height))

    #         total_frames = -1 if params['is_camera'] else int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    #         return cap, second_cap, main_out, mobile_out, total_frames

    #     except Exception as e:
    #         self.show_status_message(f"Error en setup I/O: {str(e)}", 3000)
    #         if cap: cap.release()
    #         if second_cap: second_cap.release()
    #         if main_out: main_out.release()
    #         if mobile_out: mobile_out.release()
    #         return None, None, None, None, 0  

    def _setup_video_io(self, params):
        cap = None
        second_cap = None
        main_out = None
        mobile_out = None
        total_frames = 0
        try:
            cap = cv2.VideoCapture(params['video_path'])
            if not cap.isOpened():
                self.show_status_message(f"Error: No se pudo abrir {params['video_path']}", 3000)
                return None, None, None, None, 0

            if 'second_camera_id' in params:
                second_cap = cv2.VideoCapture(params['second_camera_id'])
                if not second_cap.isOpened():
                    self.show_status_message("Advertencia: No se pudo abrir la segunda cámara.", 3000)
                    second_cap = None

            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30.0

            ext = os.path.splitext(params['output_path'])[1]
            base_path = os.path.splitext(params['output_path'])[0]
            fourcc = cv2.VideoWriter_fourcc(*params['codec'])

            if params.get('save_main'):
                main_out_path = base_path + "_main" + ext
                main_out = cv2.VideoWriter(main_out_path, fourcc, fps, (frame_width, frame_height))

            if params.get('save_mobile'):
                mobile_out_path = base_path + "_mobile" + ext
                mobile_out = cv2.VideoWriter(mobile_out_path, fourcc, fps, (frame_width, frame_height))

            total_frames = -1 if params['is_camera'] else int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            return cap, second_cap, main_out, mobile_out, total_frames

        except Exception as e:
            self.show_status_message(f"Error en setup I/O: {str(e)}", 3000)
            if cap: cap.release()
            if second_cap: second_cap.release()
            if main_out: main_out.release()
            if mobile_out: mobile_out.release()
            return None, None, None, None, 0

    # def _process_video_with_tracking(self, cap, second_cap, main_out, mobile_out, params, total_frames):
    #     """Procesa el video frame por frame aplicando el tracking usando PersonTrackingManager."""
    #     primer_id, rastreo_id, ultima_coords, frames_perdidos = None, None, None, 0
    #     ids_globales = set()
    #     frame_count = 0
    #     controlar_servo = params['is_camera'] and self.serial_widget.is_serial_enabled()  # Solo si es cámara y está activo

    #     while self.procesando:
    #         # Leer frame de la cámara principal
    #         ret, frame = cap.read()
    #         if not ret:
    #             break
                
    #         # Leer frame de la segunda cámara si está disponible
    #         second_frame = None
    #         if second_cap:
    #             ret_second, second_frame = second_cap.read()
    #             if ret_second:
    #                 # Mostrar el segundo frame en la UI
    #                 if params['is_camera']:
    #                     self.video_display.display_second_frame(second_frame)
    #             else:
    #                 second_frame = None

    #         frame_count += 1
    #         if not params['is_camera'] and total_frames > 0:
    #             progress = int((frame_count / total_frames) * 100)
    #             self.show_status_message(f"Procesando: {progress}%", 0)
    #         elif params['is_camera'] and frame_count % 30 == 0:
    #             self.show_status_message(f"Frames procesados (en vivo): {frame_count}", 0)

    #         frame_width = frame.shape[1]
    #         result = self.person_tracker.detectar_personas(frame, params['confidence'])
    #         if result is None:
    #             # Si no hay detección, mostrar el frame original
    #             if params['is_camera']:
    #                 self.video_display.display_frame(frame)
                
    #             # Combinar frames para salida de video
    #             if second_frame is not None and main_out:
    #                 combined_frame = self._combine_frames(frame, second_frame)
    #                 main_out.write(combined_frame)
    #             elif main_out:
    #                 main_out.write(frame)
                    
    #             QApplication.processEvents()
    #             continue

    #         boxes = result.boxes
    #         ids_esta_frame = self.person_tracker.extraer_ids(boxes)
    #         primer_id, rastreo_id, reiniciar_coords, frames_perdidos = self.person_tracker.actualizar_rastreo(
    #             primer_id, rastreo_id, ids_esta_frame, frames_perdidos, params['frames_espera']
    #         )
    #         if reiniciar_coords:
    #             ultima_coords = None

    #         annotated_frame, ultima_coords = self.person_tracker.dibujar_anotaciones(
    #             result.plot(), boxes, rastreo_id, ultima_coords, ids_globales,
    #             frame_width, controlar_servo=controlar_servo
    #         )

    #         # Mostrar el frame anotado en la UI
    #         if self.video_display:
    #             self.video_display.display_frame(annotated_frame)
            
    #         # Preparar y guardar el frame combinado con ambas cámaras
    #         if main_out:
    #             if second_frame is not None:
    #                 combined_frame = self._combine_frames(annotated_frame, second_frame)
    #                 main_out.write(combined_frame)
    #             else:
    #                 main_out.write(annotated_frame)

    #         if mobile_out and ultima_coords:
    #             x1, y1, x2, y2 = map(int, ultima_coords)
    #             h, w = frame.shape[:2]
    #             x1 = max(0, x1); y1 = max(0, y1)
    #             x2 = min(w, x2); y2 = min(h, y2)
    #             if x2 > x1 and y2 > y1:
    #                 zoom_frame = frame[y1:y2, x1:x2]
    #                 zoom_frame = cv2.resize(zoom_frame, (w, h))
    #                 mobile_out.write(zoom_frame)        
    #         QApplication.processEvents()

    #     if main_out:
    #         main_out.release()
    #     if mobile_out:
    #         mobile_out.release()

    def _process_video_with_tracking(self, cap, second_cap, main_out, mobile_out, params, total_frames):
        """Procesa el video frame por frame aplicando el tracking usando PersonTrackingManager."""
        primer_id, rastreo_id, ultima_coords, frames_perdidos = None, None, None, 0
        ids_globales = set()
        frame_count = 0
        controlar_servo = params['is_camera'] and self.serial_widget.is_serial_enabled()

        while self.procesando:
            ret, frame = cap.read()
            if not ret:
                break

            second_frame = None
            if second_cap:
                ret_second, second_frame = second_cap.read()
                if ret_second:
                    self.video_display.display_second_frame(second_frame)
                else:
                    second_frame = None

            frame_count += 1
            if not params['is_camera'] and total_frames > 0:
                progress = int((frame_count / total_frames) * 100)
                self.show_status_message(f"Procesando: {progress}%", 0)
            elif params['is_camera'] and frame_count % 30 == 0:
                self.show_status_message(f"Frames procesados (en vivo): {frame_count}", 0)

            frame_width = frame.shape[1]
            result = self.person_tracker.detectar_personas(frame, params['confidence'])
            if result is None:
                if params['is_camera']:
                    self.video_display.display_frame(frame)

                if main_out:
                    main_out.write(frame)
                QApplication.processEvents()
                continue

            boxes = result.boxes
            ids_esta_frame = self.person_tracker.extraer_ids(boxes)

            primer_id, rastreo_id, reiniciar_coords, frames_perdidos = self.person_tracker.actualizar_rastreo(
                primer_id, rastreo_id, ids_esta_frame, frames_perdidos, params['frames_espera']
            )
            if reiniciar_coords:
                ultima_coords = None

            annotated_frame, ultima_coords = self.person_tracker.dibujar_anotaciones(
                result.plot(), boxes, rastreo_id, ultima_coords, ids_globales,
                frame_width, controlar_servo=controlar_servo
            )

            self.video_display.display_frame(annotated_frame)

            if main_out:
                main_out.write(annotated_frame)

            if mobile_out and ultima_coords:
                x1, y1, x2, y2 = map(int, ultima_coords)
                h, w = frame.shape[:2]
                x1 = max(0, x1); y1 = max(0, y1)
                x2 = min(w, x2); y2 = min(h, y2)
                if x2 > x1 and y2 > y1:
                    zoom_frame = frame[y1:y2, x1:x2]
                    zoom_frame = cv2.resize(zoom_frame, (w, h))
                    mobile_out.write(zoom_frame)

            QApplication.processEvents()

        if main_out:
            main_out.release()
        if mobile_out:
            mobile_out.release()


    def _combine_frames(self, main_frame, second_frame):
        """
        Combina dos frames en uno solo con proporción 3/4 para el principal y 1/4 para el secundario.
        
        Args:
            main_frame: El frame de la cámara principal
            second_frame: El frame de la cámara secundaria (móvil)
            
        Returns:
            combined_frame: Un único frame combinando ambos
        """
        if main_frame is None:
            return None
            
        if second_frame is None:
            return main_frame  # Si no hay segundo frame, devolver solo el principal
            
        # Obtener dimensiones del frame principal
        h, w = main_frame.shape[:2]
        
        # Calcular el ancho que ocupará el frame secundario (1/4 del total)
        second_width = w // 4
        
        # Redimensionar el frame secundario para que ocupe 1/4 del ancho y la misma altura
        second_frame_resized = cv2.resize(second_frame, (second_width, h))
        
        # Crear un nuevo frame combinando ambos (3/4 para principal, 1/4 para secundario)
        combined_frame = np.zeros((h, w, 3), dtype=np.uint8)
        combined_frame[:, :w-second_width, :] = main_frame[:, :w-second_width, :]
        combined_frame[:, w-second_width:, :] = second_frame_resized
        
        # Dibujar una línea separadora
        cv2.line(combined_frame, (w-second_width, 0), (w-second_width, h), (255, 255, 255), 1)
        
        return combined_frame

    def toggle_config_panel(self):
        """Alterna entre panel colapsado y expandido."""
        if hasattr(self.config_panel, "width") and self.config_panel.width() > 50:  # Si está expandido
            self.collapse_config_panel()
            # Guardar estado en configuración
            settings.config_panel_collapsed = True
            settings.save_settings()
        else:  # Si está colapsado
            self.expand_config_panel()
            # Guardar estado en configuración
            settings.config_panel_collapsed = False
            settings.save_settings()
    
    def collapse_config_panel(self):
        """Colapsa el panel de configuración hacia la izquierda."""
        # Guardar el ancho actual para poder restaurarlo después
        if self.config_panel.width() > 0 : 
            self.config_panel_width = self.config_panel.width()
        
        # Crear una animación para colapsar suavemente
        self.animation = QPropertyAnimation(self.config_panel, b"maximumWidth")
        self.animation.setDuration(300)  # 300ms para la animación
        self.animation.setStartValue(self.config_panel.width())
        self.animation.setEndValue(0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        # Visibilidad de boton stop a partir de si se esta procesando o no
        if self.procesando:
            self.new_stop_button_main.show()
            self.new_stop_button_main.setEnabled(True)
        else:
            self.new_stop_button_main.hide()
            self.new_stop_button_main.setEnabled(False)
            
        self.animation.start()
        
        # Crear un botón para expandir el panel
        if not hasattr(self, 'expand_button'):
            self.expand_button = QPushButton(">")
            self.expand_button.setFixedSize(20, 60)
            self.expand_button.clicked.connect(self.expand_config_panel)
            self.expand_button.setToolTip("Expandir panel (Ctrl+B)")
            self.expand_button.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    border: 1px solid #ccc;
                    border-left: none;
                    border-top-right-radius: 10px;
                    border-bottom-right-radius: 10px;
                }
                QPushButton:hover { background-color: #e0e0e0; }
            """)
            
        # Añadir el botón al layout principal, alineado a la izquierda y centrado verticalmente
        self.content_layout.insertWidget(0, self.expand_button, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.expand_button.show()

    def expand_config_panel(self):
        """Expande el panel de configuración."""
        # Usar getattr para un acceso seguro a config_panel_width, default de 300
        target_expanded_width = getattr(self, 'config_panel_width', 300)
        if target_expanded_width <= 0:
            target_expanded_width = 300

        # Animar la expansión
        self.animation = QPropertyAnimation(self.config_panel, b"maximumWidth")
        self.animation.setDuration(300)
        # Iniciar animacion desde el maximo ancho
        self.animation.setStartValue(self.config_panel.maximumWidth())
        self.animation.setEndValue(target_expanded_width)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.animation.start()
        
        # Ocultar el botón de expansión
        if hasattr(self, 'expand_button'):
            self.expand_button.hide()
        
        # Esconder el boton cuando se expande el panel
        if hasattr(self, 'new_stop_button_main'):
            self.new_stop_button_main.hide()
            self.new_stop_button_main.setEnabled(False)

    def closeEvent(self, event):
        """Maneja el evento de cierre de la ventana."""
        self.input_widget.detener_previsualizacion()
        self.input_widget.detener_segunda_previsualizacion() # Detener también la segunda cámara
        self.detener_procesamiento()
        super().closeEvent(event)

    def resizeEvent(self, event):
        """Maneja eventos de cambio de tamaño de la ventana."""
        super().resizeEvent(event)
        
        # Si la ventana se hace demasiado estrecha, colapsar automáticamente el panel
        if self.width() < 900 and not hasattr(self, 'auto_collapsed') and not self.procesando:
            self.collapse_config_panel()
            self.auto_collapsed = True
        elif self.width() >= 900 and hasattr(self, 'auto_collapsed') and not self.procesando:
            self.expand_config_panel()
            delattr(self, 'auto_collapsed')