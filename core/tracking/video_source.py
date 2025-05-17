"""
Módulo para gestión de fuentes de video (entrada).
"""
import cv2
from pathlib import Path


class VideoSource:
    """
    Clase responsable de manejar la entrada de video, ya sea archivo o cámara.
    Implementa el patrón de responsabilidad única para la fuente de video.
    """
    
    def __init__(self):
        """
        Inicializa la fuente de video.
        """
        self.cap = None
        self.frame_width = 0
        self.frame_height = 0
        self.fps = 0
        self.source_path = None
        self.is_camera = False
    
    def open(self, source_path):
        """
        Abre una fuente de video (archivo o cámara).
        
        Args:
            source_path (str or int): Ruta del archivo o índice de la cámara.
            
        Returns:
            bool: True si se abrió correctamente, False en caso contrario.
        """
        self.close()  # Cerrar si había algo abierto
        
        try:
            self.source_path = source_path
            self.is_camera = isinstance(source_path, int) or source_path.isdigit()
            
            self.cap = cv2.VideoCapture(source_path)
            if not self.cap.isOpened():
                print(f"Error: No se pudo abrir la fuente de video: {source_path}")
                return False
            
            self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.fps <= 0:  # Si no se puede determinar el FPS
                self.fps = 30.0
                
            return True
        except Exception as e:
            print(f"Error al abrir la fuente de video: {e}")
            self.close()
            return False
    
    def read_frame(self):
        """
        Lee el siguiente frame de la fuente de video.
        
        Returns:
            tuple: (éxito, frame) donde éxito es un booleano y frame es el frame leído.
        """
        if self.cap is None:
            return False, None
            
        return self.cap.read()
    
    def close(self):
        """
        Cierra la fuente de video y libera recursos.
        """
        if self.cap:
            self.cap.release()
            self.cap = None
            self.source_path = None
    
    def is_opened(self):
        """
        Verifica si hay una fuente de video abierta.
        
        Returns:
            bool: True si hay una fuente abierta, False en caso contrario.
        """
        return self.cap is not None and self.cap.isOpened()
    
    def get_total_frames(self):
        """
        Obtiene el número total de frames del video.
        Para cámaras en vivo, devuelve -1.
        
        Returns:
            int: Número total de frames o -1 si es una cámara.
        """
        if not self.is_opened():
            return 0
            
        if self.is_camera:
            return -1
        return int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    def get_dimensions(self):
        """
        Obtiene las dimensiones actuales del video.
        
        Returns:
            tuple: (ancho, alto) del video.
        """
        return (self.frame_width, self.frame_height)
    
    def get_fps(self):
        """
        Obtiene los FPS del video.
        
        Returns:
            float: FPS del video.
        """
        return self.fps
    
    def get_source_info(self):
        """
        Obtiene información sobre la fuente de video.
        
        Returns:
            dict: Diccionario con información sobre la fuente.
        """
        return {
            "source": self.source_path,
            "is_camera": self.is_camera,
            "dimensions": f"{self.frame_width}x{self.frame_height}",
            "fps": self.fps,
            "total_frames": self.get_total_frames()
        }
