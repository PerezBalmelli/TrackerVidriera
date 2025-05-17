"""
Widget para la visualización de video en la aplicación TrackerVidriera.
"""
import cv2
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap


class VideoDisplayWidget(QWidget):
    """Widget para la visualización de frames de video."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Label para mostrar el video
        self.display_label = QLabel("Vista previa no disponible")
        self.display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display_label.setMinimumSize(480, 360)  # Tamaño mínimo para la vista previa
        self.display_label.setStyleSheet("background-color: black; color: white;")
        
        layout.addWidget(self.display_label)
    
    @pyqtSlot(object)
    def display_frame(self, frame):
        """Muestra un frame en el label."""
        if frame is None:
            self.display_label.clear()
            self.display_label.setText("Vista previa no disponible")
            return

        try:
            # Convertir frame de BGR (OpenCV) a RGB (Qt)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            
            # Crear QImage desde los datos del frame
            qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Crear QPixmap y escalar manteniendo la proporción
            pixmap = QPixmap.fromImage(qimg)
            scaled_pixmap = pixmap.scaled(
                self.display_label.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.display_label.setPixmap(scaled_pixmap)
        except Exception as e:
            self.display_label.setText(f"Error al mostrar frame:\n{e}")
