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
import logging

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStatusBar, QApplication, QPushButton
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

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
from core.video_processing_thread import VideoProcessingThread # MODIFIED: Import new thread class

# --- Dummy classes for missing imports (as in original) ---
try:
    from config.settings import settings
    from core.video_output import VideoOutputManager
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
    if 'VideoOutputManager' not in sys.modules:
        logger.warning("Using DummyVideoOutputManager because core.video_output might be missing from expected path.")
        class DummyVideoOutputManager:
            def setup_output(self, *args, **kwargs): logger.info("DummyVOM: setup_output"); return True
            def write_frame(self, *args, **kwargs): logger.info("DummyVOM: write_frame"); return True
            def release(self, *args, **kwargs): logger.info("DummyVOM: release"); return True
            def get_output_info(self, *args, **kwargs): logger.info("DummyVOM: get_output_info"); return {}
        VideoOutputManager = DummyVideoOutputManager


# VideoProcessingThread class is now in core.video_processing_thread

class MainWindow(QMainWindow):
    """Ventana principal de la aplicación TrackerVidriera."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("TrackerVidriera")
        self.setMinimumSize(800, 600)

        self.procesando_flag = False
        self.config_panel_width = 300
        self.processing_thread = None

        self.person_tracker = PersonTrackingManager()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo")

        self.init_ui()
        self.connect_widget_signals()

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
        self.new_process_button_main.clicked.connect(self.start_processing_video)
        self.new_process_button_main.hide()
        header_layout.addWidget(self.new_process_button_main)

        self.new_stop_button_main = QPushButton("Stop")
        self.new_stop_button_main.setMinimumHeight(40)
        self.new_stop_button_main.setStyleSheet("background-color: red; color: white;")
        self.new_stop_button_main.clicked.connect(self.stop_processing_video)
        self.new_stop_button_main.hide()
        header_layout.addWidget(self.new_stop_button_main)
        main_layout.addLayout(header_layout)

        self.content_layout = QHBoxLayout()

        self.config_panel = QWidget()
        config_layout = QVBoxLayout(self.config_panel)
        config_layout.setSpacing(10)

        self.input_widget = InputConfigWidget()
        self.model_widget = ModelConfigWidget()
        self.output_widget = OutputConfigWidget()
        self.serial_widget = SerialConfigWidget(serial_manager)
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

        self.content_layout.addWidget(self.config_panel, 1)
        self.content_layout.addWidget(self.video_display, 3)

        main_layout.addLayout(self.content_layout)
        self.setCentralWidget(central_widget)

        shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        shortcut.activated.connect(self.toggle_config_panel)

    def connect_widget_signals(self):
        self.input_widget.input_type_changed.connect(self.toggle_input_type)
        self.input_widget.video_file_selected.connect(self.on_video_file_selected)
        self.input_widget.status_message.connect(self.show_status_message)
        self.input_widget.frame_received.connect(self.video_display.display_frame)
        self.input_widget.second_frame_received.connect(self.video_display.display_second_frame)
        self.input_widget.camera_selected.connect(self.on_main_camera_selected)
        self.input_widget.second_camera_selected.connect(self.on_second_camera_selected)

        self.model_widget.status_message.connect(self.show_status_message)
        self.serial_widget.status_message.connect(self.show_status_message)

        self.action_buttons.process_clicked.connect(self.start_processing_video)
        self.action_buttons.stop_clicked.connect(self.stop_processing_video)
        self.action_buttons.save_config_clicked.connect(self.save_settings_from_ui)

        self.video_display.display_error.connect(
            lambda msg: self.show_status_message(f"Error de Visualización: {msg}", 5000)
        )

    def _update_ui_for_processing_state(self):
        is_live_camera_mode = self.input_widget.get_input_type() == 1
        self.action_buttons.set_processing_mode(self.procesando_flag, is_live_camera_mode)

        if hasattr(self.config_panel, 'maximumWidth') and self.config_panel.maximumWidth() == 0: # Panel is collapsed
            if self.procesando_flag:
                self.new_process_button_main.hide()
                self.new_stop_button_main.show()
            else:
                self.new_process_button_main.show()
                self.new_stop_button_main.hide()
                self.new_process_button_main.setEnabled(self.action_buttons.process_button.isEnabled())
                self.new_process_button_main.setText(self.action_buttons.process_button.text())
        else: # Panel is expanded
            self.new_process_button_main.hide()
            self.new_stop_button_main.hide()

        self.input_widget.setEnabled(not self.procesando_flag)
        self.model_widget.setEnabled(not self.procesando_flag)
        self.output_widget.setEnabled(not self.procesando_flag)
        self.serial_widget.setEnabled(not self.procesando_flag)
        self.action_buttons.save_config_button.setEnabled(not self.procesando_flag)


    def toggle_input_type(self, index):
        is_file_mode = (index == 0)
        can_process = False
        if is_file_mode:
            can_process = bool(self.input_widget.get_video_path())
        else:
            can_process = self.input_widget.get_selected_camera_id() is not None

        self.action_buttons.enable_process_button(
            enabled=can_process and not self.procesando_flag, # Cannot enable if already processing
            text="Procesar video" if is_file_mode else "Procesar en vivo"
        )
        self._update_ui_for_processing_state()


    def on_video_file_selected(self, file_path):
        if file_path and self.input_widget.get_input_type() == 0:
            self.action_buttons.enable_process_button(True and not self.procesando_flag)
        self._update_ui_for_processing_state()

    def on_main_camera_selected(self, camera_id, camera_description):
        self.show_status_message(f"Cámara principal seleccionada: {camera_description}", 2000)
        if self.input_widget.get_input_type() == 1:
            self.action_buttons.enable_process_button(enabled=(camera_id is not None) and not self.procesando_flag)
        self._update_ui_for_processing_state()


    def on_second_camera_selected(self, camera_id, camera_description):
        if camera_id != -1:
            self.show_status_message(f"Segunda cámara seleccionada: {camera_description}", 2000)
        else:
            self.show_status_message("Segunda cámara deshabilitada.", 2000)

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

        self.serial_widget.set_serial_port(getattr(settings, 'serial_port', None))
        self.serial_widget.set_baudrate(getattr(settings, 'serial_baudrate', 115200))
        self.serial_widget.set_serial_enabled(getattr(settings, 'serial_enabled', True))

        QTimer.singleShot(100, self._apply_panel_state_from_settings)


    def _apply_panel_state_from_settings(self):
        # Ensure config_panel_width is initialized
        if not hasattr(self, 'config_panel_width') or self.config_panel_width <= 0:
            # Attempt to get current width if panel exists and is visible, otherwise default
            if hasattr(self, 'config_panel') and self.config_panel and self.config_panel.isVisible():
                current_w = self.config_panel.width()
                self.config_panel_width = current_w if current_w > 50 else 300 # Ensure a minimum sensible width
            else:
                self.config_panel_width = 300

        is_collapsed_setting = getattr(settings, 'config_panel_collapsed', False)

        # Ensure UI elements exist before manipulating
        if hasattr(self, 'config_panel') and self.config_panel:
            if is_collapsed_setting:
                if self.config_panel.maximumWidth() > 0: # If not already collapsed
                    self.collapse_config_panel(animate=False)
            else:
                if self.config_panel.maximumWidth() == 0: # If currently collapsed
                    self.expand_config_panel(animate=False)
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
        params['model_name'] = self.model_widget.get_model_path() # Store name for messages
        params['confidence'] = self.model_widget.get_confidence()
        params['frames_espera'] = self.model_widget.get_frames_wait()

        params['output_path'] = self.output_widget.get_output_path()
        params['codec'] = self.output_widget.get_codec()
        params['save_main'] = self.output_widget.should_save_main_camera()
        params['save_mobile'] = self.output_widget.should_save_mobile_camera()
        params['mobile_output_path'] = self.output_widget.get_mobile_output_path()
        params['mobile_codec'] = params['codec']

        params['is_camera'] = (self.input_widget.get_input_type() == 1)

        if params['is_camera']:
            params['video_path'] = self.input_widget.get_selected_camera_id()
            params['video_path_display'] = self.input_widget.get_selected_camera_description()
            if params['video_path'] is None:
                self.show_status_message("Error: Cámara principal no seleccionada para procesamiento.", 3000)
                return None

            second_cam_id = self.input_widget.get_selected_second_camera_id()
            if second_cam_id is not None: # Will be None if "Ninguna" or error
                params['second_camera_id'] = second_cam_id
                params['second_camera_display'] = self.input_widget.get_selected_second_camera_description()
            else:
                params['second_camera_id'] = None # Explicitly set to None
        else:
            video_file_path_str = self.input_widget.get_video_path()
            if not video_file_path_str:
                self.show_status_message("Error: Archivo de video no seleccionado para procesamiento.", 3000)
                return None
            video_file_path = Path(video_file_path_str)
            if not video_file_path.is_file():
                self.show_status_message(f"Error: Archivo de video no encontrado: {video_file_path_str}", 3000)
                return None
            params['video_path'] = str(video_file_path)
            params['video_path_display'] = video_file_path.name

        # Resolve model path (using the name from model_widget)
        model_filename = self.model_widget.get_model_path()
        # Prioritize models directory relative to where main_window_refactored.py is (ui/)
        # Assuming structure: project_root/ui/main_window_refactored.py and project_root/models/
        project_root_models_dir = Path(__file__).resolve().parent.parent / "models"

        model_path_actual = project_root_models_dir / model_filename
        if not (model_path_actual.exists() and model_path_actual.is_file()):
            # Fallback: check if model_filename is an absolute path or relative to CWD
            model_path_actual_alt = Path(model_filename)
            if model_path_actual_alt.exists() and model_path_actual_alt.is_file():
                model_path_actual = model_path_actual_alt
            else:
                self.show_status_message(f"Error: Modelo '{model_filename}' no encontrado.", 5000)
                logger.error(f"Modelo '{model_filename}' no encontrado. Verificado en: {project_root_models_dir / model_filename} y como ruta directa/relativa.")
                return None
        params['model_path'] = str(model_path_actual)
        params['model_name_resolved'] = model_path_actual.name # For messages if needed

        params['serial_port'] = self.serial_widget.get_serial_port() # Can be None
        params['serial_baudrate'] = self.serial_widget.get_baudrate()
        # serial_enabled for processing is handled by serial_widget passed to thread constructor

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

        if self.serial_widget.is_serial_enabled() and not params['serial_port']:
            # Log warning, but allow processing to continue. Thread will handle non-connection.
            logger.warning("Serial habilitado pero sin puerto seleccionado; control servo no funcionará.")
            self.show_status_message("Advertencia: Serial activado pero no hay puerto COM seleccionado.", 4000)


        self.procesando_flag = True
        self._update_ui_for_processing_state()

        if hasattr(self.config_panel, 'maximumWidth') and not (self.config_panel.maximumWidth() == 0) :
            self.collapse_config_panel()

        self.show_status_message(f"Iniciando procesamiento: {params['video_path_display']}...", 0)
        logger.info(f"Iniciando procesamiento con parámetros: {params}")

        try:
            # Ensure PersonTrackingManager is robust for re-initialization if needed
            self.person_tracker.inicializar_modelo(str(params['model_path']))
            if hasattr(self.person_tracker, 'detector') and self.person_tracker.detector:
                 self.person_tracker.detector.set_confidence(params['confidence'])
            if hasattr(self.person_tracker, 'tracker') and self.person_tracker.tracker:
                 self.person_tracker.tracker.set_frames_espera(params['frames_espera'])
        except Exception as e_model:
            self.show_status_message(f"Error al inicializar modelo: {e_model}", 5000)
            logger.error(f"Error al inicializar modelo: {e_model}", exc_info=True)
            self.procesando_flag = False # Reset flag
            self._update_ui_for_processing_state() # Update UI
            return

        self.input_widget.detener_previsualizacion()
        self.input_widget.detener_segunda_previsualizacion()

        self.video_display.display_frame(None)
        self.video_display.display_second_frame(None)

        self.processing_thread = VideoProcessingThread(params, self.person_tracker, self.serial_widget, self)
        self.processing_thread.processed_frame.connect(self._update_video_displays)
        self.processing_thread.progress_update.connect(self._update_progress_status)
        self.processing_thread.processing_finished.connect(self._handle_processing_finished)
        self.processing_thread.error_occurred.connect(self._handle_processing_error)
        self.processing_thread.finished.connect(self._on_thread_actually_finished)

        self.processing_thread.start()


    def _update_video_displays(self, main_frame, second_frame):
        self.video_display.display_frame(main_frame)
        if second_frame is not None:
            self.video_display.display_second_frame(second_frame)
        else:
            self.video_display.display_second_frame(None)


    def _update_progress_status(self, current_frame, total_frames, status_text):
        self.show_status_message(status_text, 0)

    def _handle_processing_finished(self, message):
        self.show_status_message(message, 5000)
        logger.info(f"Thread de procesamiento reportó finalización: {message}")
        # Flag and UI state will be handled by _on_thread_actually_finished

    def _handle_processing_error(self, error_message):
        self.show_status_message(f"Error en procesamiento: {error_message}", 7000)
        logger.error(f"Thread de procesamiento reportó error: {error_message}")
        # Flag and UI state will be handled by _on_thread_actually_finished,
        # which is connected to thread's 'finished' signal, emitted even on error exits.
        # No need to call stop_processing_video here as thread termination handles it.

    def _on_thread_actually_finished(self):
        logger.info("QThread 'finished' signal received (procesamiento terminado o detenido).")
        self.procesando_flag = False
        self._update_ui_for_processing_state()
        self.processing_thread = None

        if self.input_widget.get_input_type() == 1: # Camera mode
            # Only restart previews if the application is not closing
            if self.isVisible():
                # Delay slightly to ensure processing thread resources are fully clear
                QTimer.singleShot(200, lambda: self.input_widget.test_camera_info() if self.input_widget.get_selected_camera_id() is not None else None)
                if self.input_widget.get_selected_second_camera_id() is not None:
                    QTimer.singleShot(400, lambda: self.input_widget.test_second_camera_info() if self.input_widget.get_selected_second_camera_id() is not None else None)


    def stop_processing_video(self): # Renamed from is_error_stop
        if self.processing_thread and self.processing_thread.isRunning():
            logger.info("Enviando señal de detención al thread de procesamiento...")
            self.processing_thread.stop()
            # UI state will be updated via _on_thread_actually_finished when thread truly stops.
        elif self.procesando_flag: # Flag is set but thread is not running (e.g. error before start)
             logger.info("Flag de procesamiento activo pero thread no corre. Reseteando UI.")
             self._on_thread_actually_finished() # Manually trigger cleanup/UI reset

        self.show_status_message("Procesamiento detenido.", 3000)

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
        if self.config_panel.maximumWidth() == 0:
            self._update_ui_for_processing_state()
            if hasattr(self, 'expand_button') and self.expand_button: self.expand_button.show()
            if hasattr(self, 'manual_collapse_button'): self.manual_collapse_button.hide()
            return

        current_width = self.config_panel.width()
        if current_width > 0: self.config_panel_width = current_width

        # Ensure expand_button is created before animation starts
        if not hasattr(self, 'expand_button') or not self.expand_button:
            self.expand_button = QPushButton(">")
            self.expand_button.setFixedSize(20, 60)
            self.expand_button.clicked.connect(lambda: self.expand_config_panel(animate=True)) # Ensure expand is animated
            self.expand_button.setToolTip("Expandir panel (Ctrl+B)")
            self.expand_button.setStyleSheet("""
                QPushButton { background-color: #f0f0f0; border: 1px solid #ccc; border-left: none;
                              border-top-right-radius: 10px; border-bottom-right-radius: 10px; }
                QPushButton:hover { background-color: #e0e0e0; } """)
            if hasattr(self, 'content_layout'):
                self.content_layout.insertWidget(0, self.expand_button, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if animate:
            self.animation_collapse = QPropertyAnimation(self.config_panel, b"maximumWidth") # Use different animation object names
            self.animation_collapse.setDuration(300)
            self.animation_collapse.setStartValue(self.config_panel_width if current_width == 0 else current_width)
            self.animation_collapse.setEndValue(0)
            self.animation_collapse.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.animation_collapse.finished.connect(self._update_ui_for_processing_state)
            self.animation_collapse.finished.connect(lambda: self.expand_button.show() if self.expand_button else None)
            self.animation_collapse.finished.connect(lambda: self.manual_collapse_button.hide() if self.manual_collapse_button else None)
            self.animation_collapse.start()
        else:
            self.config_panel.setMaximumWidth(0)
            self._update_ui_for_processing_state()
            if self.expand_button: self.expand_button.show()
            if self.manual_collapse_button: self.manual_collapse_button.hide()


    def expand_config_panel(self, animate=True):
        if not hasattr(self, 'config_panel'): return
        target_width = getattr(self, 'config_panel_width', 300)
        if target_width <=0 : target_width = 300

        if self.config_panel.maximumWidth() >= target_width and self.config_panel.isVisible():
             self._update_ui_for_processing_state()
             if hasattr(self, 'expand_button') and self.expand_button: self.expand_button.hide()
             if hasattr(self, 'manual_collapse_button'): self.manual_collapse_button.show()
             return

        if animate:
            self.animation_expand = QPropertyAnimation(self.config_panel, b"maximumWidth") # Use different animation object names
            self.animation_expand.setDuration(300)
            self.animation_expand.setStartValue(self.config_panel.maximumWidth())
            self.animation_expand.setEndValue(target_width)
            self.animation_expand.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.animation_expand.finished.connect(self._update_ui_for_processing_state)
            self.animation_expand.finished.connect(lambda: self.expand_button.hide() if self.expand_button else None)
            self.animation_expand.finished.connect(lambda: self.manual_collapse_button.show() if self.manual_collapse_button else None)
            self.animation_expand.start()
        else:
            self.config_panel.setMaximumWidth(target_width)
            self._update_ui_for_processing_state()
            if hasattr(self, 'expand_button') and self.expand_button: self.expand_button.hide()
            if hasattr(self, 'manual_collapse_button'): self.manual_collapse_button.show()


    def closeEvent(self, event):
        logger.info("Cerrando la aplicación TrackerVidriera.")
        if hasattr(self, 'input_widget'):
            self.input_widget.detener_previsualizacion()
            self.input_widget.detener_segunda_previsualizacion()

        self.stop_processing_video()
        if self.processing_thread and self.processing_thread.isRunning():
            logger.info("Esperando que el thread de procesamiento finalice antes de cerrar...")
            if not self.processing_thread.wait(2000): # Wait up to 2 seconds
                 logger.warning("El thread de procesamiento no finalizó a tiempo. Forzando salida.")

        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, 'config_panel'): return

        if self.width() < 900 and not self.procesando_flag:
            if self.config_panel.maximumWidth() > 0 :
                self.collapse_config_panel()
                self.auto_collapsed_due_to_resize = True
        elif self.width() >= 900 and hasattr(self, 'auto_collapsed_due_to_resize') and self.auto_collapsed_due_to_resize and not self.procesando_flag:
            if self.config_panel.maximumWidth() == 0 and not getattr(settings, 'config_panel_collapsed', False):
                self.expand_config_panel()
            if hasattr(self, 'auto_collapsed_due_to_resize'): # Check again before deleting
                delattr(self, 'auto_collapsed_due_to_resize')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())