"""
Módulo para manejar la salida de video en la aplicación TrackerVidriera.
Se encarga de inicializar, configurar y manejar la escritura de frames procesados.
"""
import cv2
import os
from pathlib import Path


class VideoOutputManager:
    """Clase para gestionar la salida del video procesado."""
    
    def __init__(self):
        """Inicializa el gestor de salida de video."""
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
            # Asegurarnos que el directorio de salida existe
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Guardar configuración
            self.output_path = output_path
            self.codec = codec
            self.fps = fps
            self.width = width
            self.height = height
            
            # Crear el objeto VideoWriter
            fourcc = cv2.VideoWriter_fourcc(*codec)
            self.output_writer = cv2.VideoWriter(
                output_path, fourcc, fps, (width, height)
            )
            
            return True
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
        if self.output_writer is None:
            return False
        
        try:
            self.output_writer.write(frame)
            return True
        except Exception as e:
            print(f"Error al escribir frame: {e}")
            return False
    
    def release(self):
        """
        Libera el escritor de video.
        
        Returns:
            bool: True si se liberó correctamente, False en caso contrario.
        """
        if self.output_writer is None:
            return True
        
        try:
            self.output_writer.release()
            self.output_writer = None
            return True
        except Exception as e:
            print(f"Error al liberar el escritor de video: {e}")
            return False
    
    def get_output_info(self):
        """
        Obtiene información sobre la configuración de salida.
        
        Returns:
            dict: Diccionario con la información de la salida.
        """
        return {
            "path": self.output_path,
            "codec": self.codec,
            "fps": self.fps,
            "resolution": f"{self.width}x{self.height}"
        }