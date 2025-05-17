"""
Módulo para el procesamiento de video y la gestión del flujo de entrada/salida.
Combina y orquesta las clases VideoSource y VideoOutput.
"""
import cv2
from pathlib import Path
import os
from .video_source import VideoSource
from .video_output import VideoOutput


class VideoProcessor:
    """
    Clase orquestadora que gestiona tanto la entrada como la salida de video.
    """
    
    def __init__(self):
        """
        Inicializa el procesador de video.
        """
        self.source = VideoSource()
        self.output = VideoOutput()
        self.current_frame = None
        self.display_windows = set()
        
        # Para mantener compatibilidad con código existente
        self.cap = None
        self.out = None
        self.frame_width = 0
        self.frame_height = 0
        self.fps = 0
        
    def open_source(self, source_path):
        """
        Abre una fuente de video (archivo o cámara).
        
        Args:
            source_path (str or int): Ruta del archivo o índice de la cámara.
            
        Returns:
            bool: True si se abrió correctamente, False en caso contrario.
        """
        # Usar el objeto VideoSource
        success = self.source.open(source_path)
        
        # Mantener compatibilidad con código existente
        if success:
            self.cap = self.source.cap
            self.frame_width = self.source.frame_width
            self.frame_height = self.source.frame_height
            self.fps = self.source.fps
            
        return success
        
    def setup_output(self, output_path, codec='XVID', override_dimensions=None):
        """
        Configura la salida de video.
        
        Args:
            output_path (str): Ruta del archivo de salida.
            codec (str): Codec de video (XVID, MP4V, etc).
            override_dimensions (tuple, opcional): (ancho, alto) para sobreescribir
                                                 las dimensiones de la entrada.
        
        Returns:
            bool: True si se configuró correctamente, False en caso contrario.
        """
        if not self.source.is_opened():
            print("Error: No hay fuente de video abierta.")
            return False
        
        # Usar dimensiones de la fuente si no se especificaron otras
        if override_dimensions:
            width, height = override_dimensions
        else:
            width, height = self.source.get_dimensions()
        
        # Configurar la salida con los parámetros de la fuente
        success = self.output.setup(
            output_path,
            codec,
            self.source.get_fps(),
            (width, height)
        )
        
        # Mantener compatibilidad con código existente
        if success:            self.out = self.output.output_writer
            
        return success
        
    def read_frame(self):
        """
        Lee el siguiente frame de la fuente de video.
        
        Returns:
            tuple: (éxito, frame) donde éxito es un booleano y frame es el frame leído.
        """
        success, frame = self.source.read_frame()
        if success:
            self.current_frame = frame
        return success, frame
    
    def write_frame(self, frame):
        """
        Escribe un frame al archivo de salida.
        
        Args:
            frame (numpy.ndarray): Frame a escribir.
            
        Returns:
            bool: True si se escribió correctamente, False en caso contrario.
        """
        return self.output.write_frame(frame)
    
    def display_frame(self, frame, window_name="Video"):
        """
        Muestra un frame en una ventana.
        
        Args:
            frame (numpy.ndarray): Frame a mostrar.
            window_name (str): Nombre de la ventana.        
        """
        cv2.imshow(window_name, frame)
        self.display_windows.add(window_name)
        
    def close_source(self):
        """
        Cierra la fuente de video y libera recursos.
        """
        self.source.close()
        self.cap = None
    
    def close_output(self):
        """
        Cierra la salida de video y libera recursos.
        """
        self.output.close()
        self.out = None
    
    def close_all(self):
        """
        Cierra tanto la fuente como la salida de video.
        """
        self.close_source()
        self.close_output()
        self.destroy_windows()
    
    def is_opened(self):
        """
        Verifica si hay una fuente de video abierta.
        
        Returns:
            bool: True si hay una fuente abierta, False en caso contrario.
        """
        return self.source.is_opened()
    
    def is_output_ready(self):
        """
        Verifica si la salida está lista para escribir frames.
        
        Returns:
            bool: True si la salida está lista, False en caso contrario.
        """
        return self.output.is_ready()
    
    def get_total_frames(self):
        """
        Obtiene el número total de frames del video.
        Para cámaras en vivo, devuelve -1.
        
        Returns:
            int: Número total de frames o -1 si es una cámara.
        """
        return self.source.get_total_frames()
    
    def get_dimensions(self):
        """
        Obtiene las dimensiones actuales del video de entrada.
        
        Returns:
            tuple: (ancho, alto) del video.
        """
        return self.source.get_dimensions()
    
    def get_fps(self):
        """
        Obtiene los FPS del video de entrada.
        
        Returns:
            float: FPS del video.
        """
        return self.source.get_fps()
    
    def destroy_windows(self):
        """
        Destruye todas las ventanas creadas por OpenCV.
        """
        cv2.destroyAllWindows()
        self.display_windows.clear()
    
    def get_source_info(self):
        """
        Obtiene información sobre la fuente de video.
        
        Returns:
            dict: Información sobre la fuente de video.
        """
        return self.source.get_source_info()
    
    def get_output_info(self):
        """
        Obtiene información sobre la configuración de salida de video.
        
        Returns:
            dict: Información sobre la configuración de salida.
        """
        return self.output.get_output_info()
    
    def wait_key(self, delay=1):
        """
        Espera una tecla durante un tiempo determinado.
        Wrapper para cv2.waitKey.
        
        Args:
            delay (int): Tiempo de espera en milisegundos.
            
        Returns:
            int: Código ASCII de la tecla presionada o -1 si no se presionó ninguna.
        """
        return cv2.waitKey(delay)
    
    def get_progress_percentage(self, current_frame):
        """
        Calcula el porcentaje de progreso del procesamiento del video.
        
        Args:
            current_frame (int): Frame actual.
            
        Returns:
            int: Porcentaje de progreso (0-100) o -1 si es una cámara.
        """
        total_frames = self.get_total_frames()
        if total_frames <= 0:
            return -1
        return int((current_frame / total_frames) * 100)
