"""
Widget para la configuración de la salida de video en la aplicación TrackerVidriera.
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QLineEdit
)
from PyQt6.QtCore import pyqtSignal


class OutputConfigWidget(QWidget):
    """Widget para configurar los parámetros de salida del video procesado."""
    
    output_path_changed = pyqtSignal(str)
    codec_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.codec_extension_map = {
            "XVID": ".avi", "MP4V": ".mp4", "MJPG": ".avi",
            "H264": ".mp4", "AVC1": ".mp4"
        }
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Grupo de configuración de salida
        output_group = QGroupBox("Configuración de salida")
        output_layout = QFormLayout(output_group)
        
        # Ruta de salida
        self.output_path_edit = QLineEdit("salida.avi")
        output_save_button = QPushButton("Guardar como...")
        output_save_button.clicked.connect(self._set_output_file)
        
        output_path_layout = QHBoxLayout()
        output_path_layout.addWidget(self.output_path_edit)
        output_path_layout.addWidget(output_save_button)
        
        output_layout.addRow("Archivo de salida:", output_path_layout)
        
        # Codec de video
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["XVID", "MP4V", "MJPG", "H264", "AVC1"])
        self.codec_combo.currentTextChanged.connect(self._on_codec_changed)
        
        output_layout.addRow("Formato:", self.codec_combo)
        
        layout.addWidget(output_group)
    
    def _on_codec_changed(self, codec):
        """Maneja el cambio del codec seleccionado."""
        if self.output_path_edit.text():
            new_path = self._ensure_valid_extension(
                self.output_path_edit.text(), codec
            )
            if new_path != self.output_path_edit.text():
                self.output_path_edit.setText(new_path)
                self.output_path_changed.emit(new_path)
        self.codec_changed.emit(codec)
    
    def _set_output_file(self):
        """Abre un diálogo para seleccionar la ubicación del archivo de salida."""
        codec = self.codec_combo.currentText()
        recommended_ext = self._get_recommended_extension(codec)
        
        base_name = os.path.splitext(Path(self.output_path_edit.text()).name)[0] if self.output_path_edit.text() else "salida"
        default_name = f"{base_name}{recommended_ext}"
        
        filter_str = "MP4 (*.mp4);;AVI (*.avi);;MKV (*.mkv);;Todos los archivos (*)"
        if recommended_ext == ".avi":
            filter_str = "AVI (*.avi);;MP4 (*.mp4);;MKV (*.mkv);;Todos los archivos (*)"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar video como", default_name, filter_str
        )
        
        if file_path:
            file_ext = os.path.splitext(file_path)[1].lower()
            if not file_ext:
                file_path += recommended_ext
                file_ext = recommended_ext
                
            self.output_path_edit.setText(file_path)
            self._update_codec_for_extension(file_ext)
            self.output_path_changed.emit(file_path)
    
    def _get_recommended_extension(self, codec):
        """Retorna la extensión recomendada para el codec seleccionado."""
        return self.codec_extension_map.get(codec.upper(), ".avi")
    
    def _ensure_valid_extension(self, file_path, codec):
        """Asegura que la extensión del archivo es compatible con el codec."""
        if not file_path:
            return file_path
            
        current_ext = os.path.splitext(file_path)[1].lower()
        recommended_ext = self._get_recommended_extension(codec)
        
        if current_ext not in [".avi", ".mp4", ".mkv"] or \
           (current_ext != recommended_ext and self._is_extension_incompatible(current_ext, codec)):
            new_path = os.path.splitext(file_path)[0] + recommended_ext
            return new_path
            
        return file_path
    
    def _is_extension_incompatible(self, extension, codec):
        """Verifica si la extensión es incompatible con el codec seleccionado."""
        codec = codec.upper()
        if extension == ".mp4" and codec not in ["MP4V", "H264", "AVC1"]:
            return True
        if extension == ".avi" and codec not in ["XVID", "MJPG"]:
            return True
        return False
    
    def _update_codec_for_extension(self, extension):
        """Actualiza el codec para que sea compatible con la extensión."""
        extension = extension.lower()
        current_codec = self.codec_combo.currentText()
        
        new_codec_str = None
        if extension == ".mp4" and current_codec not in ["MP4V", "H264", "AVC1"]:
            new_codec_str = "MP4V"
        elif extension == ".avi" and current_codec not in ["XVID", "MJPG"]:
            new_codec_str = "XVID"

        if new_codec_str:
            new_codec_index = self.codec_combo.findText(new_codec_str)
            if new_codec_index >= 0:
                self.codec_combo.setCurrentIndex(new_codec_index)
                return True
                
        return False
    
    # Métodos públicos para acceder desde la ventana principal
    def get_output_path(self):
        """Retorna la ruta de salida configurada."""
        return self.output_path_edit.text()
    
    def set_output_path(self, path):
        """Establece la ruta de salida."""
        self.output_path_edit.setText(path)
        
    def get_codec(self):
        """Retorna el codec seleccionado."""
        return self.codec_combo.currentText()
    
    def set_codec(self, codec):
        """Establece el codec."""
        index = self.codec_combo.findText(codec)
        if index >= 0:
            self.codec_combo.setCurrentIndex(index)
