"""
Módulo principal para la interfaz de usuario de TrackerVidriera.
Implementa la ventana principal y todos los controles de la aplicación.
"""
import sys
import os
import traceback
import cv2
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStatusBar, QApplication, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QStandardPaths
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

from ui.widgets.input_config_widget import InputConfigWidget
from ui.widgets.model_config_widget import ModelConfigWidget
from ui.widgets.output_config_widget import OutputConfigWidget
from ui.widgets.serial_config_widget import SerialConfigWidget
from ui.widgets.video_display_widget import VideoDisplayWidget
from ui.widgets.action_buttons_widget import ActionButtonsWidget

from core.serial_manager import serial_manager

try:
    from core.tracking.video_output import VideoOutput
except ImportError:
    print("ADVERTENCIA: No se pudo importar 'VideoOutput' desde 'core.tracking.video_output'. La grabación de la segunda cámara NO funcionará.")
    class VideoOutput:
        def __init__(self): self.output_writer = None; self._output_path = "dummy_output.avi"; print("[DummyVO] Instancia creada.")
        def setup(self,p,c,f,s): print(f"[DummyVO] Setup: {p}");self._output_path=p;self.output_writer=True;return True
        def write_frame(self,fr): return True
        def close(self): print(f"[DummyVO] Close: {self._output_path}");self.output_writer=None;return True
        def get_output_info(self): return {"output_path":self._output_path}

try:
    from config.settings import settings
    from core.video_output import VideoOutputManager
except ImportError:
    print("Warning: Could not import 'settings' or 'VideoOutputManager'.")
    class DummySettings:
        def __init__(self):
            self.model_path="yolov8n.pt"; self.confidence_threshold=0.6; self.frames_espera=10
            self.output_path= str(Path.cwd() / "salida_procesada.avi")
            self.video_format = "XVID" # Formato unificado
            self.second_camera_output_path=str(Path.cwd() / "salida_cam2_crudo.avi")
            self.serial_port="COM3"; self.serial_baudrate=115200; self.serial_enabled=True
            self.input_type=0; self.video_path=None; self.camera_id=0
            self.second_camera_id=-1; self.config_panel_collapsed=False
        def save_settings(self): return True
        def load_settings(self): pass
    settings = DummySettings()

    class DummyVideoOutputManager:
        def setup_output(self, *args): return True
        def write_frame(self, *args): return True
        def release(self, *args): return True
        def get_output_info(self, *args): return {}
    VideoOutputManager = DummyVideoOutputManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TrackerVidriera")
        self.setMinimumSize(800, 600)
        self.procesando = False
        self.left_panel_target_width = 350
        self.video_output = VideoOutputManager()
        self.second_camera_raw_recorder = None
        self.is_recording_second_camera = False
        self._second_camera_frame_props = {}
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo")
        self.init_ui()
        self.showMaximized()
        self.load_settings_to_ui()
        QTimer.singleShot(0, lambda: self.toggle_input_type(self.input_widget.get_input_type()))
        self._update_main_processing_buttons_state()

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        header_layout = QHBoxLayout()
        title_label = QLabel("TrackerVidriera")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header_layout.addWidget(title_label); header_layout.addStretch()

        # Botón "Procesar en vivo" en el header
        self.header_process_button = QPushButton("Procesar en Vivo")
        self.header_process_button.setMinimumHeight(40)
        self.header_process_button.setStyleSheet("background-color: #2ecc71; color: white;") # Estilo verde
        self.header_process_button.clicked.connect(self.process_video)
        self.header_process_button.hide() # Inicialmente oculto
        header_layout.addWidget(self.header_process_button)

        # Botón "Stop" en el header
        self.header_stop_button = QPushButton("Stop") # Renombrado de new_stop_button_main
        self.header_stop_button.setMinimumHeight(40)
        self.header_stop_button.setStyleSheet("background-color: red; color: white;")
        self.header_stop_button.clicked.connect(self.detener_procesamiento)
        self.header_stop_button.hide()
        header_layout.addWidget(self.header_stop_button)

        main_layout.addLayout(header_layout)
        self.content_layout = QHBoxLayout()
        self.left_panel_widget = QWidget()
        self.left_panel_layout = QVBoxLayout(self.left_panel_widget)
        self.left_panel_layout.setContentsMargins(5,5,5,5)
        self.left_panel_layout.setSpacing(10)

        config_widgets_container = QWidget()
        config_layout_inside = QVBoxLayout(config_widgets_container)
        config_layout_inside.setSpacing(10)
        config_layout_inside.setContentsMargins(0,0,0,0)

        self.manual_collapse_button = QPushButton("⇦")
        self.manual_collapse_button.setFixedSize(30, 30)
        self.manual_collapse_button.setToolTip("Colapsar panel")
        self.manual_collapse_button.clicked.connect(self.collapse_config_panel)
        collapse_button_layout = QHBoxLayout()
        collapse_button_layout.addStretch(1)
        collapse_button_layout.addWidget(self.manual_collapse_button)
        config_layout_inside.addLayout(collapse_button_layout)

        self.input_widget = InputConfigWidget()
        self.model_widget = ModelConfigWidget()
        self.output_widget = OutputConfigWidget()
        self.serial_widget = SerialConfigWidget(serial_manager)

        config_layout_inside.addWidget(self.input_widget)
        config_layout_inside.addWidget(self.model_widget)
        config_layout_inside.addWidget(self.output_widget)
        config_layout_inside.addWidget(self.serial_widget)

        self.action_buttons = ActionButtonsWidget()

        self.left_panel_layout.addWidget(config_widgets_container)
        self.left_panel_layout.addStretch(1)
        self.left_panel_layout.addWidget(self.action_buttons)

        self.video_display = VideoDisplayWidget()

        self.connect_widget_signals()

        self.content_layout.addWidget(self.left_panel_widget, 0)
        self.content_layout.addWidget(self.video_display, 1)

        self.left_panel_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

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
        self.input_widget.second_frame_received.connect(self._handle_second_camera_frame_for_recording)
        self.input_widget.camera_selected.connect(self.on_main_camera_selected)
        self.input_widget.second_camera_selected.connect(self.on_second_camera_selected)
        self.model_widget.status_message.connect(self.show_status_message)
        self.serial_widget.status_message.connect(self.show_status_message)
        self.action_buttons.process_clicked.connect(self.process_video)
        self.action_buttons.stop_clicked.connect(self.detener_procesamiento)
        self.action_buttons.save_config_clicked.connect(self.save_settings_from_ui)

    def _update_main_processing_buttons_state(self):
        is_live_mode = self.input_widget.get_input_type() == 1
        main_cam_id = self.input_widget.get_selected_camera_id()
        can_process_live = is_live_mode and (main_cam_id is not None)
        can_process_file = not is_live_mode and bool(self.input_widget.get_video_path())

        # Botones en el panel de acciones
        self.action_buttons.set_processing_mode(self.procesando, is_live_mode)
        if not self.procesando:
            if is_live_mode:
                self.action_buttons.enable_process_button(enabled=can_process_live, text="Procesar en vivo")
            else:
                self.action_buttons.enable_process_button(enabled=can_process_file, text="Procesar video")

        # Actualizar botones del header (visibilidad y estado)
        self._update_header_buttons_visibility()


    def _update_header_buttons_visibility(self):
        """Controla la visibilidad y estado de los botones en el header."""
        panel_is_collapsed = (self.left_panel_widget.maximumWidth() == 0)
        is_live_mode = self.input_widget.get_input_type() == 1
        main_cam_id = self.input_widget.get_selected_camera_id()
        can_process_live_now = is_live_mode and (main_cam_id is not None)

        if panel_is_collapsed:
            if self.procesando:
                self.header_stop_button.show()
                self.header_stop_button.setEnabled(True)
                self.header_process_button.hide()
            else: # No procesando
                self.header_stop_button.hide()
                if is_live_mode:
                    self.header_process_button.show()
                    self.header_process_button.setEnabled(can_process_live_now)
                else: # Modo archivo, no mostrar botón de procesar en vivo en header
                    self.header_process_button.hide()
        else: # Panel expandido
            self.header_stop_button.hide()
            self.header_process_button.hide()

    def toggle_input_type(self, index):
        self._update_main_processing_buttons_state() # Esto ya llama a _update_header_buttons_visibility
        if self.is_recording_second_camera: self._stop_record_second_camera()
        is_camera_mode = (index == 1)
        if hasattr(self, 'output_widget'):
             self.output_widget.set_second_camera_output_visible(is_camera_mode)

    def on_video_file_selected(self, file_path):
        self._update_main_processing_buttons_state() # Esto ya llama a _update_header_buttons_visibility
        self.video_display.display_second_frame(None)

    def on_main_camera_selected(self, camera_id, camera_description):
        self.show_status_message(f"Cámara principal seleccionada: {camera_description}", 2000)
        self._update_main_processing_buttons_state() # Esto ya llama a _update_header_buttons_visibility

    def on_second_camera_selected(self, camera_id, camera_description):
        if camera_id != -1: self.show_status_message(f"Segunda cámara seleccionada: {camera_description}", 2000)
        else:
            self.show_status_message("Segunda cámara deshabilitada.", 2000)
            self.video_display.display_second_frame(None)
            if self.is_recording_second_camera: self._stop_record_second_camera()
        self._update_main_processing_buttons_state() # No afecta directamente a los botones del header, pero es bueno mantenerlo

    def show_status_message(self, message, timeout=0):
        self.status_bar.showMessage(message, timeout)

    def load_settings_to_ui(self):
        settings.load_settings()
        self.input_widget.set_all_settings({
            "input_type": getattr(settings, 'input_type', 0), "video_path": getattr(settings, 'video_path', None),
            "camera_id": getattr(settings, 'camera_id', 0), "second_camera_id": getattr(settings, 'second_camera_id', -1)})
        self.model_widget.set_model_path(getattr(settings, 'model_path', "yolov8n.pt"))
        self.model_widget.set_confidence(getattr(settings, 'confidence_threshold', 0.6))
        self.model_widget.set_frames_wait(getattr(settings, 'frames_espera', 10))

        self.output_widget.set_main_output_path(getattr(settings, 'output_path', str(Path.cwd() / "salida_procesada.avi")))
        default_sec_cam_path = str(Path.cwd() / "salida_cam2_crudo.avi")
        self.output_widget.set_second_cam_output_path(getattr(settings, 'second_camera_output_path', default_sec_cam_path))

        self.output_widget.set_video_format(getattr(settings, 'video_format', "XVID"))

        self.serial_widget.set_serial_port(getattr(settings, 'serial_port', "COM3"))
        self.serial_widget.set_baudrate(getattr(settings, 'serial_baudrate', 115200))
        self.serial_widget.set_serial_enabled(getattr(settings, 'serial_enabled', True))
        QTimer.singleShot(100, self._apply_panel_state)

    def _apply_panel_state(self):
        target_width_attr = 'left_panel_target_width'
        if not hasattr(self, target_width_attr) or getattr(self, target_width_attr) <= 0:
            current_width = self.left_panel_widget.width() if hasattr(self.left_panel_widget, 'width') else 0
            setattr(self, target_width_attr, current_width if current_width > 50 else 350)

        panel_should_be_collapsed = getattr(settings, 'config_panel_collapsed', False)

        if panel_should_be_collapsed:
            if self.left_panel_widget.maximumWidth() > 0 : self.collapse_config_panel(animate=False)
            elif hasattr(self, 'expand_button'): self.expand_button.show()
        else:
            if self.left_panel_widget.maximumWidth() == 0: self.expand_config_panel(animate=False)
            if hasattr(self, 'expand_button'): self.expand_button.hide()

        self._update_header_buttons_visibility() # Asegurar que los botones del header están correctos al inicio

    def save_settings_from_ui(self):
        input_settings_data = self.input_widget.get_all_settings()
        settings.input_type = input_settings_data.get("input_type")
        settings.video_path = input_settings_data.get("video_path")
        settings.camera_id = input_settings_data.get("camera_id")
        settings.second_camera_id = input_settings_data.get("second_camera_id")
        settings.model_path = self.model_widget.get_model_path()
        settings.confidence_threshold = self.model_widget.get_confidence()
        settings.frames_espera = self.model_widget.get_frames_wait()

        settings.output_path = self.output_widget.get_main_output_path()
        settings.second_camera_output_path = self.output_widget.get_second_cam_output_path()
        settings.video_format = self.output_widget.get_video_format()

        settings.serial_port = self.serial_widget.get_serial_port()
        settings.serial_baudrate = self.serial_widget.get_baudrate()
        settings.serial_enabled = self.serial_widget.is_serial_enabled()
        if hasattr(self, 'left_panel_widget'):
            settings.config_panel_collapsed = self.left_panel_widget.maximumWidth() == 0
        success = settings.save_settings()
        self.show_status_message("Configuración guardada." if success else "Error al guardar.", 3000)

    def process_video(self):
        try:
            from rastreo import (inicializar_modelo, detectar_personas, extraer_ids, actualizar_rastreo, dibujar_anotaciones)
        except ImportError: self.show_status_message("Error: Módulo 'rastreo.py' no encontrado.", 5000); return
        params = self._get_processing_parameters()
        if not params: self._update_main_processing_buttons_state(); return

        self.procesando = True
        self._update_main_processing_buttons_state() # Actualiza botones del panel de acciones
        # Si el panel está colapsado, _update_header_buttons_visibility (llamado desde el anterior) se encargará
        if self.left_panel_widget.maximumWidth() > 0: # Solo colapsar si está expandido
            self.collapse_config_panel()
        else: # Si ya está colapsado, solo actualizar botones del header
            self._update_header_buttons_visibility()

        self.show_status_message(f"Procesando: {params['video_path_display']}...", 0)
        if params['is_camera']: self._start_record_second_camera()
        try:
            model = inicializar_modelo(str(params['model_path']))
            cap, out, total_frames = self._setup_video_io(params)
            if not cap: self.detener_procesamiento(); return
            if not params['is_camera'] and not out: self.detener_procesamiento(); return
            self._process_video_with_tracking(model, cap, out, params, detectar_personas, extraer_ids, actualizar_rastreo, dibujar_anotaciones, total_frames)
            if cap: cap.release()
            if out: out.release()
            if self.procesando: self.show_status_message(f"Procesado. Guardado en: {params['output_path']}" if not params['is_camera'] else "Procesamiento en vivo finalizado.", 5000)
        except Exception as e: self.show_status_message(f"Error en procesamiento: {str(e)}", 5000); traceback.print_exc()
        finally: self.detener_procesamiento()

    def detener_procesamiento(self):
        self.procesando = False
        if self.is_recording_second_camera: self._stop_record_second_camera()
        self._update_main_processing_buttons_state() # Actualiza botones del panel de acciones
        if self.left_panel_widget.maximumWidth() == 0: # Si el panel estaba colapsado
            self._update_header_buttons_visibility() # Actualizar botones del header
        else: # Si estaba expandido, expandirlo (si no lo estaba ya)
             self.expand_config_panel()

        self.show_status_message("Procesamiento detenido.", 3000)

    def _start_record_second_camera(self):
        if not (self.input_widget.second_camera_thread and self.input_widget.second_camera_thread.isRunning() and self.input_widget.get_selected_second_camera_id() is not None):
            self.show_status_message("Segunda cámara no activa, no se grabará.", 2000); return
        cam_thread = self.input_widget.second_camera_thread
        if not cam_thread.cap or not cam_thread.cap.isOpened():
            self.show_status_message("Stream 2da cámara no disponible. Esperando primer frame...", 2000)
            self._second_camera_frame_props = {}; self.is_recording_second_camera = True; return
        fps = cam_thread.cap.get(cv2.CAP_PROP_FPS); width = int(cam_thread.cap.get(cv2.CAP_PROP_FRAME_WIDTH)); height = int(cam_thread.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if fps <= 0: fps = 20.0
        if width <= 0 or height <= 0:
            self.show_status_message("Dimensiones 2da cámara inválidas. Esperando primer frame...", 2000)
            self._second_camera_frame_props = {}; self.is_recording_second_camera = True; return
        self._second_camera_frame_props = {'fps': fps, 'width': width, 'height': height}
        self._initialize_second_camera_recorder()

    def _initialize_second_camera_recorder(self):
        if not all(self._second_camera_frame_props.get(k) for k in ['width', 'height', 'fps']):
            self.show_status_message("Error: Faltan props para grabar cámara móvil.", 5000); self.is_recording_second_camera = False
            if self.second_camera_raw_recorder: self.second_camera_raw_recorder.close(); self.second_camera_raw_recorder = None
            return
        w = self._second_camera_frame_props['width']; h = self._second_camera_frame_props['height']; fps = self._second_camera_frame_props['fps']

        output_path_str = self.output_widget.get_second_cam_output_path()
        video_format_str = self.output_widget.get_video_format()

        if not output_path_str or not video_format_str:
            self.show_status_message("Error: Ruta de salida o formato no configurados para 2da cámara.", 5000)
            self.is_recording_second_camera = False; return

        final_output_path = Path(output_path_str); output_dir = final_output_path.parent
        if not output_dir.exists():
            try: output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e: self.show_status_message(f"Error crear dir 2da cámara ({output_dir}): {e}", 5000); self.is_recording_second_camera = False; return

        self.second_camera_raw_recorder = VideoOutput()
        if self.second_camera_raw_recorder.setup(str(final_output_path), video_format_str, fps, (w, h)):
            self.is_recording_second_camera = True; self.show_status_message(f"Grabando cámara móvil en: {final_output_path}", 0)
        else:
            self.show_status_message(f"Error iniciar grabación 2da cámara ({final_output_path}).", 5000)
            self.second_camera_raw_recorder = None; self.is_recording_second_camera = False

    def _stop_record_second_camera(self):
        if self.second_camera_raw_recorder:
            info = self.second_camera_raw_recorder.get_output_info(); path = info.get('output_path', 'N/A')
            self.second_camera_raw_recorder.close(); self.show_status_message(f"Grabación cámara móvil detenida. Guardado en: {path}", 5000)
            self.second_camera_raw_recorder = None
        self.is_recording_second_camera = False; self._second_camera_frame_props = {}

    def _handle_second_camera_frame_for_recording(self, frame):
        if frame is None: return
        if self.is_recording_second_camera and not self.second_camera_raw_recorder:
            if not self._second_camera_frame_props.get('width'):
                h, w, _ = frame.shape; self._second_camera_frame_props.update({'width':w, 'height':h})
                fps_val = 20.0
                if self.input_widget.second_camera_thread and self.input_widget.second_camera_thread.cap and self.input_widget.second_camera_thread.cap.isOpened():
                    thread_fps = self.input_widget.second_camera_thread.cap.get(cv2.CAP_PROP_FPS)
                    if thread_fps > 0: fps_val = thread_fps
                self._second_camera_frame_props['fps'] = fps_val
                self.show_status_message("Props frame obtenidas. Iniciando grabador CM...", 1000); self._initialize_second_camera_recorder()
        if self.is_recording_second_camera and self.second_camera_raw_recorder and self.second_camera_raw_recorder.output_writer:
            try: self.second_camera_raw_recorder.write_frame(frame)
            except Exception as e: print(f"Error escribir frame 2da cámara: {e}"); self.show_status_message(f"Error escribiendo frame CM: {e}", 3000)

    def _get_processing_parameters(self):
        model_name = self.model_widget.get_model_path()
        confidence = self.model_widget.get_confidence()
        frames_espera = self.model_widget.get_frames_wait()

        output_path = self.output_widget.get_main_output_path()
        video_format = self.output_widget.get_video_format()

        is_camera = self.input_widget.get_input_type() == 1
        video_path_display = "Cámara en vivo"

        if is_camera:
            camera_id = self.input_widget.get_selected_camera_id()
            if camera_id is None: self.show_status_message("Error: Cámara principal no seleccionada.",3000);return None
            video_path = camera_id
            video_path_display = self.input_widget.get_selected_camera_description()
        else:
            video_path = self.input_widget.get_video_path()
            if not video_path: self.show_status_message("Error: No video seleccionado.",3000);return None
            video_path_display = Path(video_path).name; video_path = str(video_path)

        model_path_found = None
        base_path_for_models = None
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_path_for_models = Path(sys._MEIPASS)
        else:
            base_path_for_models = Path(__file__).resolve().parent.parent

        possible_paths = [
            base_path_for_models / "models" / model_name,
            base_path_for_models / model_name,
            Path.cwd() / "models" / model_name, Path.cwd() / model_name,
            Path(model_name)
        ]
        for path_attempt in possible_paths:
            try:
                resolved_path = path_attempt.resolve()
                if resolved_path.is_file(): model_path_found = resolved_path; print(f"Modelo encontrado en: {model_path_found}"); break
            except Exception: pass
        if model_path_found is None:
            self.show_status_message(f"Error: Modelo '{model_name}' no encontrado.", 5000)
            print(f"Debug: Modelo '{model_name}' no encontrado. Base path usado: {base_path_for_models}")
            return None

        return {
            'video_path': video_path, 'is_camera': is_camera, 'model_path': str(model_path_found),
            'confidence': confidence, 'frames_espera': frames_espera,
            'output_path': output_path,
            'codec': video_format,
            'video_path_display': video_path_display,
        }

    def _setup_video_io(self, params):
        cap,out,total_frames=None,None,0
        try:
            vid_src=params['video_path']; cap=cv2.VideoCapture(vid_src)
            if not cap.isOpened():
                self.show_status_message(f"Error: No se pudo abrir: {params['video_path_display']}",3000)
                return None,None,0

            total_frames=-1 if params['is_camera']else int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));fps=cap.get(cv2.CAP_PROP_FPS)
            if fps<=0:fps=30.0

            if w<=0 or h<=0:
                self.show_status_message(f"Error: Dimensiones inválidas {params['video_path_display']}",3000)
                if cap: cap.release()
                return None,None,0

            if not params['is_camera']or(params['is_camera']and params['output_path']):
                out_path_str=self.output_widget._ensure_valid_extension(params['output_path'], params['codec'])
                params['output_path']=out_path_str;fourcc=cv2.VideoWriter_fourcc(*params['codec']);out_dir=os.path.dirname(out_path_str)
                if out_dir and not os.path.exists(out_dir):os.makedirs(out_dir)

                if os.path.exists(out_path_str):
                    try: os.remove(out_path_str)
                    except Exception as e:
                        self.show_status_message(f"No se pudo eliminar {out_path_str}:{e}",3000)
                        if cap: cap.release()
                        return None,None,0

                out=cv2.VideoWriter(out_path_str,fourcc,fps,(w,h))
                if not out.isOpened():
                    self.show_status_message(f"Error crear salida {out_path_str}.Intentando H264...",3000)
                    if params['codec'].upper()=="MP4V"and os.path.splitext(out_path_str)[1].lower()==".mp4":
                        f_alt=cv2.VideoWriter_fourcc(*"H264")
                        o_alt=cv2.VideoWriter(out_path_str,f_alt,fps,(w,h))
                        if not o_alt.isOpened():
                            self.show_status_message(f"Error con H264 en {out_path_str}.",3000)
                            if cap: cap.release()
                            return None,None,0
                        out=o_alt
                    else:
                        if cap:cap.release()
                        return None,None,0
            return cap,out,total_frames
        except Exception as e:
            self.show_status_message(f"Error crítico en _setup_video_io:{str(e)}",5000);traceback.print_exc()
            if cap:cap.release()
            if'out'in locals()and out and out.isOpened():out.release()
            return None,None,0

    def _process_video_with_tracking(self,model,cap,out,params,detect_p,extract_ids,update_track,draw_anno,total_frames):
        p_id,r_id,l_coords,f_lost=None,None,None,0;ids_g=set();f_count=0;ctrl_servo=params['is_camera']
        while self.procesando:
            ret,frame=cap.read()
            if not ret:self.show_status_message("Fin stream principal.",0 if params['is_camera']else 2000);break
            f_count+=1
            if not params['is_camera']and total_frames>0:self.show_status_message(f"Procesando:{int((f_count/total_frames)*100)}%",0)
            elif params['is_camera']and f_count%30==0:self.show_status_message(f"Frames procesados(vivo):{f_count}",0)
            res=detect_p(model,frame,params['confidence'])
            if res is None:
                if params['is_camera']:self.video_display.display_frame(frame)
                if out:out.write(frame)
                QApplication.processEvents();continue
            boxes=res.boxes;ids_frame=extract_ids(boxes)
            p_id,r_id,re_coords,f_lost=update_track(p_id,r_id,ids_frame,f_lost,params['frames_espera'])
            if re_coords:l_coords=None
            anno_yolo=res.plot()
            anno_final,l_coords=draw_anno(anno_yolo,boxes,r_id,l_coords,ids_g,frame.shape[1],controlar_servo=ctrl_servo)
            if self.video_display:self.video_display.display_frame(anno_final)
            if out:out.write(anno_final)
            QApplication.processEvents()

    def toggle_config_panel(self):
        is_currently_collapsed = (self.left_panel_widget.maximumWidth() == 0)
        if not is_currently_collapsed:
            self.collapse_config_panel()
        else:
            self.expand_config_panel()
        # No guardar settings aquí, collapse/expand se encargan de la visibilidad de botones del header
        # y el estado de 'settings.config_panel_collapsed' se guarda al presionar "Guardar Configuración"

    def collapse_config_panel(self, animate=True): # Añadido parámetro animate
        current_width = self.left_panel_widget.width()
        if current_width > 0 and self.left_panel_widget.maximumWidth() > 0 :
            self.left_panel_target_width = current_width

        if animate:
            self.animation = QPropertyAnimation(self.left_panel_widget, b"maximumWidth")
            self.animation.setDuration(300)
            self.animation.setStartValue(current_width if current_width > 0 else getattr(self, 'left_panel_target_width', 350))
            self.animation.setEndValue(0)
            self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.animation.finished.connect(self._update_header_buttons_visibility) # Actualizar botones al finalizar
            self.animation.start()
        else:
            self.left_panel_widget.setMaximumWidth(0)
            self._update_header_buttons_visibility() # Actualizar botones inmediatamente

        if not hasattr(self, 'expand_button'):
            self.expand_button = QPushButton(">"); self.expand_button.setFixedSize(20,60)
            self.expand_button.clicked.connect(self.expand_config_panel); self.expand_button.setToolTip("Expandir (Ctrl+B)")
            self.expand_button.setStyleSheet("QPushButton{background-color:#f0f0f0;border:1px solid #ccc;border-left:none;border-top-right-radius:10px;border-bottom-right-radius:10px} QPushButton:hover{background-color:#e0e0e0}")
            self.content_layout.insertWidget(0, self.expand_button, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.expand_button.show()
        settings.config_panel_collapsed = True # Actualizar estado para guardado

    def expand_config_panel(self, animate=True): # Añadido parámetro animate
        target_width = getattr(self, 'left_panel_target_width', 350)
        if target_width <= 0: target_width = 350

        if animate:
            self.animation = QPropertyAnimation(self.left_panel_widget, b"maximumWidth")
            self.animation.setDuration(300)
            self.animation.setStartValue(self.left_panel_widget.maximumWidth())
            self.animation.setEndValue(target_width)
            self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.animation.finished.connect(self._update_header_buttons_visibility) # Actualizar botones al finalizar
            self.animation.start()
        else:
            self.left_panel_widget.setMaximumWidth(target_width)
            self._update_header_buttons_visibility() # Actualizar botones inmediatamente

        if hasattr(self, 'expand_button'): self.expand_button.hide()
        settings.config_panel_collapsed = False # Actualizar estado para guardado

    def closeEvent(self, event):
        self.input_widget.detener_previsualizacion(); self.input_widget.detener_segunda_previsualizacion()
        if self.procesando : self.detener_procesamiento()
        elif self.is_recording_second_camera: self._stop_record_second_camera()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() < 900 and not hasattr(self, 'auto_collapsed') and not self.procesando:
            if self.left_panel_widget.maximumWidth() > 0 :
                self.collapse_config_panel()
                self.auto_collapsed = True
        elif self.width() >= 900 and hasattr(self, 'auto_collapsed') and not self.procesando:
            if self.left_panel_widget.maximumWidth() == 0:
                self.expand_config_panel()
            delattr(self, 'auto_collapsed')