"""
Punto de entrada principal para la aplicación TrackerVidriera.
Esta aplicación permite el procesamiento y seguimiento de personas en videos.
"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
import os
from pathlib import Path

# Importamos nuestros módulos
from ui.main_window_refactored import MainWindow


def main():
    """Función principal que inicia la aplicación."""
    # Crear la aplicación Qt
    app = QApplication(sys.argv)
    app.setApplicationName("TrackerVidriera")
    
    # Establecer la hoja de estilo para toda la aplicación
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #f5f5f5;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #cccccc;
            border-radius: 5px;
            margin-top: 1ex;
            padding: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
            background-color: #f5f5f5;
        }
        QPushButton {
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 5px 10px;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        QPushButton:disabled {
            background-color: #cccccc;
        }
        QLabel {
            color: #2c3e50;
        }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 3px 5px;
            background-color: white;
        }
        QStatusBar {
            background-color: #ecf0f1;
            color: #2c3e50;
        }
    """)
    
    # Crear y mostrar la ventana principal
    window = MainWindow()
    window.show()
    
    # Ejecutar el bucle de eventos de la aplicación
    sys.exit(app.exec() if hasattr(app, 'exec') else app.exec_())


if __name__ == "__main__":
    main()