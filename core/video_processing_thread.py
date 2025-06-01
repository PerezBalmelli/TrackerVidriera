"""
Módulo para el thread de procesamiento de video en la aplicación TrackerVidriera.
"""
import logging
import cv2
import numpy as np
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

import yt_dlp # Importar yt_dlp directamente

from .serial_manager import serial_manager
try:
    from .person_tracking_manager import PersonTrackingManager
except ImportError:
    # Fallback si la importación relativa no funciona
    logging.warning("No se pudo importar PersonTrackingManager con importación relativa. Usando Dummy.")
    class DummyPersonTrackingManager:
        def inicializar_modelo(self, model_path): pass # Añadido para consistencia
        def detectar_personas(self, frame, confidence): return None
        def extraer_ids(self, boxes): return []
        def actualizar_rastreo(self, *args): return None, None, False, 0
        def dibujar_anotaciones(self, *args, **kwargs): return args[0], None
    PersonTrackingManager = DummyPersonTrackingManager
    # logging.error("Usando DummyPersonTrackingManager ya que PersonTrackingManager no pudo ser importado.") # Log más discreto

logger = logging.getLogger(__name__)

class VideoProcessingThread(QThread):
    processed_frame = pyqtSignal(object, object)
    progress_update = pyqtSignal(int, int, str)
    processing_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    person_ids_detected = pyqtSignal(list, int, bool)  # Lista de IDs detectados, ID rastreado, y bool indicando cambio auto
    def __init__(self, processing_params, person_tracker_ref, serial_widget_ref, parent=None):
        super().__init__(parent)
        self.params = processing_params
        self.person_tracker = person_tracker_ref
        self.serial_widget = serial_widget_ref
        self.running = False
        self.cap_main = None
        self.cap_second = None
        self.out_main = None
        self.out_mobile = None

    def set_target_person_id(self, target_id: int):
        """
        Establece el ID de la persona a rastrear.
        
        Args:
            target_id (int): ID de la persona a seguir
        """
        if self.person_tracker and hasattr(self.person_tracker, 'set_target_person_id'):
            self.person_tracker.set_target_person_id(target_id)
            logger.info(f"ID objetivo establecido desde thread: {target_id}")

    def _get_youtube_stream_url_with_ytdlp(self, youtube_url):
        # Opciones para yt-dlp:
        # Queremos la mejor calidad de video que OpenCV pueda manejar, preferiblemente mp4,
        # y hasta una resolución razonable (ej. 1080p) para no sobrecargar.
        # 'bestvideo[ext=mp4][height<=?1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=?1080]/bestvideo[height<=?1080]+bestaudio/best[height<=?1080]/best'
        # es una cadena de formato común. Para OpenCV, a menudo solo necesitamos la URL del video.
        # Si yt-dlp devuelve un formato que combina video y audio, mejor. Si no, solo video.
        ydl_opts = {
            'format': 'best[ext=mp4][height<=?1080]/best[ext=webm][height<=?1080]/bestvideo[height<=?1080]/best',
            'quiet': True,
            'noplaylist': True, # importante si pasas una URL de playlist por error
            # 'verbose': True, # Descomenta para depuración si tienes problemas con yt-dlp
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.debug(f"yt-dlp: Extrayendo información para {youtube_url} con opciones: {ydl_opts}")
                info_dict = ydl.extract_info(youtube_url, download=False)

                stream_url = None
                if 'url' in info_dict: # A menudo, el formato solicitado directamente pone la URL aquí
                    stream_url = info_dict['url']
                elif 'requested_formats' in info_dict and info_dict['requested_formats']: # Si se solicitaron múltiples formatos
                    stream_url = info_dict['requested_formats'][0]['url'] # Tomar el primero de los solicitados
                elif 'formats' in info_dict: # Buscar en la lista de todos los formatos como fallback
                    for f_info in reversed(info_dict['formats']): # Los mejores suelen estar al final de la lista
                        if f_info.get('url') and f_info.get('vcodec') != 'none': # Necesitamos un stream de video válido
                            logger.info(f"yt-dlp: Usando URL del stream desde 'formats' (fallback): {f_info.get('format_note', '')} - {f_info.get('ext', '')}")
                            stream_url = f_info['url']
                            break

                if stream_url:
                    logger.info(f"yt-dlp: URL de stream obtenida: {stream_url[:100]}...") # Loguea solo parte de la URL
                    return stream_url
                else:
                    # Loguea más información si no se encontró la URL para ayudar a depurar
                    logger.error(f"yt-dlp: No se encontró una URL de stream utilizable para {youtube_url}. Info_dict keys: {list(info_dict.keys())}")
                    # Puedes loguear info_dict completo si es pequeño, o partes específicas:
                    # logger.debug(f"yt-dlp: Info_dict completo: {info_dict}")
                    raise IOError(f"yt-dlp no pudo encontrar una URL de stream para {youtube_url}")

        except yt_dlp.utils.DownloadError as e_dl:
            logger.error(f"yt-dlp: Error de descarga/extracción para '{youtube_url}': {e_dl}")
            # Personaliza los mensajes de error basados en la excepción de yt-dlp
            if "Unsupported URL" in str(e_dl):
                raise IOError(f"URL de YouTube no soportada por yt-dlp: {youtube_url}")
            elif "Video unavailable" in str(e_dl) or "Private video" in str(e_dl) or "This video is unavailable" in str(e_dl):
                raise IOError(f"Video de YouTube no disponible/privado: {youtube_url}")
            else:
                raise IOError(f"Error de yt-dlp al procesar URL '{youtube_url}': {str(e_dl)}")
        except Exception as e: # Captura otras excepciones inesperadas durante el proceso
            logger.error(f"yt-dlp: Excepción genérica al obtener URL para '{youtube_url}': {e}", exc_info=True)
            raise IOError(f"Error inesperado de yt-dlp con URL '{youtube_url}': {str(e)}")

    def _setup_io_in_thread(self):
        try:
            video_path_cv = None
            is_youtube_stream = self.params.get('is_youtube', False)

            if is_youtube_stream:
                youtube_url_original = self.params['video_path']
                logger.info(f"Intentando obtener stream para URL de YouTube con yt-dlp: {youtube_url_original}")
                video_path_cv = self._get_youtube_stream_url_with_ytdlp(youtube_url_original)
                # La función _get_youtube_stream_url_with_ytdlp ya lanza IOError si falla

            elif self.params['is_camera']:
                video_path_cv = int(self.params['video_path'])
            else: # File
                video_path_cv = str(self.params['video_path'])

            self.cap_main = cv2.VideoCapture(video_path_cv)
            if not self.cap_main.isOpened():
                display_path = self.params.get('video_path_display', str(self.params.get('video_path', 'N/A')))
                raise IOError(f"Error: No se pudo abrir fuente principal {display_path} (OpenCV)")

            main_width = int(self.cap_main.get(cv2.CAP_PROP_FRAME_WIDTH))
            main_height = int(self.cap_main.get(cv2.CAP_PROP_FRAME_HEIGHT))
            main_fps = self.cap_main.get(cv2.CAP_PROP_FPS)

            if main_fps <= 0:
                logger.warning(f"FPS de fuente principal reportado como {main_fps}. Usando 30 FPS por defecto.")
                main_fps = 30.0
            if main_width == 0 or main_height == 0: # Verifica dimensiones válidas
                self.cap_main.release() # Libera el recurso si está mal
                raise IOError(f"Fuente principal {self.params.get('video_path_display', '')} devolvió dimensiones inválidas ({main_width}x{main_height}) después de abrir.")

            # Configuración de segunda cámara (si aplica)
            if 'second_camera_id' in self.params and self.params['second_camera_id'] is not None:
                second_video_path_cv = int(self.params['second_camera_id'])
                self.cap_second = cv2.VideoCapture(second_video_path_cv)
                if not self.cap_second.isOpened():
                    logger.warning(f"Advertencia: No se pudo abrir la segunda cámara {self.params.get('second_camera_display', '')}.")
                    self.cap_second = None
                else:
                    s_width = int(self.cap_second.get(cv2.CAP_PROP_FRAME_WIDTH))
                    s_height = int(self.cap_second.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    if s_width == 0 or s_height == 0:
                        logger.warning(f"Segunda cámara {self.params.get('second_camera_display', '')} devolvió dimensiones inválidas ({s_width}x{s_height}). Deshabilitándola.")
                        self.cap_second.release()
                        self.cap_second = None

            # Configuración de VideoWriter (si aplica)
            if self.params.get('save_main') and self.params.get('output_path'):
                main_output_dir = Path(self.params['output_path']).parent
                main_output_dir.mkdir(parents=True, exist_ok=True)
                main_fourcc = cv2.VideoWriter_fourcc(*self.params['codec'])
                self.out_main = cv2.VideoWriter(str(self.params['output_path']), main_fourcc, main_fps, (main_width, main_height))
                if not self.out_main.isOpened():
                    logger.error(f"Error al crear archivo principal en {self.params['output_path']}")
                    self.out_main = None

            if self.params.get('save_mobile') and self.params.get('mobile_output_path') and self.cap_second and self.cap_second.isOpened():
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

            total_frames = -1 # Default para streams o cámaras
            if not self.params['is_camera'] and not is_youtube_stream: # Solo para archivos locales
                total_frames = int(self.cap_main.get(cv2.CAP_PROP_FRAME_COUNT))
            return total_frames

        except yt_dlp.utils.DownloadError as e_ytdlp_setup:
            self.error_occurred.emit(f"Error de yt-dlp en setup: {str(e_ytdlp_setup)}")
            self._release_resources()
            return -2 # Indica fallo crítico en setup
        except IOError as e_io_setup: # Captura IOErrors lanzados explícitamente
             self.error_occurred.emit(f"Error de I/O en setup: {str(e_io_setup)}")
             self._release_resources()
             return -2
        except Exception as e_general_setup: # Captura general para otros errores de setup
            self.error_occurred.emit(f"Error general en setup I/O: {str(e_general_setup)}")
            self._release_resources()
            return -2

    
    def run(self):
        self.running = True
        logger.info("Thread de procesamiento de video iniciado.")

        total_frames = self._setup_io_in_thread()
        if total_frames == -2: # Chequea el código de error de _setup_io_in_thread
            self.running = False
            logger.error("Fallo en setup I/O del thread. Thread terminado porque el setup falló.")
            # La señal error_occurred ya fue emitida por _setup_io_in_thread
            return

        frame_count = 0
        primer_id, rastreo_id, ultima_coords, frames_perdidos = None, None, None, 0
        ids_globales = set()

        controlar_servo = self.params['is_camera'] and self.serial_widget.is_serial_enabled()

        if controlar_servo:
            s_port = self.serial_widget.get_serial_port()
            s_baud = self.serial_widget.get_baudrate()
            if s_port and serial_manager.connect(s_port, s_baud):
                logger.info(f"Comunicación serial conectada en thread para {s_port}@{s_baud}")
            else:
                logger.warning(f"No se pudo conectar serial en thread para {s_port}@{s_baud}. Control servo desactivado.")
                controlar_servo = False
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
                is_youtube_stream = self.params.get('is_youtube', False)

                if not self.params['is_camera'] and not is_youtube_stream and total_frames > 0: # File
                    progress = int((frame_count / total_frames) * 100)
                    progress_text = f"Procesando video: {progress}% (Frame {frame_count}/{total_frames})"
                elif self.params['is_camera']: # Camera
                    progress_text = f"Procesando en vivo (Cámara): Frame {frame_count}"
                elif is_youtube_stream: # YouTube
                    progress_text = f"Procesando Stream YouTube: Frame {frame_count}"

                if frame_count % 15 == 0 or (total_frames > 0 and frame_count == total_frames) :
                    self.progress_update.emit(frame_count, total_frames, progress_text)

                annotated_frame_main = frame_main.copy()
                boxes = None
                try:
                    if self.person_tracker and hasattr(self.person_tracker, 'detectar_personas'):
                        result = self.person_tracker.detectar_personas(frame_main, self.params['confidence'])
                        if result and hasattr(result, 'boxes') and result.boxes is not None and len(result.boxes) > 0:
                            boxes = result.boxes
                            ids_esta_frame = self.person_tracker.extraer_ids(boxes)
                            
                            # Actualizar ids_globales con los IDs detectados en este frame
                            ids_globales.update(ids_esta_frame)
                            primer_id, rastreo_id, reiniciar_coords, frames_perdidos = self.person_tracker.actualizar_rastreo(
                                primer_id, rastreo_id, ids_esta_frame, frames_perdidos, self.params['frames_espera']
                            )
                            if reiniciar_coords: ultima_coords = None
                            
                            # Obtener el ID que se está rastreando actualmente usando el método auxiliar
                            current_tracking_id = self.person_tracker.get_current_tracking_id()
                            
                            # Preparar lista de IDs para el widget (solo los visibles en este frame)
                            ids_para_widget = list(ids_esta_frame)
                            
                            # Emitir IDs para el widget de selección, con el indicador reiniciar_coords que muestra si hubo cambio de ID
                            self.person_ids_detected.emit(ids_para_widget, current_tracking_id if current_tracking_id else -1, reiniciar_coords)
                            
                            plot_frame = result.plot()
                            if plot_frame is not None and isinstance(plot_frame, np.ndarray):
                                annotated_frame_main = plot_frame
                            annotated_frame_main, ultima_coords = self.person_tracker.dibujar_anotaciones(
                                annotated_frame_main, boxes, rastreo_id, ultima_coords, ids_globales,
                                frame_main.shape[1], controlar_servo=controlar_servo
                            )
                        
                        else:                            # No hay detecciones en este frame
                            # Si estamos rastreando un ID, incluirlo en la lista para mantener la selección
                            ids_para_widget = []
                            # Obtener el ID que se está rastreando actualmente (aunque no sea visible)
                            current_tracking_id = self.person_tracker.get_current_tracking_id()
                            # Emitir una lista vacía de IDs visibles, pero incluir el ID de rastreo actual
                            self.person_ids_detected.emit(ids_para_widget, current_tracking_id if current_tracking_id else -1, False)
                    else:
                        logger.warning("Person tracker no está disponible. Saltando detección/tracking.")
                except Exception as e_track:
                    logger.error(f"Error durante detección/tracking: {e_track}", exc_info=True)

                    # --- ZOOM VIRTUAL: activar en modos archivo o youtube
                is_virtual_mobile = (not self.params['is_camera'])  # True en archivo o YouTube
                if is_virtual_mobile:
                    # Calcula el zoom virtual solo si hay boxes y un id a seguir
                    zoom_frame = None
                    if boxes is not None and rastreo_id is not None:
                        zoom_frame = obtener_crop_zoom(frame_main, boxes, rastreo_id, zoom_factor=2.0)
                    # Si no hay persona, opcional: mostrar None o el frame completo
                    second_frame_for_display = zoom_frame if zoom_frame is not None else None
                    second_frame_for_saving = zoom_frame if zoom_frame is not None else None
                else:
                    # MANTENER LOGICA PARA CAMARA FISICA (DOS CAMARAS)
                    if self.cap_second and self.cap_second.isOpened():
                        ret_second, temp_second_frame = self.cap_second.read()
                        if ret_second:
                            second_frame_for_display = temp_second_frame.copy()
                            if self.out_mobile and self.params.get('save_mobile'):
                                second_frame_for_saving = temp_second_frame

                self.processed_frame.emit(annotated_frame_main, second_frame_for_display)

                if self.out_main and self.params.get('save_main'):
                    self.out_main.write(annotated_frame_main)

                if self.out_mobile and self.params.get('save_mobile') and second_frame_for_saving is not None:
                    self.out_mobile.write(second_frame_for_saving)

            if not self.running and (total_frames == -1 or (total_frames > 0 and frame_count < total_frames)):
                logger.info("Procesamiento detenido por el usuario (hilo).")
                self.processing_finished.emit("Procesamiento detenido por el usuario.")
            else:
                logger.info("Procesamiento de video finalizado (hilo).")
                output_msg = "Procesamiento finalizado."
                if not self.params['is_camera']: # Para archivos o streams de YouTube
                    saved_files = []
                    if self.params.get('save_main') and self.out_main: saved_files.append(self.params['output_path'])
                    if self.params.get('save_mobile') and self.out_mobile: saved_files.append(self.params['mobile_output_path'])

                    if saved_files:
                        output_msg = f"Procesado. Guardado en: {', '.join(saved_files)}"
                    else: # No se guardaron archivos
                        if self.params.get('is_youtube', False):
                             output_msg = "Procesamiento de Stream YouTube finalizado. No se configuró salida de archivo."
                        else: # Era un archivo pero no se seleccionó guardar (esto no debería pasar si la UI lo valida)
                             output_msg = "Procesado. No se configuró ninguna salida de archivo."
                self.processing_finished.emit(output_msg)

        except Exception as e:
            logger.error(f"Error mayor en el thread de procesamiento de video: {e}", exc_info=True)
            self.error_occurred.emit(f"Error en procesamiento (hilo): {str(e)}")
        finally:
            self._release_resources()
            if controlar_servo:
                serial_manager.disconnect()
            logger.info("Thread de procesamiento de video terminado y recursos liberados.")

    def _release_resources(self):
        logger.debug("Liberando recursos del thread de video...")
        if self.cap_main:
            logger.debug("Liberando cap_main.")
            self.cap_main.release()
        if self.cap_second:
            logger.debug("Liberando cap_second.")
            self.cap_second.release()
        if self.out_main:
            logger.debug("Liberando out_main.")
            self.out_main.release()
        if self.out_mobile:
            logger.debug("Liberando out_mobile.")
            self.out_mobile.release()
        self.cap_main, self.cap_second, self.out_main, self.out_mobile = None, None, None, None
        logger.debug("Recursos del thread de video liberados.")

    def stop(self):
        logger.info("Solicitando detención del thread de procesamiento de video...")
        self.running = False

def obtener_crop_zoom(frame, boxes, rastreo_id, zoom_factor=2.0):
    """
    Recorta y amplía la zona donde se encuentra la persona rastreada (rastreo_id).
    Retorna el frame zoomed (al tamaño original) o None si ID no se detecta.
    """
    if boxes is not None and boxes.id is not None and boxes.xyxy is not None:
        for i, id_tensor in enumerate(boxes.id):
            id_ = int(id_tensor.item())
            if id_ == rastreo_id and i < len(boxes.xyxy):
                x1, y1, x2, y2 = map(int, boxes.xyxy[i].tolist())
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                w = x2 - x1
                h = y2 - y1
                crop_w = int(w * zoom_factor)
                crop_h = int(h * zoom_factor)
                x_start = max(0, cx - crop_w // 2)
                x_end = min(frame.shape[1], cx + crop_w // 2)
                y_start = max(0, cy - crop_h // 2)
                y_end = min(frame.shape[0], cy + crop_h // 2)
                crop = frame[y_start:y_end, x_start:x_end]
                crop_resized = cv2.resize(
                    crop, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR
                )
                return crop_resized
    return None        