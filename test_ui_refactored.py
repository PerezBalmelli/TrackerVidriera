"""
Script para probar la versión refactorizada de la interfaz de usuario.
"""
import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window_refactored import MainWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())
