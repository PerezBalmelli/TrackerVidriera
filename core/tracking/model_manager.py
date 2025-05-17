"""
Módulo para la gestión de modelos de detección de objetos.
"""
from ultralytics import YOLO
from pathlib import Path


class ModelManager:
    """
    Clase responsable de cargar y gestionar los modelos
    """
    _instance = None
    _model = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, model_path='yolov8n.pt'):
        if self._initialized:
            return
        
        self._model_path = Path(model_path)
        self._model = None
        self._initialized = True
    
    def load_model(self):
        if self._model is None:
            try:
                self._model = YOLO(str(self._model_path))
            except Exception as e:
                raise RuntimeError(f"Error al cargar modelo {self._model_path}: {str(e)}")
        return self._model
    
    def get_model(self):
        if self._model is None:
            return self.load_model()
        return self._model
    
    def set_model_path(self, model_path):
        self._model_path = Path(model_path)
        self._model = None  # Forzar recarga
        
    @property
    def model_path(self):
        """Obtiene la ruta del modelo actual."""
        return str(self._model_path)
