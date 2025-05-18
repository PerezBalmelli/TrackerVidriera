"""
Widget con los botones de acción de la aplicación TrackerVidriera.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal


class ActionButtonsWidget(QWidget):
    """Widget con los botones de acción principales."""
    
    process_clicked = pyqtSignal()  # Señal cuando se presiona el botón de procesar
    stop_clicked = pyqtSignal()     # Señal cuando se presiona el botón de detener
    save_config_clicked = pyqtSignal()  # Señal cuando se presiona el botón de guardar config
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Botón de procesar
        self.process_button = QPushButton("Procesar video")
        self.process_button.setMinimumHeight(40)
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self.process_clicked)
        
        # Botón de detener
        self.stop_button = QPushButton("Detener")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_clicked)
        
        # Botón de guardar configuración
        self.save_config_button = QPushButton("Guardar configuración")
        self.save_config_button.clicked.connect(self.save_config_clicked)
        
        # Añadir botones al layout
        layout.addWidget(self.process_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.save_config_button)
    
    # Métodos para controlar el estado de los botones
    def enable_process_button(self, enabled=True, text=None):
        """Habilita o deshabilita el botón de procesar y opcionalmente cambia su texto."""
        self.process_button.setEnabled(enabled)
        if text:
            self.process_button.setText(text)
    
    def enable_stop_button(self, enabled=True):
        """Habilita o deshabilita el botón de detener."""
        self.stop_button.setEnabled(enabled)
    
    def set_processing_mode(self, is_processing, is_camera=False):
        """Configura los botones para el modo de procesamiento."""
        self.process_button.setEnabled(not is_processing)
        self.stop_button.setEnabled(is_processing)
        
        if is_processing:
            self.process_button.setText("Procesando...")
        else:
            self.process_button.setText("Procesar en vivo" if is_camera else "Procesar video")
