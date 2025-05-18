"""
Módulo para manejar la salida de video en la aplicación TrackerVidriera.
Se encarga de inicializar, configurar y manejar la escritura de frames procesados.
"""
import cv2
import os
from pathlib import Path
from .tracking.video_output import VideoOutput


class VideoOutputManager:
    """Clase para gestionar la salida del video procesado.
    Implementa el patrón Adapter para mantener compatibilidad con código existente
    mientras utiliza la implementación refactorizada."""
    
    def __init__(self):
        """Inicializa el gestor de salida de video."""
        self._output = VideoOutput()
        
        # Mantener variables para compatibilidad con código existente
        self.output_writer = None
        self.output_path = None
        self.codec = None
        self.fps = None
        self.width = None
        self.height = None
    def setup_output(self, output_path, codec, fps, width, height):
        """
        Configura el escritor de video para la salida.
        
        Args:
            output_path (str): Ruta donde se guardará el video.
            codec (str): Código FourCC del codec a utilizar.
            fps (float): Frames por segundo.
            width (int): Ancho del video de salida.
            height (int): Alto del video de salida.
        
        Returns:
            bool: True si la configuración fue exitosa, False en caso contrario.
        """
        try:
            # Usar la implementación refactorizada
            success = self._output.setup(output_path, codec, fps, (width, height))
            
            # Actualizar variables para compatibilidad
            if success:
                self.output_path = output_path
                self.codec = codec
                self.fps = fps
                self.width = width
                self.height = height
                self.output_writer = self._output.output_writer
                
            return success
        except Exception as e:
            print(f"Error al configurar la salida de video: {e}")
            return False
    def write_frame(self, frame):
        """
        Escribe un frame en el video de salida.
        
        Args:
            frame (ndarray): Frame a escribir.
            
        Returns:
            bool: True si el frame se escribió correctamente, False en caso contrario.
        """
        return self._output.write_frame(frame)
    
    def release(self):
        """
        Libera el escritor de video.
        
        Returns:
            bool: True si se liberó correctamente, False en caso contrario.
        """
        success = self._output.close()
        if success:
            self.output_writer = None
        return success
    
    def get_output_info(self):
        """
        Obtiene información sobre la configuración de salida.
        
        Returns:
            dict: Diccionario con la información de la salida.
        """
        return self._output.get_output_info()