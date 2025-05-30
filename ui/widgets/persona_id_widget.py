"""
Widget flotante colapsable para seleccionar IDs de personas a seguir.
"""
import logging
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, 
    QScrollArea, QPushButton, QButtonGroup, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QRect, QEasingCurve, QPoint, QTimer
from PyQt6.QtGui import QFont, QPalette

logger = logging.getLogger(__name__)


class PersonaIdWidget(QWidget):
    """Panel flotante colapsable para seleccionar IDs de personas a seguir."""
    
    id_selected = pyqtSignal(int)  # Señal emitida cuando se selecciona un ID
    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self._position = 'top-left'  # Posición por defecto
        self._available_ids = []
        self._visible_ids = []  # IDs visibles en el frame actual
        self._last_tracking_id = None  
        self._auto_changed = False  # Flag para indicar cambio automático
        self._manual_id = None  # ID seleccionado manualmente
        self._manual_id_visible = True  # Si el ID manual está visible
        
        # Configuraciones importantes para overlay
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAutoFillBackground(True)
        
        # Asegurar que esté siempre visible por encima
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Configurar z-order alto para mantenerse por encima
        self.setStyleSheet("PersonaIdWidget { z-index: 9999; }")
        
        self._init_ui()
        self._setup_styles()
        self._make_draggable()
        
        # Elevar el widget por encima de otros elementos
        self.raise_()
        
    def _init_ui(self):
        """Inicializa la interfaz de usuario del widget."""
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)
        
        # Header con título e icono de colapso
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        
        # Título
        self.title_label = QLabel("👥 Personas disponibles")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        self.title_label.setFont(title_font)
        
        # Botón de colapso
        self.collapse_button = QToolButton()
        self.collapse_button.setText("▲")
        self.collapse_button.setFixedSize(20, 20)
        self.collapse_button.clicked.connect(self._toggle_collapse)
        
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.collapse_button)
        
        main_layout.addWidget(header_widget)
        
        # Área scrollable para los botones de ID
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setMaximumHeight(200)
        self.scroll_area.setMinimumHeight(80)
        
        # Widget contenedor para los botones
        self.buttons_widget = QWidget()
        self.buttons_layout = QVBoxLayout(self.buttons_widget)
        self.buttons_layout.setContentsMargins(4, 4, 4, 4)
        self.buttons_layout.setSpacing(2)
        
        # Grupo de botones exclusivos
        self.button_group = QButtonGroup()
        self.button_group.setExclusive(True)
        self.button_group.buttonClicked.connect(self._on_id_button_clicked)
        
        # Label para cuando no hay IDs
        self.no_ids_label = QLabel("No hay personas detectadas")
        self.no_ids_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_ids_label.setStyleSheet("color: #888; font-style: italic;")
        self.buttons_layout.addWidget(self.no_ids_label)
        
        self.scroll_area.setWidget(self.buttons_widget)
        main_layout.addWidget(self.scroll_area)
          # Configurar tamaño y comportamiento
        self.setFixedWidth(180)
        self.setMaximumHeight(300)
    def _setup_styles(self):
        """Configura los estilos del widget."""
        self.setStyleSheet("""
            PersonaIdWidget {
                background-color: rgba(40, 40, 40, 240);
                border: 2px solid #4A90E2;
                border-radius: 8px;
            }
            QLabel {
                color: white;
                background-color: transparent;
            }
            QToolButton {
                background-color: rgba(70, 70, 70, 200);
                border: 1px solid #666;
                border-radius: 3px;
                color: white;
                font-weight: bold;
                padding: 2px;
            }
            QToolButton:hover {
                background-color: rgba(90, 90, 90, 220);
            }
            QScrollArea {
                background-color: transparent;
                border: 1px solid #666;
                border-radius: 4px;
            }
            QScrollArea QWidget {
                background-color: transparent;
            }
            /* Eliminar estilos generales de QPushButton para evitar conflictos */
        """)
        
    def _make_draggable(self):
        """Hace que el widget sea arrastrable."""
        self._drag_start_position = None
        
    def mousePressEvent(self, event):
        """Inicia el arrastre del widget."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.globalPosition().toPoint() - self.pos()
            
    def mouseMoveEvent(self, event):
        """Mueve el widget durante el arrastre."""
        if (event.buttons() == Qt.MouseButton.LeftButton and 
            self._drag_start_position is not None):
            new_pos = event.globalPosition().toPoint() - self._drag_start_position
            
            # Limitar el movimiento dentro del widget padre
            if self.parent():
                parent_rect = self.parent().rect()
                widget_rect = QRect(new_pos, self.size())
                
                # Asegurar que el widget permanezca dentro del área padre
                if widget_rect.left() < 0:
                    new_pos.setX(0)
                elif widget_rect.right() > parent_rect.width():
                    new_pos.setX(parent_rect.width() - self.width())
                    
                if widget_rect.top() < 0:
                    new_pos.setY(0)
                elif widget_rect.bottom() > parent_rect.height():
                    new_pos.setY(parent_rect.height() - self.height())
                    
            self.move(new_pos)
            
    def _toggle_collapse(self):
        """Alterna entre estado colapsado y expandido."""
        self._collapsed = not self._collapsed
        
        if self._collapsed:
            self.collapse_button.setText("▼")
            self.scroll_area.hide()
            self.setFixedHeight(self.title_label.height() + 16)  # Solo header
        else:
            self.collapse_button.setText("▲")
            self.scroll_area.show()
            # Calcular altura basada en contenido
            content_height = min(200, self.buttons_widget.sizeHint().height() + 20)
            self.setFixedHeight(self.title_label.height() + content_height + 24)    
    def _on_id_button_clicked(self, button):
        """Maneja el clic en un botón de ID."""
        try:
            # Extraer el ID del texto del botón, removiendo indicadores visuales
            button_text = button.text()
            # Remover "ID " del inicio y cualquier indicador visual del final
            id_text = button_text.replace("ID ", "").split(" ")[0]  # Tomar solo la primera parte
            id_value = int(id_text)            # Registrar que este ID fue seleccionado manualmente
            self._manual_id = id_value
            self._manual_id_visible = id_value in self._visible_ids
            self._auto_changed = False
            
            self.id_selected.emit(id_value)
            logger.debug(f"ID seleccionado manualmente: {id_value}")
            print(f"ID seleccionado manualmente: {id_value}, visible: {self._manual_id_visible}")
        except (ValueError, IndexError):
            logger.error(f"Error al extraer ID del botón: {button.text()}")    
    def update_available_ids(self, ids: List[int], currently_tracking_id: Optional[int] = None, auto_change: bool = False):
        """
        Actualiza la lista de IDs disponibles.
        
        Args:
            ids: Lista de IDs de personas detectadas visualmente
            currently_tracking_id: ID que se está rastreando actualmente (puede no estar visible)
            auto_change: Indica si ocurrió un cambio automático de ID
        """
        # Debug logs
        logger.debug(f"update_available_ids called with ids={ids}, currently_tracking_id={currently_tracking_id}, auto_change={auto_change}")
        # Añadir print para depuración
        print(f"UPDATE_AVAILABLE_IDS: ids={ids}, tracking_id={currently_tracking_id}, auto_change={auto_change}")
        
        # Almacenar los IDs visibles para referencia futura
        self._visible_ids = list(ids)
        
        # Actualizar estado de visibilidad del ID manual
        if self._manual_id is not None:
            was_visible = self._manual_id_visible
            self._manual_id_visible = self._manual_id in ids
            
            # Si el ID manual dejó de ser visible, registrarlo
            # Simplificamos la condición: solo nos importa si era visible y ahora no lo es
            if was_visible and not self._manual_id_visible:
                print(f"ID seleccionado manualmente {self._manual_id} ya no es visible (tracking_id={currently_tracking_id})")
        
        # Si hubo un cambio automático, registrarlo
        if auto_change and currently_tracking_id != self._manual_id:
            self._auto_changed = True
            print(f"Cambio automático detectado: de {self._manual_id} a {currently_tracking_id}")
          # Crear conjunto completo de IDs a mostrar
        all_ids = set(ids)
        if currently_tracking_id is not None:
            all_ids.add(currently_tracking_id)
        
        # Asegurar que el ID manual siempre esté visible aunque ya no esté en la lista
        if self._manual_id is not None:
            all_ids.add(self._manual_id)
        
        logger.debug(f"all_ids after processing: {all_ids}")
        
        if set(all_ids) == set(self._available_ids):
            return  # No hay cambios

        selected_before = self.get_selected_id()
        self._available_ids = list(all_ids)
        
        # Limpiar botones existentes
        for button in self.button_group.buttons():
            self.button_group.removeButton(button)
            self.buttons_layout.removeWidget(button)
            button.deleteLater()
            
        # Remover label "no hay IDs" si existe
        if self.no_ids_label.parent():
            self.buttons_layout.removeWidget(self.no_ids_label)
            
        if not all_ids:
            # No hay IDs, mostrar mensaje
            self.buttons_layout.addWidget(self.no_ids_label)
        else:            # Crear botones para cada ID
            for id_value in sorted(all_ids):
                is_visible = id_value in ids
                is_tracking = id_value == currently_tracking_id
                
                logger.debug(f"ID {id_value}: is_visible={is_visible}, is_tracking={is_tracking}")
                
                # Determinar si este ID debe mostrarse en naranja
                show_orange = False
                button_text = f"ID {id_value}"
                
                # Caso 1: Es el ID rastreado actualmente pero no está visible
                if is_tracking and not is_visible:
                    show_orange = True
                    button_text += " (🔍)"
                    print(f"Marcando ID {id_value} como naranja (tracking pero no visible)")
                
                # Caso 2: Es el ID seleccionado manualmente y ya no está visible
                if id_value == self._manual_id and not self._manual_id_visible:
                    show_orange = True
                    button_text += " (🔍)"
                    print(f"Marcando ID {id_value} como naranja (manual y no visible)")
                
                # Caso 3: Hubo un cambio automático y este es el nuevo ID
                if self._auto_changed and id_value == currently_tracking_id and id_value != self._manual_id:
                    show_orange = True
                    button_text += " (🔄)"  # Indicador de cambio automático
                    print(f"Marcando ID {id_value} como naranja (cambio automático)")
                
                id_button = QPushButton(button_text)
                id_button.setCheckable(True)
                
                # Aplicar estilo naranja si corresponde
                if show_orange:
                    # ID siendo rastreado pero no visible, o ID seleccionado automáticamente
                    id_button.setStyleSheet("""
                        QPushButton {
                            background-color: rgba(255, 165, 0, 150) !important;
                            border: 2px solid #FFA500 !important;
                            color: white !important;
                            font-weight: bold !important;
                            padding: 6px 12px !important;
                            border-radius: 4px !important;
                            min-height: 25px !important;
                        }
                        QPushButton:checked {
                            background-color: rgba(255, 140, 0, 220) !important;
                            border: 2px solid #FF8C00 !important;
                        }
                        QPushButton:hover {
                            background-color: rgba(255, 165, 0, 180) !important;
                        }
                    """)
                else:
                    # ID visible normalmente
                    id_button.setStyleSheet("""
                        QPushButton {
                            background-color: rgba(70, 130, 180, 150) !important;
                            border: 2px solid #4682B4 !important;
                            color: white !important;
                            font-weight: bold !important;
                            padding: 6px 12px !important;
                            border-radius: 4px !important;
                            min-height: 25px !important;
                        }
                        QPushButton:checked {
                            background-color: rgba(34, 139, 34, 220) !important;
                            border: 2px solid #32CD32 !important;
                        }
                        QPushButton:hover {
                            background-color: rgba(100, 150, 200, 220) !important;
                        }
                    """)
                
                self.button_group.addButton(id_button)
                self.buttons_layout.addWidget(id_button)

            # Restaurar selección previa si existe
            if selected_before in all_ids:
                for btn in self.button_group.buttons():
                    if f"ID {selected_before}" in btn.text():
                        btn.setChecked(True)
                        break
            elif currently_tracking_id is not None:
                # Si no hay selección previa pero hay un ID siendo rastreado, seleccionarlo
                for btn in self.button_group.buttons():
                    if f"ID {currently_tracking_id}" in btn.text():
                        btn.setChecked(True)
                        break

                
        # Ajustar altura si no está colapsado
        if not self._collapsed:
            # content_height = min(200, self.buttons_widget.sizeHint().height() + 20)
            # self.setFixedHeight(self.title_label.height() + content_height + 24)
            QTimer.singleShot(0, self._recalc_size)
            
        logger.debug(f"IDs actualizados: {ids}")
        
    def clear_selection(self):
        """Desmarca todos los IDs seleccionados."""
        if self.button_group.checkedButton():
            self.button_group.setExclusive(False)
            self.button_group.checkedButton().setChecked(False)
            self.button_group.setExclusive(True)
            
    def set_position(self, position: str):
        """
        Establece la posición del widget en su contenedor padre.
        
        Args:
            position: 'top-left', 'top-right', 'bottom-left', 'bottom-right'
        """
        self._position = position
        if self.parent():
            self._update_position()
            
    def _update_position(self):
        """Actualiza la posición del widget basada en la configuración."""
        if not self.parent():
            return
            
        parent_rect = self.parent().rect()
        margin = 10
        
        if self._position == 'top-left':
            self.move(margin, margin)
        elif self._position == 'top-right':
            self.move(parent_rect.width() - self.width() - margin, margin)
        elif self._position == 'bottom-left':
            self.move(margin, parent_rect.height() - self.height() - margin)
        elif self._position == 'bottom-right':
            self.move(parent_rect.width() - self.width() - margin, 
                     parent_rect.height() - self.height() - margin)
                     
    def resizeEvent(self, event):
        """Maneja el redimensionamiento del widget padre."""
        super().resizeEvent(event)
        if self.parent():
            self._update_position()
    def showEvent(self, event):
        """Maneja la visualización del widget."""
        super().showEvent(event)
        self._update_position()
        self.raise_()  # Asegurar que esté por encima cuando se muestre
        
    def paintEvent(self, event):
        """Maneja el pintado del widget para asegurar visibilidad."""
        super().paintEvent(event)
        # Asegurar que estemos por encima después de cada repintado
        if self.parent():
            self.raise_()
        
    def get_selected_id(self) -> Optional[int]:
        """
        Obtiene el ID actualmente seleccionado.
        
        Returns:
            ID seleccionado o None si no hay selección
        """
        checked_button = self.button_group.checkedButton()
        if checked_button:
            try:
                # Extraer el ID del texto del botón, removiendo indicadores visuales
                button_text = checked_button.text()
                id_text = button_text.replace("ID ", "").split(" ")[0]  # Tomar solo la primera parte
                return int(id_text)
            except (ValueError, IndexError):
                return None
        return None
    def ensure_visibility(self):
        """
        Asegura que el widget esté visible por encima de otros elementos.
        Útil para llamar después de actualizaciones del widget padre.
        """
        if self.isVisible():
            self.raise_()
            self.setFocus(Qt.FocusReason.OtherFocusReason)  # Intentar ganar foco
            self.update()  # Forzar repintado
            self.repaint()  # Forzar repintado inmediato
    def _recalc_size(self):
        """Recalcula la altura cuando el layout ya está resuelto."""
        header_h = self.title_label.sizeHint().height()
        content_h = min(200, self.buttons_widget.sizeHint().height() + 20)
        self.setFixedHeight(header_h + content_h + 24)