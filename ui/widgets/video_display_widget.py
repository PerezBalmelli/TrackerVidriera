"""
Widget para la visualización de video en la aplicación TrackerVidriera.
"""
import cv2
import logging # Added
import numpy as np  # Importado para trabajar con coordenadas y detecciones
from typing import List, Dict, Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal # Added pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QMouseEvent
from .persona_id_widget import PersonaIdWidget

logger = logging.getLogger(__name__) # Added

class VideoDisplayWidget(QWidget):
    """Widget para la visualización de frames de video."""
    display_error = pyqtSignal(str) # Added signal for display errors
    person_id_selected = pyqtSignal(int)  # Señal para ID de persona seleccionado
    person_clicked = pyqtSignal(int, int)  # Señal emitida cuando se hace clic en una coordenada (x, y)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.persona_id_widget = None  # Se inicializará en _init_ui
        self._init_ui()
        self._setup_persona_id_widget()
        
        # Añadir atributos para seguimiento de personas y detecciones
        self.current_detections = {}  # Diccionario para mapear IDs a cajas delimitadoras {id: (x1, y1, x2, y2)}
        self.current_frame_size = (0, 0)  # Tamaño del frame actual (ancho, alto)
        self.displayed_pixmap_rect = None  # Rectángulo donde se muestra la imagen escalada
        self.enable_click_selection = True  # Habilitar/deshabilitar selección por clic
        
        # Habilitar seguimiento de mouse en el QLabel para recibir eventos
        self.display_label.setMouseTracking(True)
        self.display_label.mousePressEvent = self._on_main_display_clicked
        self.display_label.mouseMoveEvent = self._on_main_display_hover

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
        # pero con una frecuencia baja para no interrumpir la interacción del usuario
        from PyQt6.QtCore import QTimer
        self._visibility_timer = QTimer()
        self._visibility_timer.timeout.connect(self._ensure_panel_visibility)
        self._visibility_timer.start(15000)  # Reducido a cada 15 segundos para minimizar interrupciones
        
        # Agregar algunos IDs de prueba para verificar que funciona
        self.persona_id_widget.update_available_ids([1, 2, 3])
        
    def _ensure_panel_visibility(self):
        """Asegura periódicamente que el panel esté visible."""
        if self.persona_id_widget and self.persona_id_widget.isVisible():
            self.persona_id_widget.raise_()
        
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

            # Guardar el tamaño del frame original para el mapeo de coordenadas
            if label_widget == self.display_label:
                self.current_frame_size = (w, h)

            # Escalar al tamaño del QLabel contenedor, manteniendo aspect ratio
            scaled_pixmap = pixmap.scaled(
                label_widget.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            label_widget.setPixmap(scaled_pixmap)
            
            # Si es la cámara principal, guardar el rectángulo donde se muestra la imagen
            # para poder mapear correctamente las coordenadas de clic
            if label_widget == self.display_label:
                # Calcular el rectángulo de la imagen escalada dentro del QLabel
                label_size = label_widget.size()
                pixmap_size = scaled_pixmap.size()
                
                # Calcular posición (centrada en el QLabel)
                x_offset = (label_size.width() - pixmap_size.width()) // 2
                y_offset = (label_size.height() - pixmap_size.height()) // 2
                
                # Guardar el rectángulo donde se muestra la imagen
                from PyQt6.QtCore import QRect
                self.displayed_pixmap_rect = QRect(
                    x_offset, y_offset, 
                    pixmap_size.width(), pixmap_size.height()
                )
                
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
            
    def update_detections_from_boxes(self, boxes, frame_size):
        """
        Actualiza las detecciones a partir de las cajas (boxes) del modelo YOLO.
        
        Args:
            boxes: Objeto boxes de YOLO con las detecciones 
            frame_size: Tupla (ancho, alto) del frame original
        """
        if boxes is None or not hasattr(boxes, 'id') or not hasattr(boxes, 'xyxy') or boxes.id is None:
            self.current_detections = {}
            return
            
        detections = {}
        for i, id_tensor in enumerate(boxes.id):
            if i < len(boxes.xyxy):
                person_id = int(id_tensor.item())
                coords = boxes.xyxy[i].tolist()
                x1, y1, x2, y2 = map(int, coords)
                detections[person_id] = (x1, y1, x2, y2)
                
        self.current_detections = detections
        self.current_frame_size = frame_size

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

    def _on_main_display_clicked(self, event: QMouseEvent):
        """
        Maneja los clics en la visualización de la cámara principal.
        Identifica si el clic fue sobre una persona detectada y la selecciona.
        
        Args:
            event: Evento de clic del mouse
        """
        if not self.enable_click_selection or not self.current_detections:
            return
            
        # Verificar que tenemos un pixmap y conocemos su ubicación en el QLabel
        if not self.displayed_pixmap_rect or self.current_frame_size == (0, 0):
            logger.warning("No hay información suficiente para determinar la posición del clic")
            return
        
        # Obtener las coordenadas del clic relativas al QLabel
        click_x, click_y = event.pos().x(), event.pos().y()
        
        # Mapear coordenadas del clic a coordenadas originales del frame
        scaled_x = self._map_coordinate(click_x, self.displayed_pixmap_rect.left(), 
                                        self.displayed_pixmap_rect.right(), 0, self.current_frame_size[0])
        scaled_y = self._map_coordinate(click_y, self.displayed_pixmap_rect.top(), 
                                        self.displayed_pixmap_rect.bottom(), 0, self.current_frame_size[1])
        
        logger.debug(f"Clic en ({click_x}, {click_y}) mapeado a ({scaled_x}, {scaled_y}) en frame original")
        
        # Emitir señal con las coordenadas del clic para debugging o funcionalidades adicionales
        self.person_clicked.emit(int(scaled_x), int(scaled_y))
        
        # Buscar qué persona fue seleccionada (si alguna)
        selected_id = self._find_person_at_position(scaled_x, scaled_y)
        
        if selected_id is not None:
            logger.info(f"Persona seleccionada por clic: ID {selected_id}")
            # Actualizamos la selección en el panel de IDs
            if self.persona_id_widget:
                # Buscamos el botón correspondiente y lo marcamos
                for btn in self.persona_id_widget.button_group.buttons():
                    if f"ID {selected_id}" in btn.text():
                        btn.setChecked(True)
                        break
            # Emitimos la señal de selección
            self.person_id_selected.emit(selected_id)
    
    def _find_person_at_position(self, x: float, y: float) -> Optional[int]:
        """
        Determina si una coordenada (x, y) está dentro de alguna de las cajas de detección.
        
        Args:
            x: Coordenada X en el frame original
            y: Coordenada Y en el frame original
            
        Returns:
            ID de la persona si el punto está dentro de una caja, None en caso contrario
        """
        for person_id, bbox in self.current_detections.items():
            x1, y1, x2, y2 = bbox
            if x1 <= x <= x2 and y1 <= y <= y2:
                return person_id
        return None
    
    def _map_coordinate(self, value: float, display_min: float, display_max: float, 
                        original_min: float, original_max: float) -> float:
        """
        Mapea una coordenada desde el espacio de visualización al espacio original.
        
        Args:
            value: Valor a mapear
            display_min: Valor mínimo en el espacio de visualización
            display_max: Valor máximo en el espacio de visualización
            original_min: Valor mínimo en el espacio original
            original_max: Valor máximo en el espacio original
            
        Returns:
            Valor mapeado al espacio original
        """
        # Prevenir división por cero
        if display_max == display_min:
            return original_min
            
        # Mapeo lineal
        display_range = display_max - display_min
        original_range = original_max - original_min
        
        # Normalizar valor en el espacio de visualización y luego escalar al espacio original
        normalized = (value - display_min) / display_range
        return original_min + (normalized * original_range)
        
    def update_detections(self, detections: Dict[int, tuple]):
        """
        Actualiza las detecciones actuales para habilitar la selección por clic.
        
        Args:
            detections: Diccionario que mapea IDs a bounding boxes (x1, y1, x2, y2)
        """
        self.current_detections = detections

        # Actualizar el rectángulo de la imagen mostrada si es necesario
        if self.display_label.pixmap() is not None:
            self.displayed_pixmap_rect = self.display_label.pixmap().rect()
        else:
            self.displayed_pixmap_rect = None

    def _on_main_display_hover(self, event: QMouseEvent):
        """
        Maneja el movimiento del mouse sobre el display para mostrar feedback visual.
        Cambia el cursor a una mano cuando se encuentra sobre una persona detectada.
        
        Args:
            event: Evento de movimiento del mouse
        """
        if not self.enable_click_selection or not self.current_detections or not self.displayed_pixmap_rect:
            return
            
        # Obtener coordenadas del puntero y mapearlas al frame original
        mouse_x, mouse_y = event.pos().x(), event.pos().y()
        
        # Solo procesar si estamos dentro del área de la imagen
        if not self.displayed_pixmap_rect.contains(mouse_x, mouse_y):
            self.display_label.setCursor(Qt.CursorShape.ArrowCursor)
            return
            
        # Mapear coordenadas
        scaled_x = self._map_coordinate(mouse_x, self.displayed_pixmap_rect.left(), 
                                       self.displayed_pixmap_rect.right(), 0, self.current_frame_size[0])
        scaled_y = self._map_coordinate(mouse_y, self.displayed_pixmap_rect.top(), 
                                       self.displayed_pixmap_rect.bottom(), 0, self.current_frame_size[1])
        
        # Verificar si el cursor está sobre alguna persona
        person_id = self._find_person_at_position(scaled_x, scaled_y)
        
        # Cambiar cursor según si estamos sobre una persona o no
        if person_id is not None:
            self.display_label.setCursor(Qt.CursorShape.PointingHandCursor)
            self.display_label.setToolTip(f"Hacer clic para seleccionar persona ID {person_id}")
        else:
            self.display_label.setCursor(Qt.CursorShape.ArrowCursor)
            self.display_label.setToolTip("")