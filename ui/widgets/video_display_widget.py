"""
Widget para la visualización de video en la aplicación TrackerVidriera.
"""
import cv2
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap


class VideoDisplayWidget(QWidget):
    """Widget para la visualización de frames de video."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        main_layout = QHBoxLayout(self) # Layout principal horizontal
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2) # Pequeño espacio entre las vistas previas

        # Contenedor para la cámara principal (3/4 del espacio)
        self.main_camera_container = QWidget()
        main_camera_layout = QVBoxLayout(self.main_camera_container)
        main_camera_layout.setContentsMargins(0,0,0,0)
        self.display_label = QLabel("Cámara Principal")
        self.display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display_label.setMinimumSize(320, 240)
        self.display_label.setStyleSheet("background-color: black; color: white; border: 1px solid #555;")
        main_camera_layout.addWidget(self.display_label)
        
        # Contenedor para la segunda cámara (1/4 del espacio)
        self.second_camera_container = QWidget()
        second_camera_layout = QVBoxLayout(self.second_camera_container)
        second_camera_layout.setContentsMargins(0,0,0,0)
        self.second_display_label = QLabel("Cámara Móvil")
        self.second_display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.second_display_label.setMinimumSize(160, 120) 
        self.second_display_label.setStyleSheet("background-color: #111; color: white; border: 1px solid #444;")
        second_camera_layout.addWidget(self.second_display_label)

        main_layout.addWidget(self.main_camera_container, 3)  # 3/4 del espacio
        main_layout.addWidget(self.second_camera_container, 1) # 1/4 del espacio

        # Establecer políticas de tamaño para que se comporten bien al redimensionar
        self.display_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.second_display_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

    def _display_single_frame(self, frame, label_widget):
        if frame is None:
            label_widget.clear()
            if label_widget == self.display_label:
                label_widget.setText("Cámara Principal no disponible")
            else:
                label_widget.setText("Cámara Móvil no disponible")
            return

        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            
            # Escalar al tamaño del QLabel contenedor, manteniendo aspect ratio
            # El QLabel ya está dentro de un layout que maneja su tamaño relativo (3/4 o 1/4)
            scaled_pixmap = pixmap.scaled(
                label_widget.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            label_widget.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Error displaying frame: {e}")
            label_widget.setText("Error al mostrar frame")

    @pyqtSlot(object)
    def display_frame(self, frame):
        """Muestra un frame en el label de la cámara principal."""
        self._display_single_frame(frame, self.display_label)
    
    @pyqtSlot(object)
    def display_second_frame(self, frame):
        """Muestra un frame en el label de la segunda cámara."""
        self._display_single_frame(frame, self.second_display_label)
