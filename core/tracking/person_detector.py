"""
Módulo para detección de personas usando modelos YOLOv8.
"""
from .model_manager import ModelManager


class PersonDetector:
    """
    Clase responsable de detectar personas en imágenes o frames de video.
    """
    
    def __init__(self, model_path='yolov8n.pt', confidence=0.6):
        self.model_manager = ModelManager(model_path)
        self.confidence = confidence
        
    def detect(self, frame, confidence=None):
        """
        Detecta personas en un frame.
        
        Args:
            frame (numpy.ndarray): Frame de video o imagen.
            confidence (float, opcional): Umbral de confianza para esta detección.
                Si es None, se usa el umbral establecido en el constructor.
        
        Returns:
            object: Resultado de la detección con los boxes de personas.
        """
        if confidence is None:
            confidence = self.confidence
            
        model = self.model_manager.get_model()
        try:
            results = model.track(frame, persist=True, conf=confidence, classes=[0])  # Solo clase 0: persona
            # Aseguramos que hay al menos un resultado
            if results and len(results) > 0:
                return results[0]
            return None
        except Exception as e:
            print(f"Error en la detección: {e}")
            return None
    
    def set_confidence(self, confidence):
        self.confidence = max(0.0, min(1.0, confidence))  # Asegurar rango válido
    
    def extract_person_ids(self, detection_result):
        if detection_result is None or not hasattr(detection_result, 'boxes'):
            return set()
        
        ids_esta_frame = set()
        boxes = detection_result.boxes
        ids = boxes.id
        
        if ids is not None:
            for id_tensor in ids:
                ids_esta_frame.add(int(id_tensor.item()))
                
        return ids_esta_frame
