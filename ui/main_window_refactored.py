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
from ui.widgets.output_config_widget import OutputConfigWidget # Asegúrate que este archivo esté actualizado
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

            # Main output
            self.output_path = "salida_principal.avi"
            self.output_format = "XVID" # Códec Global
            self.save_main_camera = True

            # Mobile output
            self.save_mobile_camera = False
            self.mobile_output_path = "salida_movil.avi"
            # self.mobile_output_format no es necesario, usa output_format

            self.serial_port = "COM3"
            self.serial_baudrate = 115200
            self.serial_enabled = True
            self.config_panel_collapsed = False

            self.input_type = 0
            self.video_path = None
            self.camera_id = 0
            self.second_camera_id = -1

        def save_settings(self):
            print("DummySettings: save_settings called")
            return True
        def load_settings(self):
            print("DummySettings: load_settings called")
            pass
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
        self.config_panel_width = 300

        self.new_stop_button_main = None
        self.new_process_button_main = None

        self.video_output = VideoOutputManager()
        self.person_tracker = PersonTrackingManager()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo")

        self.init_ui()
        self.showMaximized()
        self.load_settings_to_ui()
        if hasattr(self, 'input_widget') and self.input_widget: # Check if input_widget is initialized
             self.toggle_input_type(self.input_widget.get_input_type())


    def init_ui(self):
        """Inicializa la interfaz de usuario."""
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
        self.new_process_button_main.clicked.connect(self.process_video)
        self.new_process_button_main.hide()
        header_layout.addWidget(self.new_process_button_main)

        self.new_stop_button_main = QPushButton("Stop")
        self.new_stop_button_main.setMinimumHeight(40)
        self.new_stop_button_main.setStyleSheet("background-color: red; color: white;")
        self.new_stop_button_main.clicked.connect(self.detener_procesamiento)
        self.new_stop_button_main.hide()
        header_layout.addWidget(self.new_stop_button_main)
        main_layout.addLayout(header_layout)

        self.content_layout = QHBoxLayout()

        self.config_panel = QWidget()
        config_layout = QVBoxLayout(self.config_panel)
        config_layout.setSpacing(10)

        self.input_widget = InputConfigWidget()
        self.model_widget = ModelConfigWidget()
        self.output_widget = OutputConfigWidget() # Make sure this uses the updated OutputConfigWidget
        self.serial_widget = SerialConfigWidget(serial_manager)
        self.action_buttons = ActionButtonsWidget()
        self.video_display = VideoDisplayWidget()

        self.connect_widget_signals()

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
        self.content_layout.addWidget(self.video_display, 2)

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

        self.action_buttons.process_clicked.connect(self.process_video)
        self.action_buttons.stop_clicked.connect(self.detener_procesamiento)
        self.action_buttons.save_config_clicked.connect(self.save_settings_from_ui)

    def toggle_input_type(self, index):
        is_file_mode = (index == 0)
        self.action_buttons.enable_process_button(
            enabled=bool(self.input_widget.get_video_path()) if is_file_mode else True,
            text="Procesar video" if is_file_mode else "Procesar en vivo"
        )
        self._update_header_process_button_state_if_collapsed()

    def on_video_file_selected(self, file_path):
        if file_path and self.input_widget.get_input_type() == 0:
            self.action_buttons.enable_process_button(True) # El texto se actualiza en toggle_input_type
            self.video_display.display_second_frame(None)
            self._update_header_process_button_state_if_collapsed()

    def _update_header_process_button_state_if_collapsed(self):
        if hasattr(self, 'config_panel') and self.config_panel.maximumWidth() == 0 and \
           self.new_process_button_main: # Asegurarse que el botón exista
            if not self.procesando:
                self.new_process_button_main.setEnabled(self.action_buttons.process_button.isEnabled())
                self.new_process_button_main.setText(self.action_buttons.process_button.text())

    def on_main_camera_selected(self, camera_id, camera_description):
        self.show_status_message(f"Cámara principal seleccionada: {camera_description}", 2000)

    def on_second_camera_selected(self, camera_id, camera_description):
        if camera_id != -1:
            self.show_status_message(f"Segunda cámara seleccionada: {camera_description}", 2000)
        else:
            self.show_status_message("Segunda cámara deshabilitada.", 2000)
            self.video_display.display_second_frame(None)

    def show_status_message(self, message, timeout=0):
        self.status_bar.showMessage(message, timeout)

    def load_settings_to_ui(self):
        settings.load_settings()

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
        self.output_widget.set_codec(getattr(settings, 'output_format', 'XVID')) # Carga el códec global
        self.output_widget.set_save_main_camera(getattr(settings, 'save_main_camera', True))

        self.output_widget.set_save_mobile_camera(getattr(settings, 'save_mobile_camera', False))
        self.output_widget.set_mobile_output_path(getattr(settings, 'mobile_output_path', 'salida_movil.avi'))
        # No se carga mobile_output_format porque es global

        self.serial_widget.set_serial_port(getattr(settings, 'serial_port', "COM3"))
        self.serial_widget.set_baudrate(getattr(settings, 'serial_baudrate', 115200))
        self.serial_widget.set_serial_enabled(getattr(settings, 'serial_enabled', True))

        QTimer.singleShot(100, self._apply_panel_state)

    def _apply_panel_state(self):
        if not hasattr(self, 'config_panel_width') or self.config_panel_width <= 0:
            self.config_panel_width = self.config_panel.width() if hasattr(self, 'config_panel') and self.config_panel.width() > 0 else 300

        is_collapsed_setting = getattr(settings, 'config_panel_collapsed', False)
        if is_collapsed_setting:
            if not hasattr(self, 'config_panel') or self.config_panel.maximumWidth() > 0 :
                 self.collapse_config_panel()
            else:
                self.config_panel.setMaximumWidth(0)
                if hasattr(self, 'expand_button') and self.expand_button: self.expand_button.show()
                self._update_header_buttons_for_collapsed_state()
        else:
            if hasattr(self, 'config_panel') and self.config_panel.maximumWidth() == 0:
                self.expand_config_panel()

    def _update_header_buttons_for_collapsed_state(self):
        if not (self.new_process_button_main and self.new_stop_button_main and self.action_buttons):
            return # Botones no inicializados completamente

        if self.procesando:
            self.new_stop_button_main.show()
            self.new_process_button_main.hide()
        else:
            self.new_stop_button_main.hide()
            self.new_process_button_main.show()
            self.new_process_button_main.setEnabled(self.action_buttons.process_button.isEnabled())
            self.new_process_button_main.setText(self.action_buttons.process_button.text())

    def save_settings_from_ui(self):
        input_settings = self.input_widget.get_all_settings()
        settings.input_type = input_settings.get("input_type")
        settings.video_path = input_settings.get("video_path")
        settings.camera_id = input_settings.get("camera_id")
        settings.second_camera_id = input_settings.get("second_camera_id")

        settings.model_path = self.model_widget.get_model_path()
        settings.confidence_threshold = self.model_widget.get_confidence()
        settings.frames_espera = self.model_widget.get_frames_wait()

        settings.output_path = self.output_widget.get_output_path()
        settings.output_format = self.output_widget.get_codec() # Guarda el códec global
        settings.save_main_camera = self.output_widget.should_save_main_camera()

        settings.save_mobile_camera = self.output_widget.should_save_mobile_camera()
        settings.mobile_output_path = self.output_widget.get_mobile_output_path()
        # No se guarda mobile_output_format porque es global

        settings.serial_port = self.serial_widget.get_serial_port()
        settings.serial_baudrate = self.serial_widget.get_baudrate()
        settings.serial_enabled = self.serial_widget.is_serial_enabled()

        if hasattr(self, 'config_panel'):
            settings.config_panel_collapsed = self.config_panel.maximumWidth() == 0

        if settings.save_settings():
            self.show_status_message("Configuración guardada correctamente", 3000)
        else:
            self.show_status_message("Error al guardar configuración.", 3000)

    def process_video(self):
        params = self._get_processing_parameters()
        if not params:
            return

        self.procesando = True
        is_live_camera_mode = self.input_widget.get_input_type() == 1
        self.action_buttons.set_processing_mode(True, is_live_camera_mode)

        if not hasattr(self, 'config_panel') or self.config_panel.maximumWidth() > 0 :
            self.collapse_config_panel()
        else:
            self._update_header_buttons_for_collapsed_state()

        self.show_status_message(f"Procesando: {params['video_path_display']}...", 0)

        try:
            self.person_tracker.inicializar_modelo(str(params['model_path']))
            self.person_tracker.detector.set_confidence(params['confidence'])
            self.person_tracker.tracker.set_frames_espera(params['frames_espera'])

            cap, second_cap, main_out, mobile_out, total_frames = self._setup_video_io(params)
            if not cap:
                self.detener_procesamiento()
                return

            if not params['is_camera'] and not params.get('save_main') and not params.get('save_mobile'):
                self.show_status_message("Debe tildar al menos una salida para guardar video de archivo.", 4000)
                self.detener_procesamiento()
                return

            self._process_video_with_tracking(cap, second_cap, main_out, mobile_out, params, total_frames)

            if cap and cap.isOpened(): cap.release()
            if second_cap and second_cap.isOpened(): second_cap.release()

            if self.procesando:
                output_msg = "Procesamiento en vivo finalizado."
                if not params['is_camera']:
                    saved_files = []
                    if params.get('save_main') and main_out is not None : saved_files.append(params['output_path']) # Check if main_out was created
                    if params.get('save_mobile') and mobile_out is not None: saved_files.append(params['mobile_output_path']) # Check if mobile_out was created
                    if saved_files:
                        output_msg = f"Procesado. Guardado en: {', '.join(saved_files)}"
                    else:
                        output_msg = "Procesado. No se configuró ninguna salida de archivo."
                self.show_status_message(output_msg, 5000)
        except Exception as e:
            self.show_status_message(f"Error en procesamiento: {str(e)}", 5000)
            traceback.print_exc()
        finally:
            if self.procesando:
                 self.detener_procesamiento()

    def detener_procesamiento(self):
        was_processing = self.procesando
        self.procesando = False

        if hasattr(self, 'action_buttons'): # Ensure action_buttons exists
            self.action_buttons.set_processing_mode(
                False,
                self.input_widget.get_input_type() == 1
            )

        if hasattr(self, 'config_panel') and self.config_panel.maximumWidth() == 0:
            self._update_header_buttons_for_collapsed_state()
        else:
            if not (hasattr(self, 'auto_collapsed') and self.auto_collapsed):
                if hasattr(self, 'config_panel'): # Ensure config_panel exists
                    self.expand_config_panel()
            else:
                 self._update_header_buttons_for_collapsed_state()

        if was_processing:
            self.show_status_message("Procesamiento detenido.", 3000)

    def _get_processing_parameters(self):
        model_name = self.model_widget.get_model_path()
        confidence = self.model_widget.get_confidence()
        frames_espera = self.model_widget.get_frames_wait()

        output_path = self.output_widget.get_output_path()
        codec = self.output_widget.get_codec() # Códec global
        save_main = self.output_widget.should_save_main_camera()

        save_mobile = self.output_widget.should_save_mobile_camera()
        mobile_output_path = self.output_widget.get_mobile_output_path()

        is_camera = self.input_widget.get_input_type() == 1
        video_path_display = "Cámara en vivo"

        if is_camera:
            camera_id = self.input_widget.get_selected_camera_id()
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

        possible_model_paths = [
            Path(__file__).parent.parent / "models" / model_name,
            Path(__file__).resolve().parent.parent / "models" / model_name,
            Path(__file__).resolve().parent.parent.parent / model_name,
            Path(model_name)
        ]
        model_path_actual = None
        for p_path in possible_model_paths:
            try: # Path operations can raise errors if path is malformed on some OS
                if p_path.exists() and p_path.is_file():
                    model_path_actual = p_path
                    break
            except OSError:
                continue # Ignore invalid paths

        if not model_path_actual:
            self.show_status_message(f"Error: Modelo '{model_name}' no encontrado.", 3000)
            return None

        result = {
            'video_path': video_path,
            'is_camera': is_camera,
            'model_path': model_path_actual,
            'confidence': confidence,
            'frames_espera': frames_espera,
            'output_path': output_path,
            'codec': codec,
            'save_main': save_main,
            'save_mobile': save_mobile,
            'mobile_output_path': mobile_output_path,
            'mobile_codec': codec, # Usar el códec global para el móvil también
            'video_path_display': video_path_display,
        }
        if is_camera:
            second_camera_id = self.input_widget.get_selected_second_camera_id()
            if second_camera_id is not None and second_camera_id != -1:
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
            video_path_cv = int(params['video_path']) if params['is_camera'] else str(params['video_path'])
            cap = cv2.VideoCapture(video_path_cv)
            if not cap.isOpened():
                self.show_status_message(f"Error: No se pudo abrir {params['video_path_display']}", 3000)
                return None, None, None, None, 0

            if 'second_camera_id' in params and params['second_camera_id'] is not None:
                second_video_path_cv = int(params['second_camera_id'])
                second_cap = cv2.VideoCapture(second_video_path_cv)
                if not second_cap.isOpened():
                    self.show_status_message(f"Advertencia: No se pudo abrir la segunda cámara {params.get('second_camera_display', '')}.", 3000)
                    second_cap = None

            main_frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            main_frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            main_fps = cap.get(cv2.CAP_PROP_FPS)
            if main_fps <= 0: main_fps = 30.0

            if params.get('save_main') and params.get('output_path'):
                main_output_dir = Path(params['output_path']).parent
                main_output_dir.mkdir(parents=True, exist_ok=True)
                main_fourcc = cv2.VideoWriter_fourcc(*params['codec'])
                main_out = cv2.VideoWriter(str(params['output_path']), main_fourcc, main_fps, (main_frame_width, main_frame_height))
                if not main_out.isOpened():
                    self.show_status_message(f"Error al crear archivo principal en {params['output_path']}", 3000)
                    main_out = None

            if params.get('save_mobile') and params.get('mobile_output_path'):
                mobile_output_dir = Path(params['mobile_output_path']).parent
                mobile_output_dir.mkdir(parents=True, exist_ok=True)
                mobile_fourcc = cv2.VideoWriter_fourcc(*params['mobile_codec']) # mobile_codec es el global

                mobile_frame_width, mobile_frame_height, mobile_fps = 0, 0, main_fps
                can_setup_mobile_writer = False

                if second_cap and second_cap.isOpened():
                    mobile_frame_width = int(second_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    mobile_frame_height = int(second_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    _fps_mobile = second_cap.get(cv2.CAP_PROP_FPS)
                    if _fps_mobile > 0 : mobile_fps = _fps_mobile
                    if mobile_frame_width > 0 and mobile_frame_height > 0:
                        can_setup_mobile_writer = True
                elif params['is_camera']:
                    self.show_status_message("Advertencia: Cámara móvil no disponible o sin dimensiones válidas. No se guardará video móvil.", 3000)

                if can_setup_mobile_writer:
                    mobile_out = cv2.VideoWriter(str(params['mobile_output_path']), mobile_fourcc, mobile_fps, (mobile_frame_width, mobile_frame_height))
                    if not mobile_out.isOpened():
                        self.show_status_message(f"Error al crear archivo móvil en {params['mobile_output_path']}", 3000)
                        mobile_out = None
                elif params.get('save_mobile') and not can_setup_mobile_writer:
                     if not params['is_camera']: # Si es archivo y no hay 2da cam, no tiene sentido
                         self.show_status_message("Advertencia: Segunda cámara no configurada para guardar video móvil de archivo.",3000)

            total_frames = -1 if params['is_camera'] else int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            return cap, second_cap, main_out, mobile_out, total_frames

        except Exception as e:
            self.show_status_message(f"Error en setup I/O: {str(e)}", 3000)
            traceback.print_exc()
            if cap and cap.isOpened(): cap.release()
            if second_cap and second_cap.isOpened(): second_cap.release()
            if main_out: main_out.release()
            if mobile_out: mobile_out.release()
            return None, None, None, None, 0

    def _process_video_with_tracking(self, cap, second_cap, main_out, mobile_out, params, total_frames):
        primer_id, rastreo_id, ultima_coords, frames_perdidos = None, None, None, 0
        ids_globales = set()
        frame_count = 0
        controlar_servo = params['is_camera'] and self.serial_widget.is_serial_enabled()

        while self.procesando:
            ret_main, frame_main = cap.read()
            if not ret_main: break

            second_frame_for_display = None
            second_frame_for_saving = None

            if second_cap and second_cap.isOpened():
                ret_second, temp_second_frame = second_cap.read()
                if ret_second:
                    second_frame_for_display = temp_second_frame
                    if mobile_out and params.get('save_mobile'):
                        second_frame_for_saving = temp_second_frame.copy()
                    if params['is_camera']:
                        self.video_display.display_second_frame(second_frame_for_display)

            frame_count += 1
            if not params['is_camera'] and total_frames > 0:
                progress = int((frame_count / total_frames) * 100)
                self.show_status_message(f"Procesando: {progress}%", 0)
            elif params['is_camera'] and frame_count % 30 == 0:
                self.show_status_message(f"Frames procesados (en vivo): {frame_count}", 0)

            annotated_frame_main = frame_main
            result = self.person_tracker.detectar_personas(frame_main, params['confidence'])
            if result and hasattr(result, 'boxes') and result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes
                ids_esta_frame = self.person_tracker.extraer_ids(boxes)
                primer_id, rastreo_id, reiniciar_coords, frames_perdidos = self.person_tracker.actualizar_rastreo(
                    primer_id, rastreo_id, ids_esta_frame, frames_perdidos, params['frames_espera']
                )
                if reiniciar_coords: ultima_coords = None

                annotated_frame_from_plot, ultima_coords = self.person_tracker.dibujar_anotaciones(
                    result.plot(), boxes, rastreo_id, ultima_coords, ids_globales,
                    frame_main.shape[1], controlar_servo=controlar_servo
                )
                if annotated_frame_from_plot is not None:
                    annotated_frame_main = annotated_frame_from_plot

            self.video_display.display_frame(annotated_frame_main)

            if main_out and params.get('save_main'):
                main_out.write(annotated_frame_main)

            if mobile_out and params.get('save_mobile') and second_frame_for_saving is not None:
                mobile_out.write(second_frame_for_saving)

            QApplication.processEvents()

        if main_out: main_out.release()
        if mobile_out: mobile_out.release()

    def toggle_config_panel(self):
        if not hasattr(self, 'config_panel'): return
        if self.config_panel.maximumWidth() > 0 and self.config_panel.isVisible() :
            self.collapse_config_panel()
            if hasattr(settings, 'save_settings'):
                settings.config_panel_collapsed = True
                settings.save_settings()
        else:
            self.expand_config_panel()
            if hasattr(settings, 'save_settings'):
                settings.config_panel_collapsed = False
                settings.save_settings()

    def collapse_config_panel(self):
        if not hasattr(self, 'config_panel'): return
        if self.config_panel.maximumWidth() == 0:
            self._update_header_buttons_for_collapsed_state()
            if hasattr(self, 'expand_button') and self.expand_button: self.expand_button.show()
            return

        current_width = self.config_panel.width()
        if current_width > 0: self.config_panel_width = current_width

        self.animation = QPropertyAnimation(self.config_panel, b"maximumWidth")
        self.animation.setDuration(300)
        self.animation.setStartValue(self.config_panel_width if current_width == 0 else current_width)
        self.animation.setEndValue(0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        self._update_header_buttons_for_collapsed_state()

        self.animation.start()

        if not hasattr(self, 'expand_button') or not self.expand_button:
            self.expand_button = QPushButton(">")
            self.expand_button.setFixedSize(20, 60)
            self.expand_button.clicked.connect(self.expand_config_panel)
            self.expand_button.setToolTip("Expandir panel (Ctrl+B)")
            self.expand_button.setStyleSheet("""
                QPushButton { background-color: #f0f0f0; border: 1px solid #ccc; border-left: none;
                              border-top-right-radius: 10px; border-bottom-right-radius: 10px; }
                QPushButton:hover { background-color: #e0e0e0; } """)
            self.content_layout.insertWidget(0, self.expand_button, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.expand_button.show()

    def expand_config_panel(self):
        if not hasattr(self, 'config_panel'): return
        target_width = getattr(self, 'config_panel_width', 300)
        if target_width <=0 : target_width = 300

        if self.config_panel.maximumWidth() >= target_width and self.config_panel.isVisible():
             if self.new_stop_button_main: self.new_stop_button_main.hide()
             if self.new_process_button_main: self.new_process_button_main.hide()
             if hasattr(self, 'expand_button') and self.expand_button: self.expand_button.hide()
             return

        self.animation = QPropertyAnimation(self.config_panel, b"maximumWidth")
        self.animation.setDuration(300)
        self.animation.setStartValue(self.config_panel.maximumWidth())
        self.animation.setEndValue(target_width)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.animation.start()

        if hasattr(self, 'expand_button') and self.expand_button: self.expand_button.hide()
        if self.new_stop_button_main: self.new_stop_button_main.hide()
        if self.new_process_button_main: self.new_process_button_main.hide()

    def closeEvent(self, event):
        if hasattr(self, 'input_widget'):
            self.input_widget.detener_previsualizacion()
            self.input_widget.detener_segunda_previsualizacion()
        if self.procesando:
            self.detener_procesamiento()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, 'config_panel'): return

        if self.width() < 900 and not hasattr(self, 'auto_collapsed') and not self.procesando:
            if self.config_panel.maximumWidth() > 0 :
                self.collapse_config_panel()
                self.auto_collapsed = True
        elif self.width() >= 900 and hasattr(self, 'auto_collapsed') and self.auto_collapsed and not self.procesando:
            if self.config_panel.maximumWidth() == 0:
                self.expand_config_panel()
            if hasattr(self, 'auto_collapsed'): # Ensure attribute exists before deleting
                delattr(self, 'auto_collapsed')

if __name__ == '__main__':
    # This part is for standalone execution if needed, ensure your other widgets are also runnable or remove this.
    # For a real application, you would typically have a main script that imports and runs MainWindow.
    # Example:
    # from PyQt6.QtWidgets import QApplication
    # import sys
    # app = QApplication(sys.argv)
    # main_window = MainWindow()
    # main_window.show()
    # sys.exit(app.exec())
    pass