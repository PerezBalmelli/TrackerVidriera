"""
Widget para implementar un panel colapsable.
Permite mostrar/ocultar el contenido de un panel con una animación.
"""
from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, pyqtSignal, QSize, Qt

class CollapsiblePanelWidget(QWidget):
    """Implementa un panel que puede colapsarse y expandirse con animaciones."""
    
    collapsed = pyqtSignal(bool)  # Señal emitida al colapsar (True) o expandir (False)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        self.animation_duration = 300  # ms
        self.panel_width = 0
        self.toggle_button = None
        self.content_widget = None
        self.expand_button = None
        
    def setup(self, content_widget, initial_width=250):
        """
        Configura el panel con el widget de contenido.
        
        Args:
            content_widget (QWidget): Widget que se mostrará/ocultará.
            initial_width (int): Ancho inicial del panel.
        """
        self.content_widget = content_widget
        self.panel_width = initial_width
        content_widget.setMinimumWidth(initial_width // 2)
        content_widget.setMaximumWidth(initial_width * 2)
        
        # Crear el botón de expansión
        self.expand_button = QPushButton(">")
        self.expand_button.setFixedSize(20, 60)
        self.expand_button.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-left: none;
                border-top-right-radius: 10px;
                border-bottom-right-radius: 10px;
            }
            QPushButton:hover { background-color: #e0e0e0; }
        """)
        self.expand_button.clicked.connect(self.toggle)
        self.expand_button.hide()  # Inicialmente oculto
        
    def toggle(self):
        """Alterna entre estado colapsado y expandido."""
        if self.is_collapsed:
            self.expand()
        else:
            self.collapse()
            
    def collapse(self):
        """Colapsa el panel con animación."""
        if self.is_collapsed:
            return
            
        # Guardar el ancho actual para la expansión
        self.panel_width = self.content_widget.width()
        
        # Crear animación
        self.animation = QPropertyAnimation(self.content_widget, b"maximumWidth")
        self.animation.setDuration(self.animation_duration)
        self.animation.setStartValue(self.content_widget.width())
        self.animation.setEndValue(0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.animation.start()
        
        self.is_collapsed = True
        self.expand_button.setText(">")
        self.expand_button.show()
        
        # Emitir señal
        self.collapsed.emit(True)
        
    def expand(self):
        """Expande el panel con animación."""
        if not self.is_collapsed:
            return
            
        # Crear animación
        self.animation = QPropertyAnimation(self.content_widget, b"maximumWidth")
        self.animation.setDuration(self.animation_duration)
        self.animation.setStartValue(0)
        self.animation.setEndValue(self.panel_width)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.animation.start()
        
        self.is_collapsed = False
        self.expand_button.setText("<")
        
        # Emitir señal
        self.collapsed.emit(False)
