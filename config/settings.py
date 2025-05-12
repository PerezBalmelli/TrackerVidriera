"""
Módulo de configuración para la aplicación TrackerVidriera.
Gestiona todas las configuraciones y parámetros ajustables de la aplicación.
"""
import json
import os
from pathlib import Path


class Settings:
    """Clase para gestionar las configuraciones de la aplicación."""
    
    def __init__(self):
        """Inicializa las configuraciones con valores por defecto."""
        self.config_path = Path.home() / "trackervidriera_config.json"
        
        # Configuración del modelo
        self.model_path = "yolov8n.pt"
        self.confidence_threshold = 0.6
        self.classes = [0]  # Solo personas
        
        # Configuración de seguimiento
        self.frames_espera = 10
        
        # Configuración de salida
        self.output_path = "salida.avi"
        self.output_format = "XVID"
        self.output_fps = None  # Se ajustará según el video de entrada
        self.output_width = None  # Se ajustará según el video de entrada
        self.output_height = None  # Se ajustará según el video de entrada
        
        # Cargar configuraciones guardadas si existen
        self.load_settings()
    
    def save_settings(self):
        """Guarda las configuraciones actuales en un archivo JSON."""
        config_data = {
            "model_path": self.model_path,
            "confidence_threshold": self.confidence_threshold,
            "classes": self.classes,
            "frames_espera": self.frames_espera,
            "output_path": self.output_path,
            "output_format": self.output_format,
        }
        
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error al guardar la configuración: {e}")
            return False
    
    def load_settings(self):
        """Carga las configuraciones desde un archivo JSON si existe."""
        if not os.path.exists(self.config_path):
            return False
        
        try:
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
                
            self.model_path = config_data.get("model_path", self.model_path)
            self.confidence_threshold = config_data.get("confidence_threshold", self.confidence_threshold)
            self.classes = config_data.get("classes", self.classes)
            self.frames_espera = config_data.get("frames_espera", self.frames_espera)
            self.output_path = config_data.get("output_path", self.output_path)
            self.output_format = config_data.get("output_format", self.output_format)
            
            return True
        except Exception as e:
            print(f"Error al cargar la configuración: {e}")
            return False
    
    def get_codec_fourcc(self):
        """Devuelve el código FourCC para el formato de salida seleccionado."""
        codec_map = {
            "XVID": "XVID",
            "MP4V": "MP4V",
            "MJPG": "MJPG",
            "H264": "H264",
            "AVC1": "AVC1",
        }
        return codec_map.get(self.output_format, "XVID")


# Instancia global de configuración
settings = Settings()