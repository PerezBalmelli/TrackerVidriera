"""
Widget para la configuración del modelo de IA en la aplicación TrackerVidriera.
"""
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QLabel, QComboBox, QDoubleSpinBox, QSpinBox
)
from PyQt6.QtCore import pyqtSignal


class ModelConfigWidget(QWidget):
    """Widget para configurar los parámetros del modelo de detección."""
    
    model_changed = pyqtSignal(str)
    status_message = pyqtSignal(str, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Grupo de configuración del modelo
        model_group = QGroupBox("Configuración del modelo")
        model_layout = QFormLayout(model_group)
        
        # Selector de modelo
        self.model_path_combo = QComboBox()
        self.populate_model_combo()
        self.model_path_combo.currentTextChanged.connect(self._on_model_changed)
        model_layout.addRow("Modelo:", self.model_path_combo)
        
        # Umbral de confianza
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.1, 1.0)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setValue(0.6)
        model_layout.addRow("Umbral de confianza:", self.confidence_spin)
        
        # Frames de espera
        self.frames_wait_spin = QSpinBox()
        self.frames_wait_spin.setRange(1, 30)
        self.frames_wait_spin.setValue(10)
        model_layout.addRow("Frames de espera:", self.frames_wait_spin)
        
        layout.addWidget(model_group)
    
    def _on_model_changed(self, model_name):
        """Maneja el cambio del modelo seleccionado."""
        self.model_changed.emit(model_name)
    
    def populate_model_combo(self):
        """Busca y añade los modelos disponibles al combo."""
        self.model_path_combo.clear()
        models_dir = Path(__file__).parent.parent.parent / "models"
        models_root = Path(__file__).parent.parent.parent
        model_files = []
        
        if models_dir.exists() and models_dir.is_dir():
            model_files.extend(list(models_dir.glob("*.pt")))
            
        model_files.extend(list(models_root.glob("*.pt")))
        
        model_names = sorted([model.name for model in model_files if model.is_file()])
        
        if not model_names:
            model_names = ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt"]
            self.status_message.emit("No se encontraron modelos .pt, usando predeterminados.", 3000)
        else:
            self.status_message.emit(f"Se encontraron {len(model_names)} modelos.", 3000)
            
        self.model_path_combo.addItems(model_names)
    
    # Métodos públicos para acceder desde la ventana principal
    def get_model_path(self):
        """Retorna el nombre del modelo seleccionado."""
        return self.model_path_combo.currentText()
    
    def set_model_path(self, model_path):
        """Establece el modelo seleccionado."""
        index = self.model_path_combo.findText(model_path)
        if index >= 0:
            self.model_path_combo.setCurrentIndex(index)
    
    def get_confidence(self):
        """Retorna el umbral de confianza configurado."""
        return self.confidence_spin.value()
    
    def set_confidence(self, confidence):
        """Establece el umbral de confianza."""
        self.confidence_spin.setValue(confidence)
    
    def get_frames_wait(self):
        """Retorna el número de frames de espera configurado."""
        return self.frames_wait_spin.value()
    
    def set_frames_wait(self, frames):
        """Establece el número de frames de espera."""
        self.frames_wait_spin.setValue(frames)
