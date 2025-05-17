"""
Módulo mejorado para la salida de video.
Combina funcionalidades de las implementaciones anteriores con mejor estructura.
"""
import cv2
import os
from pathlib import Path


class VideoOutput:
    """
    Clase responsable exclusivamente de la salida de video.
    """
    
    def __init__(self):
        """
        Inicializa el gestor de salida de video.
        """
        self.output_writer = None
        self.output_path = None
        self.codec = None
        self.fps = None
        self.width = None
        self.height = None
        self.is_configured = False
    
    def setup(self, output_path, codec='XVID', fps=30.0, dimensions=None):
        """
        Configura el escritor de video para la salida.
        
        Args:
            output_path (str): Ruta donde se guardará el video.
            codec (str): Código FourCC del codec a utilizar (XVID, MP4V, etc).
            fps (float): Frames por segundo.
            dimensions (tuple): (width, height) del video de salida. Si es None,
                               debe configurarse más tarde con set_dimensions().
        
        Returns:
            bool: True si la configuración fue exitosa, False en caso contrario.
        """
        try:
            # Cerrar cualquier salida previa
            self.close()
            
            # Asegurarnos que el directorio de salida existe
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Guardar configuración
            self.output_path = output_path
            self.codec = codec
            self.fps = fps
            
            # Si se proporcionaron dimensiones, configurar ahora
            if dimensions:
                self.width, self.height = dimensions
                return self._initialize_writer()
            
            # Si no se proporcionaron dimensiones, esperar a que se configuren
            self.is_configured = False
            return True
        
        except Exception as e:
            print(f"Error al configurar la salida de video: {e}")
            self.close()
            return False
    
    def set_dimensions(self, width, height):
        """
        Establece las dimensiones del video de salida.
        Necesario llamar si no se proporcionaron dimensiones en setup().
        
        Args:
            width (int): Ancho del video de salida.
            height (int): Alto del video de salida.
            
        Returns:
            bool: True si se configuró correctamente, False en caso contrario.
        """
        self.width = width
        self.height = height
        
        # Si ya tenemos el resto de la configuración, inicializar el writer
        if self.output_path and self.codec and self.fps:
            return self._initialize_writer()
        
        return False
    
    def _initialize_writer(self):
        """
        Inicializa el objeto VideoWriter con la configuración establecida.
        
        Returns:
            bool: True si se inicializó correctamente, False en caso contrario.
        """
        try:
            if not all([self.output_path, self.codec, self.fps, self.width, self.height]):
                return False
                
            # Crear el objeto VideoWriter
            fourcc = cv2.VideoWriter_fourcc(*self.codec)
            self.output_writer = cv2.VideoWriter(
                self.output_path, fourcc, self.fps, (self.width, self.height)
            )
            
            if not self.output_writer.isOpened():
                print(f"Error: No se pudo crear el archivo de salida con codec {self.codec}.")
                
                # Intentar con codec alternativo si es MP4
                if self.codec == "MP4V" and self.output_path.lower().endswith(".mp4"):
                    print("Intentando con codec H264 como alternativa...")
                    fourcc = cv2.VideoWriter_fourcc(*"H264")
                    self.output_writer = cv2.VideoWriter(
                        self.output_path, fourcc, self.fps, (self.width, self.height)
                    )
                    
                    if not self.output_writer.isOpened():
                        print("Error: Tampoco se pudo crear con H264.")
                        return False
            
            self.is_configured = True
            return True
            
        except Exception as e:
            print(f"Error al inicializar el escritor de video: {e}")
            self.close()
            return False
    
    def write_frame(self, frame):
        """
        Escribe un frame en el video de salida.
        
        Args:
            frame (ndarray): Frame a escribir.
            
        Returns:
            bool: True si el frame se escribió correctamente, False en caso contrario.
        """
        if not self.is_configured or self.output_writer is None:
            return False
        
        try:
            self.output_writer.write(frame)
            return True
        except Exception as e:
            print(f"Error al escribir frame: {e}")
            return False
    
    def close(self):
        """
        Libera el escritor de video y limpia recursos.
        
        Returns:
            bool: True si se liberó correctamente, False en caso contrario.
        """
        try:
            if self.output_writer is not None:
                self.output_writer.release()
                self.output_writer = None
            
            self.is_configured = False
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
        status = "Configurado" if self.is_configured else "Sin configurar"
        if not self.output_path:
            return {"status": "Sin configurar"}
            
        return {
            "path": self.output_path,
            "codec": self.codec,
            "fps": self.fps,
            "resolution": f"{self.width}x{self.height}" if self.width and self.height else "No definida",
            "status": status
        }
    
    def is_ready(self):
        """
        Verifica si el escritor está configurado y listo para escribir.
        
        Returns:
            bool: True si está listo, False en caso contrario.
        """
        return self.is_configured and self.output_writer is not None
