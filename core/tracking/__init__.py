"""
Paquete para la detección y rastreo de personas.
Contiene los módulos necesarios para el manejo de modelos, detección y rastreo.
"""

from .model_manager import ModelManager
from .person_detector import PersonDetector
from .object_tracker import ObjectTracker
from .video_processor import VideoProcessor

__all__ = ['ModelManager', 'PersonDetector', 'ObjectTracker', 'VideoProcessor']
