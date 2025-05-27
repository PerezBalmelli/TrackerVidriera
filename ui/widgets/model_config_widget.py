"""
Widget para la configuración del modelo de IA en la aplicación TrackerVidriera.
"""
import logging # Added
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QLabel, QComboBox, QDoubleSpinBox, QSpinBox
)
from PyQt6.QtCore import pyqtSignal

logger = logging.getLogger(__name__) # Added

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
        logger.info(f"Modelo cambiado a: {model_name}")

    def populate_model_combo(self):
        """Busca y añade los modelos disponibles al combo."""
        self.model_path_combo.clear()
        # Consider defining a BASE_APP_PATH and constructing model_dir from it for robustness.
        # Current logic depends on the script's relative location to the 'models' directory.
        models_dir_project_root_sibling = Path(__file__).parent.parent.parent / "models" # ../../../models
        models_dir_parent_sibling = Path(__file__).parent.parent / "models" # ../../models

        model_files = []

        if models_dir_project_root_sibling.exists() and models_dir_project_root_sibling.is_dir():
            model_files.extend(list(models_dir_project_root_sibling.glob("*.pt")))
            logger.info(f"Buscando modelos en: {models_dir_project_root_sibling.resolve()}")

        if models_dir_parent_sibling.exists() and models_dir_parent_sibling.is_dir():
            model_files.extend(list(models_dir_parent_sibling.glob("*.pt")))
            logger.info(f"Buscando modelos en: {models_dir_parent_sibling.resolve()}")

        # Remove duplicates if paths overlap or find the same file
        model_files = sorted(list(set(model_files)), key=lambda p: p.name)


        model_names = [model.name for model in model_files if model.is_file()]

        if not model_names:
            # These are just placeholders if no .pt files are found.
            # The application logic in MainWindow should ensure these paths are valid or handle errors.
            model_names = ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt"] # Default names
            self.status_message.emit("No se encontraron modelos .pt, usando nombres predeterminados. Verifique las rutas.", 5000)
            logger.warning(f"No se encontraron modelos .pt en las rutas buscadas. Usando nombres predeterminados: {model_names}")
        else:
            self.status_message.emit(f"Se encontraron {len(model_names)} modelos.", 3000)
            logger.info(f"Modelos .pt encontrados: {model_names}")

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
        elif model_path: # If the model_path is provided but not in list, add it and select
            logger.warning(f"Modelo '{model_path}' no encontrado en la lista. Añadiéndolo manualmente.")
            self.model_path_combo.addItem(model_path)
            self.model_path_combo.setCurrentIndex(self.model_path_combo.count() -1)


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