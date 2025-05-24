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
            self.config_panel_collapsed = False # Add this
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

        # Initialize header buttons for processing state
        self.new_stop_button_main = None
        self.new_process_button_main = None

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

        # Boton verde de procesar (inicialmente oculto)
        self.new_process_button_main = QPushButton("Procesar") #
        self.new_process_button_main.setMinimumHeight(40) #
        self.new_process_button_main.setStyleSheet("background-color: green; color: white;") #
        self.new_process_button_main.clicked.connect(self.process_video) #
        self.new_process_button_main.hide() #
        header_layout.addWidget(self.new_process_button_main) #

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

        self.manual_collapse_button = QPushButton("⇦")
        self.manual_collapse_button.setFixedSize(30, 30)
        self.manual_collapse_button.setToolTip("Colapsar panel")
        self.manual_collapse_button.clicked.connect(self.collapse_config_panel)
        # Añadirlo arriba del todo del panel izquierdo
        config_layout.insertWidget(0, self.manual_collapse_button, alignment=Qt.AlignmentFlag.AlignRight)

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

        # If panel is collapsed, update the header process button state
        if hasattr(self, 'config_panel') and self.config_panel.maximumWidth() == 0 and \
           hasattr(self, 'new_process_button_main') and self.new_process_button_main:
            if not self.procesando:
                self.new_process_button_main.setEnabled(self.action_buttons.process_button.isEnabled())
                self.new_process_button_main.setText(self.action_buttons.process_button.text())


    def on_video_file_selected(self, file_path):
        """Maneja la selección de un archivo de video."""
        if file_path and self.input_widget.get_input_type() == 0:  # Si es tipo archivo
            self.action_buttons.enable_process_button(True)
            self.video_display.display_second_frame(None) # Limpiar la segunda vista previa si se cambia a video

            # If panel is collapsed, update the header process button state
            if hasattr(self, 'config_panel') and self.config_panel.maximumWidth() == 0 and \
               hasattr(self, 'new_process_button_main') and self.new_process_button_main:
                if not self.procesando:
                    self.new_process_button_main.setEnabled(self.action_buttons.process_button.isEnabled())
                    self.new_process_button_main.setText(self.action_buttons.process_button.text())


    def on_main_camera_selected(self, camera_id, camera_description):
        """Maneja la selección de la cámara principal."""
        self.show_status_message(f"Cámara principal seleccionada: {camera_description}", 2000)

    def on_second_camera_selected(self, camera_id, camera_description):
        """Maneja la selección de la segunda cámara."""
        if camera_id != -1:
            self.show_status_message(f"Segunda cámara seleccionada: {camera_description}", 2000)
        else:
            self.show_status_message("Segunda cámara deshabilitada.", 2000)
            self.video_display.display_second_frame(None)

    def show_status_message(self, message, timeout=0):
        """Muestra un mensaje en la barra de estado."""
        self.status_bar.showMessage(message, timeout)

    def load_settings_to_ui(self):
        """Carga la configuración guardada en la interfaz."""
        settings.load_settings()

        self.input_widget.set_all_settings({
            "input_type": getattr(settings, 'input_type', 0),
            "video_path": getattr(settings, 'video_path', None),
            "camera_id": getattr(settings, 'camera_id', 0),
            "second_camera_id": getattr(settings, 'second_camera_id', -1)
        })

        self.model_widget.set_model_path(settings.model_path)
        self.model_widget.set_confidence(settings.confidence_threshold)
        self.model_widget.set_frames_wait(settings.frames_espera)

        self.output_widget.set_output_path(settings.output_path)
        self.output_widget.set_codec(settings.output_format)

        self.serial_widget.set_serial_port(settings.serial_port)
        self.serial_widget.set_baudrate(settings.serial_baudrate)
        self.serial_widget.set_serial_enabled(settings.serial_enabled)

        QTimer.singleShot(100, self._apply_panel_state)

    def _apply_panel_state(self):
        """Aplica el estado guardado del panel de configuración."""
        if not hasattr(self, 'config_panel_width') or self.config_panel_width <= 0:
            if hasattr(self, 'config_panel') and self.config_panel.width() > 0:
                self.config_panel_width = self.config_panel.width()
            else:
                self.config_panel_width = 300

        if hasattr(settings, 'config_panel_collapsed') and settings.config_panel_collapsed: # Check attribute exists
            if self.config_panel.maximumWidth() > 0 : # Check if not already collapsed by animation
                 self.collapse_config_panel()
            else: # Already collapsed (width is 0 or very small)
                self.config_panel.setMaximumWidth(0)
                if hasattr(self, 'expand_button'):
                    self.expand_button.show()
                # Ensure correct header buttons are shown if starting collapsed
                if self.procesando:
                    if self.new_stop_button_main: self.new_stop_button_main.show()
                    if self.new_process_button_main: self.new_process_button_main.hide()
                else:
                    if self.new_stop_button_main: self.new_stop_button_main.hide()
                    if self.new_process_button_main:
                        self.new_process_button_main.show()
                        self.new_process_button_main.setEnabled(self.action_buttons.process_button.isEnabled())
                        self.new_process_button_main.setText(self.action_buttons.process_button.text())

        else: # Not collapsed or attribute doesn't exist
            if self.config_panel.maximumWidth() == 0: # Check if it was collapsed
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

        if hasattr(self, 'config_panel'):
            settings.config_panel_collapsed = self.config_panel.maximumWidth() == 0 # More robust check

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
        self.action_buttons.set_processing_mode(True, is_live_camera_mode) #

        # Ensure panel is collapsed and header buttons are updated
        if self.config_panel.maximumWidth() > 0 : # If not already collapsed
            self.collapse_config_panel() # This will show stop, hide process in header
        else: # Already collapsed, ensure buttons are correct
            if self.new_stop_button_main: self.new_stop_button_main.show()
            if self.new_process_button_main: self.new_process_button_main.hide()


        self.show_status_message(f"Procesando: {params['video_path_display']}...", 0)

        try:
            self.person_tracker.inicializar_modelo(str(params['model_path']))
            self.person_tracker.detector.set_confidence(params['confidence'])
            self.person_tracker.tracker.set_frames_espera(params['frames_espera'])

            cap, second_cap, main_out, mobile_out, total_frames = self._setup_video_io(params)
            if not cap:
                self.detener_procesamiento()
                return

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

            if self.procesando: # If not stopped by user
                output_msg = f"Procesado. Guardado en: {params['output_path']}" if not params['is_camera'] else "Procesamiento en vivo finalizado."
                self.show_status_message(output_msg, 5000)
        except Exception as e:
            self.show_status_message(f"Error en procesamiento: {str(e)}", 5000)
            traceback.print_exc()
        finally:
            # Ensure we always call detener_procesamiento unless it was already stopped
            if self.procesando: # Check if still in processing state
                 self.detener_procesamiento()


    def detener_procesamiento(self):
        """Detiene el procesamiento en curso."""
        if not self.procesando and not (self.new_stop_button_main and self.new_stop_button_main.isVisible()):
             # If not processing and stop button not visible, nothing to do from stop perspective
             # but still ensure panel and action buttons are in non-processing state
             if not self.action_buttons.process_button.isEnabled(): # If action buttons are in processing state
                self.action_buttons.set_processing_mode(
                    False,
                    self.input_widget.get_input_type() == 1
                )
             if self.config_panel.maximumWidth() == 0: # If panel is collapsed
                 # Update header buttons for non-processing state
                 if self.new_stop_button_main: self.new_stop_button_main.hide()
                 if self.new_process_button_main:
                     self.new_process_button_main.show()
                     self.new_process_button_main.setEnabled(self.action_buttons.process_button.isEnabled())
                     self.new_process_button_main.setText(self.action_buttons.process_button.text())
             else: # If panel is expanded
                 if not (hasattr(self, 'auto_collapsed') and self.auto_collapsed): # Avoid expanding if auto-collapsed due to resize
                    self.expand_config_panel() # This will also hide header buttons
             return


        was_processing = self.procesando
        self.procesando = False
        self.action_buttons.set_processing_mode(
            False,
            self.input_widget.get_input_type() == 1
        )

        # Expand panel or update header buttons if already collapsed
        if self.config_panel.maximumWidth() == 0: # If panel is collapsed
            if self.new_stop_button_main: self.new_stop_button_main.hide()
            if self.new_process_button_main:
                self.new_process_button_main.show()
                self.new_process_button_main.setEnabled(self.action_buttons.process_button.isEnabled())
                self.new_process_button_main.setText(self.action_buttons.process_button.text())
        else: # If panel is expanded or was just expanded
            if not (hasattr(self, 'auto_collapsed') and self.auto_collapsed): # Avoid expanding if auto-collapsed due to resize
                self.expand_config_panel() # This will hide header buttons
            else: # Auto collapsed, just update header buttons
                if self.new_stop_button_main: self.new_stop_button_main.hide()
                if self.new_process_button_main:
                    self.new_process_button_main.show()
                    self.new_process_button_main.setEnabled(self.action_buttons.process_button.isEnabled())
                    self.new_process_button_main.setText(self.action_buttons.process_button.text())


        if was_processing:
            self.show_status_message("Procesamiento detenido.", 3000)
        else:
            # If called when not processing (e.g. from closeEvent or error), ensure clean state
            self.show_status_message("Listo.", 3000)


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
            if camera_id is None: # Strict check for None if get_selected_camera_id can return it
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
            # Check in the parent of 'core' as a fallback if 'models' is sibling to 'main_window_refactored.py' parent
            model_path_alt_heuristic = Path(__file__).resolve().parent.parent / "models" / model_name
            if model_path_alt_heuristic.exists():
                model_path = model_path_alt_heuristic
            else:
                # Final fallback: assume model_name might be a direct path or in root of project (parent of parent of current file)
                model_path_root_heuristic = Path(__file__).resolve().parent.parent.parent / model_name
                if model_path_root_heuristic.exists():
                     model_path = model_path_root_heuristic
                else: # Original behavior if not found in primary or heuristic paths
                    model_path_original_check = Path(__file__).parent.parent / model_name # This was the second check in original
                    if model_path_original_check.exists():
                        model_path = model_path_original_check
                    else:
                        self.show_status_message(f"Error: Modelo {model_name} no encontrado en {models_dir}, {model_path_alt_heuristic.parent} ni {model_path_root_heuristic.parent}.", 3000)
                        return None
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
            second_camera_id = self.input_widget.get_selected_second_camera_id()
            if second_camera_id is not None and second_camera_id != -1: # Check for None explicitly
                result['second_camera_id'] = second_camera_id
                result['second_camera_display'] = self.input_widget.get_selected_second_camera_description()

        return result

    def _setup_video_io(self, params):
        cap = None
        second_cap = None
        main_out = None
        mobile_out = None
        total_frames = 0
        try:
            # Ensure video_path for camera is int
            video_path_cv = int(params['video_path']) if params['is_camera'] else params['video_path']
            cap = cv2.VideoCapture(video_path_cv) #
            if not cap.isOpened():
                self.show_status_message(f"Error: No se pudo abrir {params['video_path_display']}", 3000)
                return None, None, None, None, 0

            if 'second_camera_id' in params and params['second_camera_id'] is not None:
                second_video_path_cv = int(params['second_camera_id']) #
                second_cap = cv2.VideoCapture(second_video_path_cv)
                if not second_cap.isOpened():
                    self.show_status_message(f"Advertencia: No se pudo abrir la segunda cámara {params.get('second_camera_display', '')}.", 3000)
                    second_cap = None

            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30.0

            # Ensure output path directory exists
            output_dir = Path(params['output_path']).parent
            output_dir.mkdir(parents=True, exist_ok=True)

            ext = os.path.splitext(params['output_path'])[1]
            base_path = os.path.splitext(params['output_path'])[0]
            fourcc = cv2.VideoWriter_fourcc(*params['codec'])

            if params.get('save_main'):
                main_out_path = base_path + "_main" + ext
                main_out = cv2.VideoWriter(main_out_path, fourcc, fps, (frame_width, frame_height))
                if not main_out.isOpened():
                    self.show_status_message(f"Error: No se pudo crear archivo de salida principal en {main_out_path}", 3000)
                    main_out = None # Ensure it's None if not opened

            if params.get('save_mobile'):
                # Determine dimensions for mobile_out (from second_cap if available, else main_cap)
                mobile_frame_width, mobile_frame_height = frame_width, frame_height # Default to main cam dims
                if second_cap and second_cap.isOpened():
                    mobile_frame_width = int(second_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    mobile_frame_height = int(second_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                mobile_out_path = base_path + "_mobile" + ext
                mobile_out = cv2.VideoWriter(mobile_out_path, fourcc, fps, (mobile_frame_width, mobile_frame_height))
                if not mobile_out.isOpened():
                    self.show_status_message(f"Error: No se pudo crear archivo de salida móvil en {mobile_out_path}", 3000)
                    mobile_out = None # Ensure it's None if not opened


            total_frames = -1 if params['is_camera'] else int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            return cap, second_cap, main_out, mobile_out, total_frames

        except Exception as e:
            self.show_status_message(f"Error en setup I/O: {str(e)}", 3000)
            traceback.print_exc()
            if cap: cap.release()
            if second_cap: second_cap.release()
            if main_out: main_out.release()
            if mobile_out: mobile_out.release()
            return None, None, None, None, 0

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

            second_frame_for_processing = None # This will hold the frame to be saved by mobile_out
            second_frame_for_display = None # This is for live display

            if second_cap and second_cap.isOpened():
                ret_second, temp_second_frame = second_cap.read()
                if ret_second:
                    second_frame_for_processing = temp_second_frame.copy() # Use a copy for processing/saving
                    second_frame_for_display = temp_second_frame # Use original for display
                    if params['is_camera']: # Only display live if in camera mode
                        self.video_display.display_second_frame(second_frame_for_display)
                # else: second_frame_for_processing remains None

            frame_count += 1
            if not params['is_camera'] and total_frames > 0:
                progress = int((frame_count / total_frames) * 100)
                self.show_status_message(f"Procesando: {progress}%", 0)
            elif params['is_camera'] and frame_count % 30 == 0: # Update every 30 frames for live
                self.show_status_message(f"Frames procesados (en vivo): {frame_count}", 0)

            # Process main camera frame
            frame_width = frame.shape[1]
            result = self.person_tracker.detectar_personas(frame, params['confidence'])

            annotated_frame = frame # Default to original frame if no detection
            if result and result.boxes: # Check if result and boxes are not None and not empty
                boxes = result.boxes
                ids_esta_frame = self.person_tracker.extraer_ids(boxes)

                primer_id, rastreo_id, reiniciar_coords, frames_perdidos = self.person_tracker.actualizar_rastreo(
                    primer_id, rastreo_id, ids_esta_frame, frames_perdidos, params['frames_espera']
                )
                if reiniciar_coords:
                    ultima_coords = None

                # Use result.plot() which returns the annotated frame directly
                annotated_frame_from_plot, ultima_coords = self.person_tracker.dibujar_anotaciones(
                    result.plot(), boxes, rastreo_id, ultima_coords, ids_globales,
                    frame_width, controlar_servo=controlar_servo
                )
                if annotated_frame_from_plot is not None:
                    annotated_frame = annotated_frame_from_plot

            # Display main (potentially annotated) frame
            self.video_display.display_frame(annotated_frame)

            # Save frames to video files
            if main_out and params.get('save_main'):
                main_out.write(annotated_frame)

            if mobile_out and params.get('save_mobile'):
                if second_frame_for_processing is not None:
                    mobile_out.write(second_frame_for_processing)
                elif not params['is_camera'] and params.get('save_main') : # If not live and main is saved, and no second cam, mobile saves main
                     # This case might be undesirable - mobile should ideally be from a second source
                     # For now, let's only write if second_frame_for_processing is available.
                     pass

            QApplication.processEvents()

        # Release video writers outside the loop
        if main_out:
            main_out.release()
        if mobile_out:
            mobile_out.release()


    def _combine_frames(self, main_frame, second_frame):
        """
        Combina dos frames en uno solo con proporción 3/4 para el principal y 1/4 para el secundario.
        DEPRECATED if VideoDisplayWidget handles separate displays. Kept for potential direct use.
        """
        if main_frame is None:
            return None

        if second_frame is None:
            return main_frame

        h, w = main_frame.shape[:2]
        second_width = w // 4

        try:
            second_frame_resized = cv2.resize(second_frame, (second_width, h))
            combined_frame = np.zeros((h, w, 3), dtype=np.uint8) # Assume color
            main_frame_width_portion = w - second_width

            # Ensure main_frame is also correctly sliced if it's not 3 channels
            if main_frame.ndim == 2: # Grayscale
                main_frame = cv2.cvtColor(main_frame, cv2.COLOR_GRAY2BGR)
            if second_frame_resized.ndim == 2:
                 second_frame_resized = cv2.cvtColor(second_frame_resized, cv2.COLOR_GRAY2BGR)


            combined_frame[:, :main_frame_width_portion] = main_frame[:, :main_frame_width_portion]
            combined_frame[:, main_frame_width_portion:] = second_frame_resized

            cv2.line(combined_frame, (main_frame_width_portion, 0), (main_frame_width_portion, h), (255, 255, 255), 1)
        except cv2.error as e:
            print(f"OpenCV error in _combine_frames: {e}")
            return main_frame # Fallback to main_frame
        except Exception as e:
            print(f"Error in _combine_frames: {e}")
            return main_frame # Fallback

        return combined_frame

    def toggle_config_panel(self):
        """Alterna entre panel colapsado y expandido."""
        # Use maximumWidth as the indicator for collapsed state due to animation target
        if self.config_panel.maximumWidth() > 0 and self.config_panel.isVisible() :  # If expanded or visible and not fully collapsed
            self.collapse_config_panel()
            if hasattr(settings, 'save_settings'): # Check if dummy or real settings
                settings.config_panel_collapsed = True
                settings.save_settings()
        else:  # If collapsed
            self.expand_config_panel()
            if hasattr(settings, 'save_settings'):
                settings.config_panel_collapsed = False
                settings.save_settings()

    def collapse_config_panel(self):
        """Colapsa el panel de configuración hacia la izquierda."""
        if self.config_panel.maximumWidth() == 0: # Already collapsed
            # Ensure correct header buttons
            if self.procesando:
                if self.new_stop_button_main: self.new_stop_button_main.show()
                if self.new_process_button_main: self.new_process_button_main.hide()
            else:
                if self.new_stop_button_main: self.new_stop_button_main.hide()
                if self.new_process_button_main:
                    self.new_process_button_main.show()
                    self.new_process_button_main.setEnabled(self.action_buttons.process_button.isEnabled())
                    self.new_process_button_main.setText(self.action_buttons.process_button.text())
            if hasattr(self, 'expand_button') and self.expand_button: self.expand_button.show() # Ensure expand button is visible
            return

        current_width = self.config_panel.width()
        if current_width > 0 and current_width > self.config_panel_width / 2 : # Only save if it's a reasonable expanded width
            self.config_panel_width = current_width

        self.animation = QPropertyAnimation(self.config_panel, b"maximumWidth")
        self.animation.setDuration(300)
        self.animation.setStartValue(current_width if current_width >0 else self.config_panel_width)
        self.animation.setEndValue(0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        # Update header buttons based on processing state
        if self.procesando:
            if self.new_stop_button_main: # Check existence
                self.new_stop_button_main.show()
                self.new_stop_button_main.setEnabled(True)
            if self.new_process_button_main: # Check existence
                self.new_process_button_main.hide()
        else: # Not processing
            if self.new_stop_button_main: # Check existence
                self.new_stop_button_main.hide()
            if self.new_process_button_main: # Check existence
                self.new_process_button_main.show() #
                # Sync with action_buttons' process button state
                self.new_process_button_main.setEnabled(self.action_buttons.process_button.isEnabled()) #
                self.new_process_button_main.setText(self.action_buttons.process_button.text()) #

        self.animation.start()

        if not hasattr(self, 'expand_button') or not self.expand_button: # Ensure expand_button is created if not exists
            self.expand_button = QPushButton(">")
            self.expand_button.setFixedSize(20, 60)
            self.expand_button.clicked.connect(self.expand_config_panel)
            self.expand_button.setToolTip("Expandir panel (Ctrl+B)")
            self.expand_button.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0; border: 1px solid #ccc; border-left: none;
                    border-top-right-radius: 10px; border-bottom-right-radius: 10px;
                }
                QPushButton:hover { background-color: #e0e0e0; }
            """)
            # Add to layout if it's the first time
            self.content_layout.insertWidget(0, self.expand_button, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.expand_button.show()


    def expand_config_panel(self):
        """Expande el panel de configuración."""
        if self.config_panel.maximumWidth() > 0 and self.config_panel.maximumWidth() >= self.config_panel_width: # Already expanded
            # Ensure header buttons are hidden when panel is expanded
            if self.new_stop_button_main: self.new_stop_button_main.hide()
            if self.new_process_button_main: self.new_process_button_main.hide()
            if hasattr(self, 'expand_button') and self.expand_button: self.expand_button.hide() # Ensure expand button is hidden
            return

        target_expanded_width = getattr(self, 'config_panel_width', 300)
        if target_expanded_width <= 0: # Fallback if somehow it's zero
            target_expanded_width = 300

        self.animation = QPropertyAnimation(self.config_panel, b"maximumWidth")
        self.animation.setDuration(300)
        self.animation.setStartValue(self.config_panel.maximumWidth()) # Start from current max width (likely 0)
        self.animation.setEndValue(target_expanded_width)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.animation.start()

        if hasattr(self, 'expand_button') and self.expand_button: # Check existence
            self.expand_button.hide()

        # Hide header stop and process buttons when panel is expanded
        if hasattr(self, 'new_stop_button_main') and self.new_stop_button_main: # Check existence
            self.new_stop_button_main.hide() #
        if hasattr(self, 'new_process_button_main') and self.new_process_button_main: # Check existence
            self.new_process_button_main.hide() #


    def closeEvent(self, event):
        """Maneja el evento de cierre de la ventana."""
        self.input_widget.detener_previsualizacion()
        self.input_widget.detener_segunda_previsualizacion()
        if self.procesando: # If processing, stop it first
            self.detener_procesamiento()
        super().closeEvent(event)

    def resizeEvent(self, event):
        """Maneja eventos de cambio de tamaño de la ventana."""
        super().resizeEvent(event)

        # Check if config_panel exists before trying to access its width
        if not hasattr(self, 'config_panel'):
            return

        # If the window becomes too narrow, and panel is not already auto-collapsed, and not processing
        if self.width() < 900 and not hasattr(self, 'auto_collapsed') and not self.procesando:
            if self.config_panel.maximumWidth() > 0 : # Only collapse if it's currently expanded
                self.collapse_config_panel()
                self.auto_collapsed = True
        # If window is wider, and panel was auto-collapsed, and not processing
        elif self.width() >= 900 and hasattr(self, 'auto_collapsed') and self.auto_collapsed and not self.procesando:
            if self.config_panel.maximumWidth() == 0: # Only expand if it's currently collapsed
                self.expand_config_panel()
            delattr(self, 'auto_collapsed')