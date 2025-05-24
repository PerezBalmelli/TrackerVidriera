"""
Módulo para el thread de procesamiento de video en la aplicación TrackerVidriera.
"""
import logging
import cv2
import numpy as np
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

# Asumiendo que serial_manager y PersonTrackingManager están accesibles
# Si PersonTrackingManager no está en un módulo importable directamente,
# necesitarás pasarlo como argumento o asegurarte de que es accesible.
from .serial_manager import serial_manager  # Assuming serial_manager is in the same 'core' directory

logger = logging.getLogger(__name__)


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
        self.person_tracker = person_tracker  # Reference to the existing manager
        self.serial_widget = serial_widget_ref  # To check if serial is enabled for servo
        self.running = False
        self.cap_main = None
        self.cap_second = None
        self.out_main = None
        self.out_mobile = None

    def _setup_io_in_thread(self):
        try:
            # Main Source
            video_path_cv = int(self.params['video_path']) if self.params['is_camera'] else str(
                self.params['video_path'])
            self.cap_main = cv2.VideoCapture(video_path_cv)
            if not self.cap_main.isOpened():
                raise IOError(f"Error: No se pudo abrir fuente principal {self.params['video_path_display']}")

            main_width = int(self.cap_main.get(cv2.CAP_PROP_FRAME_WIDTH))
            main_height = int(self.cap_main.get(cv2.CAP_PROP_FRAME_HEIGHT))
            main_fps = self.cap_main.get(cv2.CAP_PROP_FPS)
            if main_fps <= 0: main_fps = 30.0  # Default

            # Secondary Source (if applicable)
            if 'second_camera_id' in self.params and self.params['second_camera_id'] is not None:
                second_video_path_cv = int(self.params['second_camera_id'])
                self.cap_second = cv2.VideoCapture(second_video_path_cv)
                if not self.cap_second.isOpened():
                    logger.warning(
                        f"Advertencia: No se pudo abrir la segunda cámara {self.params.get('second_camera_display', '')}.")
                    self.cap_second = None  # Ensure it's None if not opened

            # Main Output Writer
            if self.params.get('save_main') and self.params.get('output_path'):
                main_output_dir = Path(self.params['output_path']).parent
                main_output_dir.mkdir(parents=True, exist_ok=True)
                main_fourcc = cv2.VideoWriter_fourcc(*self.params['codec'])
                self.out_main = cv2.VideoWriter(str(self.params['output_path']), main_fourcc, main_fps,
                                                (main_width, main_height))
                if not self.out_main.isOpened():
                    logger.error(f"Error al crear archivo principal en {self.params['output_path']}")
                    self.out_main = None  # Ensure it's None

            # Mobile Output Writer
            if self.params.get('save_mobile') and self.params.get(
                    'mobile_output_path') and self.cap_second and self.cap_second.isOpened():
                mobile_output_dir = Path(self.params['mobile_output_path']).parent
                mobile_output_dir.mkdir(parents=True, exist_ok=True)
                mobile_fourcc = cv2.VideoWriter_fourcc(*self.params['mobile_codec'])

                mobile_width = int(self.cap_second.get(cv2.CAP_PROP_FRAME_WIDTH))
                mobile_height = int(self.cap_second.get(cv2.CAP_PROP_FRAME_HEIGHT))
                mobile_fps_cam = self.cap_second.get(cv2.CAP_PROP_FPS)
                mobile_fps = mobile_fps_cam if mobile_fps_cam > 0 else main_fps

                if mobile_width > 0 and mobile_height > 0:
                    self.out_mobile = cv2.VideoWriter(str(self.params['mobile_output_path']), mobile_fourcc, mobile_fps,
                                                      (mobile_width, mobile_height))
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
            self._release_resources()  # Clean up if setup fails
            return -2  # Indicate setup failure

    def run(self):
        self.running = True
        logger.info("Thread de procesamiento de video iniciado.")

        total_frames = self._setup_io_in_thread()
        if total_frames == -2:  # Setup failed critically
            self.running = False
            logger.error("Fallo en setup I/O del thread. Thread terminado.")
            # error_occurred signal already emitted by _setup_io_in_thread
            return

        frame_count = 0
        primer_id, rastreo_id, ultima_coords, frames_perdidos = None, None, None, 0
        ids_globales = set()
        # Check serial_widget directly for current state, as params might be stale if user changed UI
        controlar_servo = self.params['is_camera'] and self.serial_widget.is_serial_enabled()

        if controlar_servo:  # Attempt to connect serial if it's supposed to be used
            s_port = self.serial_widget.get_serial_port()  # Get current port from widget
            s_baud = self.serial_widget.get_baudrate()  # Get current baudrate
            if s_port and serial_manager.connect(s_port, s_baud):  # Use global serial_manager
                logger.info(f"Comunicación serial conectada en thread para {s_port}@{s_baud}")
            else:
                logger.warning(
                    f"No se pudo conectar serial en thread para {s_port}@{s_baud}. Control servo desactivado.")
                controlar_servo = False  # Disable servo if connection fails

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
                        second_frame_for_display = temp_second_frame.copy()
                        if self.out_mobile and self.params.get('save_mobile'):
                            second_frame_for_saving = temp_second_frame

                frame_count += 1
                progress_text = ""
                if not self.params['is_camera'] and total_frames > 0:
                    progress = int((frame_count / total_frames) * 100)
                    progress_text = f"Procesando video: {progress}% (Frame {frame_count}/{total_frames})"
                elif self.params['is_camera']:
                    progress_text = f"Procesando en vivo: Frame {frame_count}"

                if frame_count % 15 == 0:
                    self.progress_update.emit(frame_count, total_frames, progress_text)

                annotated_frame_main = frame_main.copy()
                try:
                    result = self.person_tracker.detectar_personas(frame_main, self.params['confidence'])
                    if result and hasattr(result, 'boxes') and result.boxes is not None and len(result.boxes) > 0:
                        boxes = result.boxes
                        ids_esta_frame = self.person_tracker.extraer_ids(boxes)
                        primer_id, rastreo_id, reiniciar_coords, frames_perdidos = self.person_tracker.actualizar_rastreo(
                            primer_id, rastreo_id, ids_esta_frame, frames_perdidos, self.params['frames_espera']
                        )
                        if reiniciar_coords: ultima_coords = None

                        plot_frame = result.plot()
                        if plot_frame is not None and isinstance(plot_frame, np.ndarray):
                            annotated_frame_main = plot_frame

                        annotated_frame_main, ultima_coords = self.person_tracker.dibujar_anotaciones(
                            annotated_frame_main, boxes, rastreo_id, ultima_coords, ids_globales,
                            frame_main.shape[1], controlar_servo=controlar_servo
                        )
                except Exception as e_track:
                    logger.error(f"Error durante detección/tracking: {e_track}", exc_info=True)

                self.processed_frame.emit(annotated_frame_main, second_frame_for_display)

                if self.out_main and self.params.get('save_main'):
                    self.out_main.write(annotated_frame_main)

                if self.out_mobile and self.params.get('save_mobile') and second_frame_for_saving is not None:
                    self.out_mobile.write(second_frame_for_saving)

            if not self.running:
                logger.info("Procesamiento detenido por el usuario (hilo).")
                self.processing_finished.emit("Procesamiento detenido por el usuario.")
            else:
                logger.info("Procesamiento de video finalizado (hilo).")
                output_msg = "Procesamiento finalizado."
                if not self.params['is_camera']:
                    saved_files = []
                    if self.params.get('save_main') and self.out_main: saved_files.append(self.params['output_path'])
                    if self.params.get('save_mobile') and self.out_mobile: saved_files.append(
                        self.params['mobile_output_path'])
                    if saved_files:
                        output_msg = f"Procesado. Guardado en: {', '.join(saved_files)}"
                    else:
                        output_msg = "Procesado. No se configuró ninguna salida de archivo."
                self.processing_finished.emit(output_msg)

        except Exception as e:
            logger.error(f"Error mayor en el thread de procesamiento de video: {e}", exc_info=True)
            self.error_occurred.emit(f"Error en procesamiento (hilo): {str(e)}")
        finally:
            self._release_resources()
            if controlar_servo:  # Disconnect serial if thread connected it
                serial_manager.disconnect()
            logger.info("Thread de procesamiento de video terminado y recursos liberados.")

    def _release_resources(self):
        if self.cap_main: self.cap_main.release()
        if self.cap_second: self.cap_second.release()
        if self.out_main: self.out_main.release()
        if self.out_mobile: self.out_mobile.release()
        self.cap_main, self.cap_second, self.out_main, self.out_mobile = None, None, None, None

    def stop(self):
        logger.info("Solicitando detención del thread de procesamiento de video...")
        self.running = False