"""
Módulo principal de rastreo de personas.
Integración de todas las clases y componentes para facilitar el uso.
"""
from .tracking.model_manager import ModelManager
from .tracking.person_detector import PersonDetector
from .tracking.object_tracker import ObjectTracker
from .tracking.video_processor import VideoProcessor
from .visualization.annotation import FrameAnnotator
from .hardware.servo_controller import ServoController


class PersonTrackingManager:
    """
    Clase principal que integra todos los componentes para el rastreo de personas.
    Proporciona una interfaz unificada para usar el sistema completo.
    """
    
    def __init__(self, model_path='yolov8n.pt', confidence=0.6, frames_espera=10):
        # Inicializar componentes
        self.model_manager = ModelManager(model_path)
        self.detector = PersonDetector(model_path, confidence)
        self.tracker = ObjectTracker(frames_espera)
        self.video_processor = VideoProcessor()
        self.frame_annotator = FrameAnnotator()
        self.servo_controller = ServoController()
        
        # Estado
        self.ultima_coords = None
        self.procesando = False
        
    def inicializar_modelo(self, ruta_modelo='yolov8n.pt'):
        """
        Inicializa o cambia el modelo de detección.
        
        Args:
            ruta_modelo (str): Ruta del modelo a utilizar.
            
        Returns:
            object: Instancia del modelo cargado.
        """
        self.model_manager.set_model_path(ruta_modelo)
        self.detector = PersonDetector(ruta_modelo, self.detector.confidence)
        return self.model_manager.get_model()
        
    def abrir_video(self, ruta_video):
        if not self.video_processor.open_source(ruta_video):
            return None
            
        # Configurar salida con nombre default
        self.video_processor.setup_output('salida.avi', 'XVID')
        
        frame_width, frame_height = self.video_processor.get_dimensions()
        fps = self.video_processor.get_fps()
        
        return (self.video_processor.cap, 
                self.video_processor.out,
                frame_width, 
                frame_height, 
                fps)
        
    def detectar_personas(self, frame, confidence=None):
        return self.detector.detect(frame, confidence)
        
    def extraer_ids(self, boxes):
        ids_esta_frame = set()
        ids = boxes.id
        if ids is not None:
            for id_tensor in ids:
                ids_esta_frame.add(int(id_tensor.item()))
        return ids_esta_frame
        
    def actualizar_rastreo(self, primer_id, rastreo_id, ids_esta_frame, frames_perdidos, frames_espera=None):
        """
        Actualiza el estado de rastreo.
        
        Args:
            primer_id (int): ID del primer objeto detectado.
            rastreo_id (int): ID del objeto actual.
            ids_esta_frame (set): IDs detectados en el frame.
            frames_perdidos (int): Contador de frames sin detectar.
            frames_espera (int, opcional): Frames de espera antes de cambiar.
            
        Returns:
            tuple: (primer_id, rastreo_id, reiniciar_coords, frames_perdidos)
        """
        if frames_espera is not None:
            self.tracker.set_frames_espera(frames_espera)
            
        # Configurar estado del tracker
        self.tracker.primer_id = primer_id
        self.tracker.rastreo_id = rastreo_id
        self.tracker.frames_perdidos = frames_perdidos
        
        # Actualizar rastreo
        primer_id, rastreo_id, reiniciar_coords, frames_perdidos = self.tracker.actualizar(ids_esta_frame)
        
        return primer_id, rastreo_id, reiniciar_coords, frames_perdidos
        
    def dibujar_anotaciones(self, frame, boxes, rastreo_id, ultima_coords, ids_globales, frame_width, controlar_servo=False):
        return self.frame_annotator.annotate_frame(
            frame, boxes, rastreo_id, ultima_coords, 
            ids_globales, frame_width, controlar_servo
        )
        
    def enviar_angulo_a_esp32(self, angulo):
        return self.servo_controller.enviar_angulo(angulo)
        
    def convertir_a_comando(self, x_centro, frame_width):
        if x_centro < frame_width // 2:
            return int(90 - ((frame_width // 2 - x_centro) / (frame_width // 2) * 45))
        else:
            return int(90 + ((x_centro - frame_width // 2) / (frame_width // 2) * 45))
        
    def iniciar_procesamiento(self, video_path='./test4.mp4', model_path='yolov8n.pt', 
                             confidence=0.6, frames_espera=10, controlar_servo=True,
                             mostrar_video=True, guardar_video=True, output_path='salida.avi'):
        """
        Inicia el procesamiento completo de un video.
        
        Args:
            video_path (str): Ruta del video o ID de cámara.
            model_path (str): Ruta del modelo.
            confidence (float): Umbral de confianza.
            frames_espera (int): Frames antes de cambiar objetivo.
            controlar_servo (bool): Si se debe controlar el servo.
            mostrar_video (bool): Si se debe mostrar el video.
            guardar_video (bool): Si se debe guardar el video.
            output_path (str): Ruta de salida del video.
            
        Returns:
            bool: True si el procesamiento fue exitoso.
        """
        try:
            # Inicializar componentes
            model = self.inicializar_modelo(model_path)
            self.detector.set_confidence(confidence)
            self.tracker.set_frames_espera(frames_espera)
            
            # Abrir video
            if not self.video_processor.open_source(video_path):
                return False
                
            # Configurar salida si es necesario
            if guardar_video:
                if not self.video_processor.setup_output(output_path):
                    return False
            
            # Estado de rastreo
            primer_id = None
            rastreo_id = None
            ids_globales = set()
            ultima_coords = None
            frames_perdidos = 0
            frame_width = self.video_processor.frame_width
            
            self.procesando = True
            
            # Loop de procesamiento
            while self.procesando:
                ret, frame = self.video_processor.read_frame()
                if not ret:
                    break
                    
                # Detectar personas
                result = self.detectar_personas(model, frame, confidence)
                if result is None:
                    continue
                    
                boxes = result.boxes
                ids_esta_frame = self.extraer_ids(boxes)
                
                # Actualizar estado de rastreo
                primer_id, rastreo_id, reiniciar_coords, frames_perdidos = self.actualizar_rastreo(
                    primer_id, rastreo_id, ids_esta_frame, frames_perdidos, frames_espera
                )
                if reiniciar_coords:
                    ultima_coords = None
                
                # Anotar frame
                annotated_frame, ultima_coords = self.dibujar_anotaciones(
                    result.plot(), boxes, rastreo_id, ultima_coords, 
                    ids_globales, frame_width, controlar_servo
                )
                
                # Mostrar y guardar
                if mostrar_video:
                    self.video_processor.display_frame(annotated_frame, "Seguimiento")
                    
                if guardar_video:
                    self.video_processor.write_frame(annotated_frame)
                
                # Salir con 'q'
                if mostrar_video and cv2.waitKey(25) & 0xFF == ord('q'):
                    break
                    
            # Limpiar
            self.video_processor.close_source()
            if mostrar_video:
                self.video_processor.destroy_windows()
                
            self.procesando = False
            return True
            
        except Exception as e:
            print(f"Error en procesamiento: {e}")
            self.procesando = False
            self.video_processor.close_source()
            if mostrar_video:
                self.video_processor.destroy_windows()
            return False
            
    def detener_procesamiento(self):
        self.procesando = False
        
    def reiniciar(self):
        self.tracker.reset()
        self.ultima_coords = None
        self.procesando = False
