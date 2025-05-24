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
import logging # Added

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStatusBar, QApplication, QPushButton
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QThread, pyqtSignal, QObject # Added QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

from ui.widgets.input_config_widget import InputConfigWidget
from ui.widgets.model_config_widget import ModelConfigWidget
from ui.widgets.output_config_widget import OutputConfigWidget
from ui.widgets.serial_config_widget import SerialConfigWidget
from ui.widgets.video_display_widget import VideoDisplayWidget
from ui.widgets.action_buttons_widget import ActionButtonsWidget

from core.serial_manager import serial_manager
from core.person_tracking_manager import PersonTrackingManager # Assumed to exist

# --- Dummy classes for missing imports (as in original) ---
try:
    from config.settings import settings
    from core.video_output import VideoOutputManager # This is actually provided now
except ImportError:
    logger.warning("Warning: Could not import 'settings'. Using DummySettings.")
    class DummySettings:
        def __init__(self):
            self.model_path = "yolov8n.pt"; self.confidence_threshold = 0.6; self.frames_espera = 10
            self.output_path = "salida_principal.avi"; self.output_format = "XVID"; self.save_main_camera = True
            self.save_mobile_camera = False; self.mobile_output_path = "salida_movil.avi"
            self.serial_port = "COM3"; self.serial_baudrate = 115200; self.serial_enabled = True
            self.config_panel_collapsed = False; self.input_type = 0; self.video_path = None
            self.camera_id = 0; self.second_camera_id = -1
        def save_settings(self): logger.info("DummySettings: save_settings called"); return True
        def load_settings(self): logger.info("DummySettings: load_settings called")
    settings = DummySettings()
    # VideoOutputManager is provided, so DummyVideoOutputManager might not be needed if path is correct.
    # If core.video_output is truly missing, this dummy would be used.
    if 'VideoOutputManager' not in sys.modules: # Check if it was actually imported
        logger.warning("Using DummyVideoOutputManager because core.video_output might be missing from expected path.")
        class DummyVideoOutputManager:
            def setup_output(self, *args, **kwargs): logger.info("DummyVOM: setup_output"); return True
            def write_frame(self, *args, **kwargs): logger.info("DummyVOM: write_frame"); return True
            def release(self, *args, **kwargs): logger.info("DummyVOM: release"); return True
            def get_output_info(self, *args, **kwargs): logger.info("DummyVOM: get_output_info"); return {}
        VideoOutputManager = DummyVideoOutputManager


# --- Video Processing Thread ---
class VideoProcessingThread(QThread):
    # Signals:
    # processed_frame: main_annotated_frame, second_display_frame (can be None)
    # progress_update: current_frame_count, total_frames (or -1 for live), status_text
    # processing_finished: message (str)
    # error_occurred: error_message (str)
    processed_frame = pyqtSignal(object, object)
    progress_update = pyqtSignal(int, int, str)
    processing_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, processing_params, person_tracker, serial_widget_ref, parent=None):
        super().__init__(parent)
        self.params = processing_params
        self.person_tracker = person_tracker # Reference to the existing manager
        self.serial_widget = serial_widget_ref # To check if serial is enabled for servo
        self.running = False
        self.cap_main = None
        self.cap_second = None
        self.out_main = None
        self.out_mobile = None

    def _setup_io_in_thread(self):
        try:
            # Main Source
            video_path_cv = int(self.params['video_path']) if self.params['is_camera'] else str(self.params['video_path'])
            self.cap_main = cv2.VideoCapture(video_path_cv)
            if not self.cap_main.isOpened():
                raise IOError(f"Error: No se pudo abrir fuente principal {self.params['video_path_display']}")

            main_width = int(self.cap_main.get(cv2.CAP_PROP_FRAME_WIDTH))
            main_height = int(self.cap_main.get(cv2.CAP_PROP_FRAME_HEIGHT))
            main_fps = self.cap_main.get(cv2.CAP_PROP_FPS)
            if main_fps <= 0: main_fps = 30.0 # Default

            # Secondary Source (if applicable)
            if 'second_camera_id' in self.params and self.params['second_camera_id'] is not None:
                second_video_path_cv = int(self.params['second_camera_id'])
                self.cap_second = cv2.VideoCapture(second_video_path_cv)
                if not self.cap_second.isOpened():
                    logger.warning(f"Advertencia: No se pudo abrir la segunda cámara {self.params.get('second_camera_display', '')}.")
                    self.cap_second = None # Ensure it's None if not opened

            # Main Output Writer
            if self.params.get('save_main') and self.params.get('output_path'):
                main_output_dir = Path(self.params['output_path']).parent
                main_output_dir.mkdir(parents=True, exist_ok=True)
                main_fourcc = cv2.VideoWriter_fourcc(*self.params['codec'])
                self.out_main = cv2.VideoWriter(str(self.params['output_path']), main_fourcc, main_fps, (main_width, main_height))
                if not self.out_main.isOpened():
                    logger.error(f"Error al crear archivo principal en {self.params['output_path']}")
                    self.out_main = None # Ensure it's None

            # Mobile Output Writer
            if self.params.get('save_mobile') and self.params.get('mobile_output_path') and self.cap_second:
                mobile_output_dir = Path(self.params['mobile_output_path']).parent
                mobile_output_dir.mkdir(parents=True, exist_ok=True)
                mobile_fourcc = cv2.VideoWriter_fourcc(*self.params['mobile_codec'])

                mobile_width = int(self.cap_second.get(cv2.CAP_PROP_FRAME_WIDTH))
                mobile_height = int(self.cap_second.get(cv2.CAP_PROP_FRAME_HEIGHT))
                mobile_fps_cam = self.cap_second.get(cv2.CAP_PROP_FPS)
                mobile_fps = mobile_fps_cam if mobile_fps_cam > 0 else main_fps

                if mobile_width > 0 and mobile_height > 0:
                    self.out_mobile = cv2.VideoWriter(str(self.params['mobile_output_path']), mobile_fourcc, mobile_fps, (mobile_width, mobile_height))
                    if not self.out_mobile.isOpened():
                        logger.error(f"Error al crear archivo móvil en {self.params['mobile_output_path']}")
                        self.out_mobile = None
                else:
                    logger.warning("Cámara móvil no tiene dimensiones válidas para guardar.")
                    self.out_mobile = None

            total_frames = -1 if self.params['is_camera'] else int(self.cap_main.get(cv2.CAP_PROP_FRAME_COUNT))
            return total_frames

        except Exception as e:
            self.error_occurred.emit(f"Error en configuración I/O del thread: {str(e)}")
            self._release_resources() # Clean up if setup fails
            return -2 # Indicate setup failure

    def run(self):
        self.running = True
        logger.info("Thread de procesamiento iniciado.")

        total_frames = self._setup_io_in_thread()
        if total_frames == -2 : # Setup failed critically
            self.running = False
            logger.error("Fallo en setup I/O del thread. Thread terminado.")
            return # Emitter in _setup_io_in_thread already sent error

        frame_count = 0
        primer_id, rastreo_id, ultima_coords, frames_perdidos = None, None, None, 0
        ids_globales = set()
        controlar_servo = self.params['is_camera'] and self.serial_widget.is_serial_enabled()

        if self.params['serial_enabled_for_processing'] and controlar_servo:
            s_port = self.params['serial_port']
            s_baud = self.params['serial_baudrate']
            if s_port and serial_manager.connect(s_port, s_baud):
                logger.info(f"Comunicación serial conectada en thread para {s_port}@{s_baud}")
            else:
                logger.warning(f"No se pudo conectar serial en thread para {s_port}@{s_baud}")
                controlar_servo = False # Disable servo if connection fails

        try:
            while self.running and self.cap_main and self.cap_main.isOpened():
                ret_main, frame_main = self.cap_main.read()
                if not ret_main:
                    logger.info("Fin del stream principal o error de lectura.")
                    break

                second_frame_for_display = None
                second_frame_for_saving = None

                if self.cap_second and self.cap_second.isOpened():
                    ret_second, temp_second_frame = self.cap_second.read()
                    if ret_second:
                        second_frame_for_display = temp_second_frame.copy() # For display
                        if self.out_mobile and self.params.get('save_mobile'):
                            second_frame_for_saving = temp_second_frame # For saving (can be same obj if not modified)

                frame_count += 1
                progress_text = ""
                if not self.params['is_camera'] and total_frames > 0:
                    progress = int((frame_count / total_frames) * 100)
                    progress_text = f"Procesando video: {progress}% (Frame {frame_count}/{total_frames})"
                elif self.params['is_camera']:
                    progress_text = f"Procesando en vivo: Frame {frame_count}"

                if frame_count % 15 == 0: # Update progress periodically
                    self.progress_update.emit(frame_count, total_frames, progress_text)

                # --- Person Detection and Tracking ---
                annotated_frame_main = frame_main.copy() # Work on a copy
                try:
                    result = self.person_tracker.detectar_personas(frame_main, self.params['confidence'])
                    if result and hasattr(result, 'boxes') and result.boxes is not None and len(result.boxes) > 0:
                        boxes = result.boxes
                        ids_esta_frame = self.person_tracker.extraer_ids(boxes)
                        primer_id, rastreo_id, reiniciar_coords, frames_perdidos = self.person_tracker.actualizar_rastreo(
                            primer_id, rastreo_id, ids_esta_frame, frames_perdidos, self.params['frames_espera']
                        )
                        if reiniciar_coords: ultima_coords = None

                        # Ensure result.plot() returns a NumPy array if not None
                        plot_frame = result.plot()
                        if plot_frame is not None and isinstance(plot_frame, np.ndarray):
                             annotated_frame_main = plot_frame # Use the plotted frame from detector

                        # Dibujar anotaciones adicionales y controlar servo
                        annotated_frame_main, ultima_coords = self.person_tracker.dibujar_anotaciones(
                            annotated_frame_main, boxes, rastreo_id, ultima_coords, ids_globales,
                            frame_main.shape[1], controlar_servo=controlar_servo # Pass serial_manager if needed by this func
                        )
                except Exception as e_track:
                    logger.error(f"Error durante detección/tracking: {e_track}", exc_info=True)
                    # Continue with unprocessed frame if tracking fails

                self.processed_frame.emit(annotated_frame_main, second_frame_for_display)

                if self.out_main and self.params.get('save_main'):
                    self.out_main.write(annotated_frame_main)

                if self.out_mobile and self.params.get('save_mobile') and second_frame_for_saving is not None:
                    self.out_mobile.write(second_frame_for_saving)

                # QThread.msleep(10) # Small delay to allow GUI to process events if needed, or rely on camera FPS

            if not self.running: # Stopped by user
                logger.info("Procesamiento detenido por el usuario.")
                self.processing_finished.emit("Procesamiento detenido por el usuario.")
            else: # Loop finished naturally (e.g. end of video)
                logger.info("Procesamiento de video finalizado.")
                output_msg = "Procesamiento finalizado."
                if not self.params['is_camera']:
                    saved_files = []
                    if self.params.get('save_main') and self.out_main: saved_files.append(self.params['output_path'])
                    if self.params.get('save_mobile') and self.out_mobile: saved_files.append(self.params['mobile_output_path'])
                    if saved_files: output_msg = f"Procesado. Guardado en: {', '.join(saved_files)}"
                    else: output_msg = "Procesado. No se configuró ninguna salida de archivo."
                self.processing_finished.emit(output_msg)

        except Exception as e:
            logger.error(f"Error mayor en el thread de procesamiento: {e}", exc_info=True)
            self.error_occurred.emit(f"Error en procesamiento: {str(e)}")
        finally:
            self._release_resources()
            if self.params['serial_enabled_for_processing'] and controlar_servo: # Disconnect serial if thread managed it
                serial_manager.disconnect()
            logger.info("Thread de procesamiento terminado y recursos liberados.")

    def _release_resources(self):
        if self.cap_main: self.cap_main.release()
        if self.cap_second: self.cap_second.release()
        if self.out_main: self.out_main.release()
        if self.out_mobile: self.out_mobile.release()
        self.cap_main, self.cap_second, self.out_main, self.out_mobile = None, None, None, None

    def stop(self):
        logger.info("Solicitando detención del thread de procesamiento...")
        self.running = False


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación TrackerVidriera."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("TrackerVidriera")
        self.setMinimumSize(800, 600)

        self.procesando_flag = False # Use this flag for state
        self.config_panel_width = 300
        self.processing_thread = None

        # self.video_output = VideoOutputManager() # Not used if VideoWriters handled in thread
        self.person_tracker = PersonTrackingManager() # Initialize your tracker

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo")

        self.init_ui() # Initializes all widgets
        self.connect_widget_signals() # Connect signals after all widgets are created

        self.showMaximized()
        self.load_settings_to_ui()
        if hasattr(self, 'input_widget') and self.input_widget:
             self.toggle_input_type(self.input_widget.get_input_type())


    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        header_layout = QHBoxLayout()
        title_label = QLabel("TrackerVidriera")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.new_process_button_main = QPushButton("Procesar")
        self.new_process_button_main.setMinimumHeight(40)
        self.new_process_button_main.setStyleSheet("background-color: green; color: white;")
        self.new_process_button_main.clicked.connect(self.start_processing_video) # Changed
        self.new_process_button_main.hide()
        header_layout.addWidget(self.new_process_button_main)

        self.new_stop_button_main = QPushButton("Stop")
        self.new_stop_button_main.setMinimumHeight(40)
        self.new_stop_button_main.setStyleSheet("background-color: red; color: white;")
        self.new_stop_button_main.clicked.connect(self.stop_processing_video) # Changed
        self.new_stop_button_main.hide()
        header_layout.addWidget(self.new_stop_button_main)
        main_layout.addLayout(header_layout)

        self.content_layout = QHBoxLayout()

        self.config_panel = QWidget()
        config_layout = QVBoxLayout(self.config_panel)
        config_layout.setSpacing(10)

        # Instantiate all widgets
        self.input_widget = InputConfigWidget()
        self.model_widget = ModelConfigWidget()
        self.output_widget = OutputConfigWidget()
        self.serial_widget = SerialConfigWidget(serial_manager) # Pass the global instance
        self.action_buttons = ActionButtonsWidget()
        self.video_display = VideoDisplayWidget()

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
        config_layout.insertWidget(0, self.manual_collapse_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.content_layout.addWidget(self.config_panel, 1) # Config panel takes 1 part
        self.content_layout.addWidget(self.video_display, 3) # Video display takes 3 parts (adjust as needed)

        main_layout.addLayout(self.content_layout)
        self.setCentralWidget(central_widget)

        shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        shortcut.activated.connect(self.toggle_config_panel)

    def connect_widget_signals(self):
        self.input_widget.input_type_changed.connect(self.toggle_input_type)
        self.input_widget.video_file_selected.connect(self.on_video_file_selected)
        self.input_widget.status_message.connect(self.show_status_message)
        # Input widget's frame_received is for live preview, not processing output
        self.input_widget.frame_received.connect(self.video_display.display_frame)
        self.input_widget.second_frame_received.connect(self.video_display.display_second_frame)
        self.input_widget.camera_selected.connect(self.on_main_camera_selected)
        self.input_widget.second_camera_selected.connect(self.on_second_camera_selected)

        self.model_widget.status_message.connect(self.show_status_message)
        self.serial_widget.status_message.connect(self.show_status_message)

        self.action_buttons.process_clicked.connect(self.start_processing_video) # Changed
        self.action_buttons.stop_clicked.connect(self.stop_processing_video) # Changed
        self.action_buttons.save_config_clicked.connect(self.save_settings_from_ui)

        self.video_display.display_error.connect( # Connect to error signal from display widget
            lambda msg: self.show_status_message(f"Error de Visualización: {msg}", 5000)
        )

    def _update_ui_for_processing_state(self):
        is_live_camera_mode = self.input_widget.get_input_type() == 1
        self.action_buttons.set_processing_mode(self.procesando_flag, is_live_camera_mode)

        if self.config_panel.maximumWidth() == 0: # Panel is collapsed
            if self.procesando_flag:
                self.new_process_button_main.hide()
                self.new_stop_button_main.show()
            else:
                self.new_process_button_main.show()
                self.new_stop_button_main.hide()
                # Update "Procesar" button state based on action_buttons' state
                self.new_process_button_main.setEnabled(self.action_buttons.process_button.isEnabled())
                self.new_process_button_main.setText(self.action_buttons.process_button.text())
        else: # Panel is expanded
            self.new_process_button_main.hide()
            self.new_stop_button_main.hide()

        # Disable config widgets during processing
        self.input_widget.setEnabled(not self.procesando_flag)
        self.model_widget.setEnabled(not self.procesando_flag)
        self.output_widget.setEnabled(not self.procesando_flag)
        self.serial_widget.setEnabled(not self.procesando_flag)
        # self.action_buttons.save_config_button.setEnabled(not self.procesando_flag) # Already handled by set_processing_mode indirectly


    def toggle_input_type(self, index): # index 0 for file, 1 for camera
        is_file_mode = (index == 0)
        can_process = False
        if is_file_mode:
            can_process = bool(self.input_widget.get_video_path())
        else: # Camera mode
            # Enable if at least one camera is selected (main camera)
            can_process = self.input_widget.get_selected_camera_id() is not None

        self.action_buttons.enable_process_button(
            enabled=can_process,
            text="Procesar video" if is_file_mode else "Procesar en vivo"
        )
        self._update_ui_for_processing_state() # Update header buttons if panel collapsed


    def on_video_file_selected(self, file_path):
        if file_path and self.input_widget.get_input_type() == 0: # File mode
            self.action_buttons.enable_process_button(True)
            # self.video_display.display_second_frame(None) # Preview widget handles this
        self._update_ui_for_processing_state()

    def on_main_camera_selected(self, camera_id, camera_description):
        self.show_status_message(f"Cámara principal seleccionada: {camera_description}", 2000)
        if self.input_widget.get_input_type() == 1: # Camera mode
            self.action_buttons.enable_process_button(enabled=(camera_id is not None))
        self._update_ui_for_processing_state()


    def on_second_camera_selected(self, camera_id, camera_description):
        if camera_id != -1:
            self.show_status_message(f"Segunda cámara seleccionada: {camera_description}", 2000)
        else:
            self.show_status_message("Segunda cámara deshabilitada.", 2000)
            # self.video_display.display_second_frame(None) # Preview handles this via input_widget signals

    def show_status_message(self, message, timeout=0):
        self.status_bar.showMessage(message, timeout)
        if "error" in message.lower() or "advertencia" in message.lower():
            logger.warning(f"Status Bar: {message}")
        else:
            logger.info(f"Status Bar: {message}")


    def load_settings_to_ui(self):
        settings.load_settings()
        logger.info("Cargando configuración a la UI.")

        self.input_widget.set_all_settings({
            "input_type": getattr(settings, 'input_type', 0),
            "video_path": getattr(settings, 'video_path', None),
            "camera_id": getattr(settings, 'camera_id', 0),
            "second_camera_id": getattr(settings, 'second_camera_id', -1)
        })

        self.model_widget.set_model_path(getattr(settings, 'model_path', "yolov8n.pt"))
        self.model_widget.set_confidence(getattr(settings, 'confidence_threshold', 0.6))
        self.model_widget.set_frames_wait(getattr(settings, 'frames_espera', 10))

        self.output_widget.set_output_path(getattr(settings, 'output_path', 'salida_principal.avi'))
        self.output_widget.set_codec(getattr(settings, 'output_format', 'XVID'))
        self.output_widget.set_save_main_camera(getattr(settings, 'save_main_camera', True))
        self.output_widget.set_save_mobile_camera(getattr(settings, 'save_mobile_camera', False))
        self.output_widget.set_mobile_output_path(getattr(settings, 'mobile_output_path', 'salida_movil.avi'))

        self.serial_widget.set_serial_port(getattr(settings, 'serial_port', None)) # Allow None
        self.serial_widget.set_baudrate(getattr(settings, 'serial_baudrate', 115200))
        self.serial_widget.set_serial_enabled(getattr(settings, 'serial_enabled', True))

        QTimer.singleShot(100, self._apply_panel_state_from_settings)


    def _apply_panel_state_from_settings(self):
        if not hasattr(self, 'config_panel_width') or self.config_panel_width <= 0:
            self.config_panel_width = self.config_panel.width() if hasattr(self, 'config_panel') and self.config_panel.width() > 0 else 300

        is_collapsed_setting = getattr(settings, 'config_panel_collapsed', False)
        if is_collapsed_setting:
            if not (hasattr(self, 'config_panel') and self.config_panel.maximumWidth() == 0):
                 self.collapse_config_panel(animate=False) # Collapse without animation on load
        else:
            if hasattr(self, 'config_panel') and self.config_panel.maximumWidth() == 0:
                self.expand_config_panel(animate=False) # Expand without animation
        self._update_ui_for_processing_state()


    def save_settings_from_ui(self):
        logger.info("Guardando configuración desde la UI.")
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
        settings.save_main_camera = self.output_widget.should_save_main_camera()
        settings.save_mobile_camera = self.output_widget.should_save_mobile_camera()
        settings.mobile_output_path = self.output_widget.get_mobile_output_path()

        settings.serial_port = self.serial_widget.get_serial_port()
        settings.serial_baudrate = self.serial_widget.get_baudrate()
        settings.serial_enabled = self.serial_widget.is_serial_enabled()

        if hasattr(self, 'config_panel'):
            settings.config_panel_collapsed = (self.config_panel.maximumWidth() == 0)

        if settings.save_settings():
            self.show_status_message("Configuración guardada correctamente", 3000)
        else:
            self.show_status_message("Error al guardar configuración.", 3000)
            logger.error("Fallo al guardar la configuración (settings.save_settings() devolvió False)")


    def _get_processing_parameters(self):
        params = {}
        params['model_path'] = self.model_widget.get_model_path()
        params['confidence'] = self.model_widget.get_confidence()
        params['frames_espera'] = self.model_widget.get_frames_wait()

        params['output_path'] = self.output_widget.get_output_path()
        params['codec'] = self.output_widget.get_codec()
        params['save_main'] = self.output_widget.should_save_main_camera()
        params['save_mobile'] = self.output_widget.should_save_mobile_camera()
        params['mobile_output_path'] = self.output_widget.get_mobile_output_path()
        params['mobile_codec'] = params['codec'] # Use global codec

        params['is_camera'] = (self.input_widget.get_input_type() == 1)

        if params['is_camera']:
            params['video_path'] = self.input_widget.get_selected_camera_id()
            params['video_path_display'] = self.input_widget.get_selected_camera_description()
            if params['video_path'] is None:
                self.show_status_message("Error: Cámara principal no seleccionada.", 3000)
                return None

            second_cam_id = self.input_widget.get_selected_second_camera_id()
            if second_cam_id is not None:
                params['second_camera_id'] = second_cam_id
                params['second_camera_display'] = self.input_widget.get_selected_second_camera_description()
        else: # File mode
            params['video_path'] = self.input_widget.get_video_path()
            if not params['video_path'] or not Path(params['video_path']).is_file():
                self.show_status_message("Error: Archivo de video no válido o no seleccionado.", 3000)
                return None
            params['video_path_display'] = Path(params['video_path']).name

        # Resolve model path
        # This pathing assumes 'models' is a sibling of the script's parent's parent,
        # or a sibling of the script's parent.
        # Or that model_name is an absolute path or in CWD.
        # It's better to use a BASE_APP_PATH or a path from settings for robustness.
        possible_model_paths = [
            Path(__file__).resolve().parent.parent / "models" / params['model_path'], # If main.py is in project_root/ui/
            Path(params['model_path']) # Absolute or relative to CWD
        ]
        model_path_actual = None
        for p_path in possible_model_paths:
            try:
                if p_path.exists() and p_path.is_file():
                    model_path_actual = p_path
                    break
            except OSError: continue

        if not model_path_actual:
            # Try one more common structure: project_root/models
            alt_path = Path(sys.argv[0]).resolve().parent.parent / "models" / params['model_path']
            if alt_path.exists() and alt_path.is_file():
                 model_path_actual = alt_path
            else:
                self.show_status_message(f"Error: Modelo '{params['model_path']}' no encontrado. Rutas verificadas: {possible_model_paths}, {alt_path}", 5000)
                logger.error(f"Modelo '{params['model_path']}' no encontrado.")
                return None
        params['model_path'] = str(model_path_actual)

        # Serial parameters for the thread
        params['serial_enabled_for_processing'] = self.serial_widget.is_serial_enabled()
        params['serial_port'] = self.serial_widget.get_serial_port()
        params['serial_baudrate'] = self.serial_widget.get_baudrate()

        return params

    def start_processing_video(self):
        if self.procesando_flag:
            self.show_status_message("El procesamiento ya está en curso.", 3000)
            return

        params = self._get_processing_parameters()
        if not params:
            self.show_status_message("Parámetros de procesamiento inválidos. No se puede iniciar.", 4000)
            return

        if not params['is_camera'] and not params.get('save_main') and not params.get('save_mobile'):
            self.show_status_message("Modo Archivo: Debe seleccionar al menos una salida de video para guardar.", 4000)
            return

        if params['serial_enabled_for_processing'] and not params['serial_port']:
            self.show_status_message("Comunicación serial activada pero no hay puerto COM seleccionado.", 4000)
            # Optionally, ask user if they want to continue without serial, or just stop.
            # For now, we proceed but servo control will likely fail or be disabled in thread.
            logger.warning("Serial habilitado pero sin puerto; el control servo podría no funcionar.")


        self.procesando_flag = True
        self._update_ui_for_processing_state() # Updates buttons and widget states

        if not (hasattr(self, 'config_panel') and self.config_panel.maximumWidth() == 0) : # If panel is not collapsed
            self.collapse_config_panel() # Collapse it

        self.show_status_message(f"Iniciando procesamiento: {params['video_path_display']}...", 0)
        logger.info(f"Iniciando procesamiento con parámetros: {params}")

        try:
            self.person_tracker.inicializar_modelo(str(params['model_path']))
            self.person_tracker.detector.set_confidence(params['confidence'])
            self.person_tracker.tracker.set_frames_espera(params['frames_espera'])
        except Exception as e_model:
            self.show_status_message(f"Error al inicializar modelo: {e_model}", 5000)
            logger.error(f"Error al inicializar modelo: {e_model}", exc_info=True)
            self.procesando_flag = False
            self._update_ui_for_processing_state()
            return

        # Stop live previews from InputConfigWidget if they are running
        self.input_widget.detener_previsualizacion()
        self.input_widget.detener_segunda_previsualizacion()

        # Clear display before starting processing thread
        self.video_display.display_frame(None)
        self.video_display.display_second_frame(None)


        self.processing_thread = VideoProcessingThread(params, self.person_tracker, self.serial_widget)
        self.processing_thread.processed_frame.connect(self._update_video_displays)
        self.processing_thread.progress_update.connect(self._update_progress_status)
        self.processing_thread.processing_finished.connect(self._handle_processing_finished)
        self.processing_thread.error_occurred.connect(self._handle_processing_error)
        self.processing_thread.finished.connect(self._on_thread_actually_finished) # For cleanup

        self.processing_thread.start()


    def _update_video_displays(self, main_frame, second_frame):
        self.video_display.display_frame(main_frame)
        if second_frame is not None:
            self.video_display.display_second_frame(second_frame)
        else: # If second_frame is explicitly None, clear its display
            self.video_display.display_second_frame(None)


    def _update_progress_status(self, current_frame, total_frames, status_text):
        self.show_status_message(status_text, 0) # Continuous update

    def _handle_processing_finished(self, message):
        self.show_status_message(message, 5000)
        logger.info(f"Thread de procesamiento reportó finalización: {message}")
        # self.procesando_flag = False # This will be set in _on_thread_actually_finished
        # self._update_ui_for_processing_state()
        # self.stop_processing_video() # Call this to ensure full cleanup, it also sets flag

    def _handle_processing_error(self, error_message):
        self.show_status_message(f"Error en procesamiento: {error_message}", 7000)
        logger.error(f"Thread de procesamiento reportó error: {error_message}")
        # self.procesando_flag = False
        # self._update_ui_for_processing_state()
        self.stop_processing_video(is_error_stop=True) # Ensure full cleanup after error

    def _on_thread_actually_finished(self):
        logger.info("QThread 'finished' signal received.")
        self.procesando_flag = False
        self._update_ui_for_processing_state()
        self.processing_thread = None # Clear the thread reference

        # Restart previews if in camera mode and not explicitly stopped by user changing mode
        if self.input_widget.get_input_type() == 1: # Camera mode
            QTimer.singleShot(100, self.input_widget.test_camera_info) # Restart main preview
            if self.input_widget.get_selected_second_camera_id() is not None:
                 QTimer.singleShot(200, self.input_widget.test_second_camera_info) # Restart second preview


    def stop_processing_video(self, is_error_stop=False):
        if self.processing_thread and self.processing_thread.isRunning():
            logger.info("Enviando señal de detención al thread de procesamiento...")
            self.processing_thread.stop()
            # Don't wait indefinitely here to keep UI responsive.
            # _on_thread_actually_finished will handle UI updates when thread truly exits.
            # If it hangs, user might need to force quit.
            # self.processing_thread.wait(3000) # Optional: wait for a bit
        else: # If thread isn't running but flag is set, or for general cleanup
            logger.info("Solicitud de detención, pero el thread no está corriendo o no existe.")
            if self.procesando_flag : # If flag was true but thread isn't (e.g. error before thread start)
                 self._on_thread_actually_finished() # Call manually to reset UI

        if not is_error_stop: # Don't show "detenido" if it was an error stop
            self.show_status_message("Procesamiento detenido.", 3000)

        # If the panel was auto-collapsed because of processing, expand it
        # unless it's meant to be collapsed by window size or user preference.
        is_collapsed_by_setting = getattr(settings, 'config_panel_collapsed', False)
        is_auto_collapsed_by_resize = hasattr(self, 'auto_collapsed_due_to_resize') and self.auto_collapsed_due_to_resize

        if not is_collapsed_by_setting and not is_auto_collapsed_by_resize:
            if hasattr(self, 'config_panel') and self.config_panel.maximumWidth() == 0:
                 self.expand_config_panel()


    def toggle_config_panel(self):
        if not hasattr(self, 'config_panel'): return
        if self.config_panel.maximumWidth() > 0 and self.config_panel.isVisible() :
            self.collapse_config_panel()
            if hasattr(settings, 'save_settings'):
                settings.config_panel_collapsed = True; settings.save_settings()
        else:
            self.expand_config_panel()
            if hasattr(settings, 'save_settings'):
                settings.config_panel_collapsed = False; settings.save_settings()


    def collapse_config_panel(self, animate=True):
        if not hasattr(self, 'config_panel'): return
        if self.config_panel.maximumWidth() == 0: # Already collapsed
            self._update_ui_for_processing_state() # Ensure header buttons are correct
            if hasattr(self, 'expand_button') and self.expand_button: self.expand_button.show()
            return

        current_width = self.config_panel.width()
        if current_width > 0: self.config_panel_width = current_width

        if animate:
            self.animation = QPropertyAnimation(self.config_panel, b"maximumWidth")
            self.animation.setDuration(300)
            self.animation.setStartValue(self.config_panel_width if current_width == 0 else current_width)
            self.animation.setEndValue(0)
            self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.animation.finished.connect(self._update_ui_for_processing_state) # Update after animation
            self.animation.start()
        else:
            self.config_panel.setMaximumWidth(0)
            self._update_ui_for_processing_state()


        if not hasattr(self, 'expand_button') or not self.expand_button:
            self.expand_button = QPushButton(">")
            self.expand_button.setFixedSize(20, 60)
            self.expand_button.clicked.connect(self.expand_config_panel)
            self.expand_button.setToolTip("Expandir panel (Ctrl+B)")
            self.expand_button.setStyleSheet("""
                QPushButton { background-color: #f0f0f0; border: 1px solid #ccc; border-left: none;
                              border-top-right-radius: 10px; border-bottom-right-radius: 10px; }
                QPushButton:hover { background-color: #e0e0e0; } """)
            # Ensure content_layout exists before inserting
            if hasattr(self, 'content_layout'):
                self.content_layout.insertWidget(0, self.expand_button, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            else:
                logger.error("content_layout no existe al crear expand_button.")


        if self.expand_button: self.expand_button.show()
        self.manual_collapse_button.hide()


    def expand_config_panel(self, animate=True):
        if not hasattr(self, 'config_panel'): return
        target_width = getattr(self, 'config_panel_width', 300)
        if target_width <=0 : target_width = 300

        if self.config_panel.maximumWidth() >= target_width and self.config_panel.isVisible(): # Already expanded
             self._update_ui_for_processing_state() # Ensure header buttons hidden
             if hasattr(self, 'expand_button') and self.expand_button: self.expand_button.hide()
             self.manual_collapse_button.show()
             return

        if animate:
            self.animation = QPropertyAnimation(self.config_panel, b"maximumWidth")
            self.animation.setDuration(300)
            self.animation.setStartValue(self.config_panel.maximumWidth())
            self.animation.setEndValue(target_width)
            self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.animation.finished.connect(self._update_ui_for_processing_state) # Update after animation
            self.animation.start()
        else:
            self.config_panel.setMaximumWidth(target_width)
            self._update_ui_for_processing_state()

        if hasattr(self, 'expand_button') and self.expand_button: self.expand_button.hide()
        self.manual_collapse_button.show()


    def closeEvent(self, event):
        logger.info("Cerrando la aplicación TrackerVidriera.")
        if hasattr(self, 'input_widget'):
            self.input_widget.detener_previsualizacion()
            self.input_widget.detener_segunda_previsualizacion()

        self.stop_processing_video() # Attempt to stop thread if running
        if self.processing_thread and self.processing_thread.isRunning():
            logger.info("Esperando que el thread de procesamiento finalice antes de cerrar...")
            self.processing_thread.wait(2000) # Wait a bit for thread to clean up

        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, 'config_panel'): return

        # Auto collapse/expand logic based on window width
        # The 'auto_collapsed_due_to_resize' flag helps distinguish user actions from automatic ones.
        if self.width() < 900 and not self.procesando_flag:
            if self.config_panel.maximumWidth() > 0 :
                self.collapse_config_panel()
                self.auto_collapsed_due_to_resize = True # Flag that resize caused collapse
        elif self.width() >= 900 and hasattr(self, 'auto_collapsed_due_to_resize') and self.auto_collapsed_due_to_resize and not self.procesando_flag:
            # Only expand if it was auto-collapsed by resize and panel is still collapsed.
            # And if user hasn't explicitly collapsed it after resize (check settings.config_panel_collapsed)
            if self.config_panel.maximumWidth() == 0 and not getattr(settings, 'config_panel_collapsed', False):
                self.expand_config_panel()
            delattr(self, 'auto_collapsed_due_to_resize')


if __name__ == '__main__':
    # Standard application startup
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show() # showMaximized is called in __init__
    sys.exit(app.exec())