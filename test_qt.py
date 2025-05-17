import sys
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

app = QApplication(sys.argv)
widget = QWidget()
widget.setWindowTitle("Test PyQt6")
label = QLabel("PyQt6 está funcionando!", widget)
widget.setGeometry(100, 100, 300, 50)
widget.show()
sys.exit(app.exec())