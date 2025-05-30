"""
Widget para la visualización de video en la aplicación TrackerVidriera.
"""
import cv2
import logging # Added
from typing import List
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal # Added pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from .persona_id_widget import PersonaIdWidget

logger = logging.getLogger(__name__) # Added

class VideoDisplayWidget(QWidget):
    """Widget para la visualización de frames de video."""
    display_error = pyqtSignal(str) # Added signal for display errors
    person_id_selected = pyqtSignal(int)  # Señal para ID de persona seleccionado

    def __init__(self, parent=None):
        super().__init__(parent)
        self.persona_id_widget = None  # Se inicializará en _init_ui
        self._init_ui()
        self._setup_persona_id_widget()

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

    def _setup_persona_id_widget(self):
        """Inicializa y configura el widget de selección de personas."""
        self.persona_id_widget = PersonaIdWidget(parent=self.main_camera_container)
        self.persona_id_widget.id_selected.connect(self._on_person_id_selected)
        self.persona_id_widget.set_position('top-left')  # Posición por defecto
        
        # Asegurar que el widget esté visible y por encima
        self.persona_id_widget.show()
        self.persona_id_widget.raise_()
        self.persona_id_widget.ensure_visibility()
        
        # Usar un timer para asegurar visibilidad periódica durante el procesamiento
        from PyQt6.QtCore import QTimer
        self._visibility_timer = QTimer()
        self._visibility_timer.timeout.connect(self._ensure_panel_visibility)
        self._visibility_timer.start(1000)  # Cada segundo
        
        # Agregar algunos IDs de prueba para verificar que funciona
        self.persona_id_widget.update_available_ids([1, 2, 3])
        
    def _ensure_panel_visibility(self):
        """Asegura periódicamente que el panel esté visible."""
        if self.persona_id_widget and self.persona_id_widget.isVisible():
            self.persona_id_widget.ensure_visibility()
        
    def _on_person_id_selected(self, person_id: int):
        """Maneja la selección de un ID de persona."""
        logger.info(f"Persona seleccionada para seguir: ID {person_id}")
        self.person_id_selected.emit(person_id)

    def _display_single_frame(self, frame, label_widget):
        if frame is None:
            label_widget.clear()
            if label_widget == self.display_label:
                label_widget.setText("Cámara Principal no disponible")
            else:
                label_widget.setText("Cámara Móvil no disponible")
            return

        try:
            # Ensure frame is not empty
            if frame.size == 0:
                logger.warning("Attempted to display an empty frame.")
                label_widget.setText("Frame vacío recibido")
                return

            # Ensure frame has 3 channels for BGR2RGB conversion
            if frame.ndim == 2 or (frame.ndim == 3 and frame.shape[2] == 1): # Grayscale
                 rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
            elif frame.shape[2] == 4: # BGRA
                 rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
            elif frame.shape[2] == 3: # BGR
                 rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                logger.error(f"Unsupported frame shape for display: {frame.shape}")
                label_widget.setText("Formato de frame no soportado")
                self.display_error.emit(f"Formato de frame no soportado: {frame.shape}")
                return


            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            # Escalar al tamaño del QLabel contenedor, manteniendo aspect ratio
            scaled_pixmap = pixmap.scaled(
                label_widget.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            label_widget.setPixmap(scaled_pixmap)
              # Asegurar que el panel de personas esté siempre por encima después de actualizar el frame
            if label_widget == self.display_label and self.persona_id_widget:
                self.persona_id_widget.raise_()
                self.persona_id_widget.ensure_visibility()
                
        except cv2.error as e: # Catch specific OpenCV errors
            logger.error(f"OpenCV error displaying frame: {e}", exc_info=True)
            label_widget.setText("Error de OpenCV al mostrar frame")
            self.display_error.emit(f"OpenCV error: {e}")
        except Exception as e:
            logger.error(f"Error displaying frame: {e}", exc_info=True)
            label_widget.setText("Error al mostrar frame")
            self.display_error.emit(f"Error al mostrar frame: {e}")


    @pyqtSlot(object)
    def display_frame(self, frame):
        """Muestra un frame en el label de la cámara principal."""
        self._display_single_frame(frame, self.display_label)

    @pyqtSlot(object)
    def display_second_frame(self, frame):
        """Muestra un frame en el label de la segunda cámara."""
        self._display_single_frame(frame, self.second_display_label)
        
    # --- Métodos para interactuar con el panel de personas ---
    def update_available_person_ids(self, ids: List[int], currently_tracking_id: int = None, auto_change: bool = False):
        """
        Actualiza la lista de IDs de personas disponibles para seguir.
        
        Args:
            ids: Lista de IDs de personas detectadas en el frame actual
            currently_tracking_id: ID que se está rastreando actualmente (puede no estar visible)
            auto_change: Indica si ocurrió un cambio automático de ID
        """
        if self.persona_id_widget:
            self.persona_id_widget.update_available_ids(ids, currently_tracking_id, auto_change)
            
    def clear_person_selection(self):
        """Limpia la selección actual de persona."""
        if self.persona_id_widget:
            self.persona_id_widget.clear_selection()
            
    def set_person_panel_position(self, position: str):
        """
        Establece la posición del panel de personas.
        
        Args:
            position: 'top-left', 'top-right', 'bottom-left', 'bottom-right'
        """
        if self.persona_id_widget:
            self.persona_id_widget.set_position(position)
            
    def get_selected_person_id(self):
        """
        Obtiene el ID de la persona actualmente seleccionada.
        
        Returns:
            int o None: ID seleccionado o None si no hay selección
        """
        if self.persona_id_widget:
            return self.persona_id_widget.get_selected_id()
        return None
        
    def set_person_panel_visible(self, visible: bool):
        """
        Muestra u oculta el panel de selección de personas.
        
        Args:
            visible: True para mostrar, False para ocultar
        """        
        if self.persona_id_widget:
            self.persona_id_widget.setVisible(visible)
            
    def resizeEvent(self, event):
        """Maneja el redimensionamiento del widget para reposicionar el panel."""
        super().resizeEvent(event)
        if self.persona_id_widget:
            # Forzar actualización de posición del panel flotante
            self.persona_id_widget._update_position()