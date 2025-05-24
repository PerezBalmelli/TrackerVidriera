"""
Widget para la configuración de comunicación serial en la aplicación TrackerVidriera.
"""
import logging # Added
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QComboBox, QCheckBox
)
from PyQt6.QtCore import pyqtSignal

logger = logging.getLogger(__name__) # Added

class SerialConfigWidget(QWidget):
    """Widget para configurar los parámetros de comunicación serial."""

    serial_config_changed = pyqtSignal(dict)
    status_message = pyqtSignal(str, int)

    def __init__(self, serial_manager, parent=None):
        super().__init__(parent)
        self.serial_manager = serial_manager
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Grupo de configuración serial
        serial_group = QGroupBox("Comunicación Serial ESP32")
        serial_layout = QFormLayout(serial_group)

        # Panel para selección de puerto COM
        port_panel = QWidget()
        port_layout = QHBoxLayout(port_panel)
        port_layout.setContentsMargins(0, 0, 0, 0)

        # Combo para selección de puertos
        self.serial_port_combo = QComboBox()
        self.serial_port_combo.setMinimumWidth(200)
        self.serial_port_combo.setToolTip("Seleccione el puerto COM del ESP32")

        # Botón para refrescar lista de puertos
        refresh_ports_button = QPushButton("🔄")
        refresh_ports_button.setToolTip("Actualizar lista de puertos COM")
        refresh_ports_button.setFixedWidth(30)
        refresh_ports_button.clicked.connect(self.refresh_serial_ports)

        # Botón para probar la conexión serial
        self.test_serial_button = QPushButton("Probar Conexión")
        self.test_serial_button.clicked.connect(self._test_serial_connection)

        port_layout.addWidget(self.serial_port_combo)
        port_layout.addWidget(refresh_ports_button)
        port_layout.addWidget(self.test_serial_button)

        # Velocidad de comunicación
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])

        # Seleccionar 115200 por defecto
        index = self.baudrate_combo.findText("115200")
        if index >= 0:
            self.baudrate_combo.setCurrentIndex(index)

        # CheckBox para habilitar/deshabilitar comunicación serial
        self.serial_enabled_check = QCheckBox("Activo")
        self.serial_enabled_check.setChecked(True)

        # Layout para baudrate y checkbox
        baudrate_panel = QWidget()
        baudrate_layout = QHBoxLayout(baudrate_panel)
        baudrate_layout.setContentsMargins(0, 0, 0, 0)
        baudrate_layout.addWidget(self.baudrate_combo)
        baudrate_layout.addWidget(self.serial_enabled_check)

        # Estado de la conexión
        self.serial_status_label = QLabel("Sin conectar")

        # Añadir al layout principal
        serial_layout.addRow("Puerto COM:", port_panel)
        serial_layout.addRow("Velocidad:", baudrate_panel)
        serial_layout.addRow("Estado:", self.serial_status_label)

        layout.addWidget(serial_group)

        # Cargar puertos disponibles
        self.refresh_serial_ports()

    def refresh_serial_ports(self):
        """Detecta y actualiza la lista de puertos seriales disponibles."""
        self.status_message.emit("Buscando puertos ESP32 disponibles...", 2000)
        self.serial_port_combo.clear()

        # Obtener descripciones de puertos ESP32 desde el gestor serial
        port_descriptions = self.serial_manager.get_port_descriptions()

        if not port_descriptions:
            # Consider not adding a default COM port automatically if none are detected.
            # self.serial_port_combo.addItem("COM3 (predeterminado)", "COM3") # Consider removing or making conditional
            self.status_message.emit("No se detectaron dispositivos ESP32.", 3000)
            self.serial_status_label.setText("Sin conectar (No detectado)")
        else:
            # Añadir los puertos detectados al combo
            for port, description in port_descriptions:
                self.serial_port_combo.addItem(description, port)
            self.status_message.emit(f"Se encontraron {len(port_descriptions)} puertos ESP32", 3000)

    def _test_serial_connection(self):
        """Prueba la conexión con el ESP32 seleccionado."""
        port = self.serial_port_combo.currentData()
        if not port:
            self.status_message.emit("Error: Seleccione un puerto válido para probar.", 3000)
            self.serial_status_label.setText("Error: Puerto no seleccionado")
            return

        try:
            baudrate = int(self.baudrate_combo.currentText())
        except ValueError:
            self.status_message.emit("Error: Baudrate inválido", 3000)
            self.serial_status_label.setText("Error: Baudrate inválido")
            return

        self.status_message.emit(f"Intentando conectar a {port} a {baudrate} baudios...", 0)
        self.serial_status_label.setText(f"Probando {port}...")

        if self.serial_manager.connect(port, baudrate, timeout=1.0, retries=1):  # 1 intento para prueba rápida
            self.serial_status_label.setText(f"Conectado a {port}")
            self.status_message.emit(f"Conexión establecida con {port} a {baudrate} baudios", 3000)

            # Desconectar después de la prueba para liberar el puerto
            self.serial_manager.disconnect()
            self.serial_status_label.setText(f"Desconectado (Prueba OK)")
        else:
            self.serial_status_label.setText("Error de conexión")
            self.status_message.emit(f"No se pudo conectar a {port}. Verifique la conexión y los permisos.", 5000)

    # Métodos públicos para acceder desde la ventana principal
    def get_serial_port(self):
        """Retorna el puerto COM seleccionado (puede ser None)."""
        return self.serial_port_combo.currentData() # Modified: Removed "COM3" fallback

    def set_serial_port(self, port):
        """Establece el puerto COM."""
        port_found = False
        if port: # Ensure port is not None or empty
            for i in range(self.serial_port_combo.count()):
                if self.serial_port_combo.itemData(i) == port:
                    self.serial_port_combo.setCurrentIndex(i)
                    port_found = True
                    break

            if not port_found:
                # Si el puerto guardado no está en la lista, lo agregamos
                self.serial_port_combo.addItem(f"{port} (manual)", port)
                self.serial_port_combo.setCurrentIndex(self.serial_port_combo.count() - 1)
        # if port is None or empty, or not found and not added, the selection remains or is cleared.

    def get_baudrate(self):
        """Retorna el baudrate seleccionado."""
        try:
            return int(self.baudrate_combo.currentText())
        except ValueError:
            logger.warning(f"Baudrate inválido en ComboBox: {self.baudrate_combo.currentText()}. Defecto a 115200.")
            return 115200 # Return a sensible default if parsing fails

    def set_baudrate(self, baudrate):
        """Establece el baudrate."""
        index = self.baudrate_combo.findText(str(baudrate))
        if index >= 0:
            self.baudrate_combo.setCurrentIndex(index)

    def is_serial_enabled(self):
        """Retorna si la comunicación serial está habilitada."""
        return self.serial_enabled_check.isChecked()

    def set_serial_enabled(self, enabled):
        """Establece si la comunicación serial está habilitada."""
        self.serial_enabled_check.setChecked(enabled)