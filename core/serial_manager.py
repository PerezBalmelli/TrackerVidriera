"""
Módulo para la gestión de la comunicación serial con dispositivos ESP32.
Implementa funcionalidades para detectar, conectar y comunicarse con ESP32.
"""
import serial
import serial.tools.list_ports
import time
import json
from typing import List, Tuple, Optional, Set, Any

class SerialManager:
    """Clase para gestionar la comunicación serial con ESP32."""
    
    # VID:PID conocidos de chips utilizados en placas ESP32
    KNOWN_VIDPID: Set[Tuple[int, int]] = {
        (0x303A, 0x0002),  # ESP32-S2 CDC
        (0x303A, 0x1001),  # ESP JTAG/serial
        (0x10C4, 0xEA60),  # CP210x
        (0x1A86, 0x7523),  # CH340
    }
    
    def __init__(self):
        """Inicializa el gestor de comunicación serial."""
        self.connection: Optional[serial.Serial] = None
        self.port: str = ""
        self.baudrate: int = 115200
    
    def find_esp32_ports(self) -> List[Any]:
        """
        Detecta los puertos seriales conectados que podrían ser dispositivos ESP32.
        
        Returns:
            List: Lista de información sobre puertos ESP32 detectados.
        """
        esp_ports = []
        for port in serial.tools.list_ports.comports():
            # Si tiene VID y PID y coinciden con los conocidos de ESP32
            if hasattr(port, 'vid') and hasattr(port, 'pid') and port.vid and port.pid:
                if (port.vid, port.pid) in self.KNOWN_VIDPID:
                    esp_ports.append(port)
        
        return esp_ports
    
    def get_port_descriptions(self) -> List[Tuple[str, str]]:
        """
        Obtiene una lista de puertos ESP32 con sus descripciones para mostrar en la UI.
        
        Returns:
            List[Tuple[str, str]]: Lista de tuplas (port_name, description).
        """
        ports = self.find_esp32_ports()
        port_descriptions = []
        
        for port in ports:
            # Crear una descripción informativa
            description = f"{port.device}"
            if port.description:
                description += f" - {port.description}"
            
            # Añadir información de VID:PID si está disponible
            if hasattr(port, 'vid') and hasattr(port, 'pid') and port.vid and port.pid:
                description += f" [{hex(port.vid)[2:].upper()}:{hex(port.pid)[2:].upper()}]"
            
            port_descriptions.append((port.device, description))
            
        return port_descriptions
    
    def connect(self, port: str, baudrate: int = 115200, timeout: float = 1.0, retries: int = 1) -> bool:
        """
        Establece la conexión con el puerto serial especificado.
        
        Args:
            port (str): Nombre del puerto serial (ej: 'COM3').
            baudrate (int): Velocidad de comunicación.
            timeout (float): Tiempo de espera en segundos.
            retries (int): Número de intentos de conexión.
            
        Returns:
            bool: True si la conexión fue exitosa, False en caso contrario.
        """
        # Si ya hay una conexión abierta, la cerramos
        self.disconnect()
        
        # Intentar establecer la conexión
        for attempt in range(retries):
            try:
                self.connection = serial.Serial(port, baudrate, timeout=timeout)
                self.port = port
                self.baudrate = baudrate
                
                # Esperar que el ESP32 se reinicie después de la conexión
                time.sleep(0.5)
                
                return True
            except serial.SerialException as e:
                print(f"Error al conectar al puerto {port}: {e}")
                if attempt < retries - 1:
                    print(f"Reintentando en 1 segundo ({attempt+1}/{retries})...")
                    time.sleep(1)
        
        # Si llegamos aquí, no pudimos establecer la conexión
        return False
    
    def disconnect(self) -> None:
        """
        Cierra la conexión serial actual si está abierta.
        """
        if self.connection and self.connection.is_open:
            self.connection.close()
            self.connection = None
    
    def is_connected(self) -> bool:
        """
        Verifica si hay una conexión serial activa.
        
        Returns:
            bool: True si hay una conexión activa, False en caso contrario.
        """
        return self.connection is not None and self.connection.is_open
    
    def send_json_command(self, command: dict) -> bool:
        """
        Envía un comando en formato JSON al dispositivo.
        
        Args:
            command (dict): Diccionario con el comando a enviar.
            
        Returns:
            bool: True si el comando se envió correctamente, False en caso contrario.
        """
        if not self.is_connected():
            return False
        
        try:
            json_cmd = json.dumps(command) + '\n'
            self.connection.write(json_cmd.encode())
            return True
        except Exception as e:
            print(f"Error al enviar comando: {e}")
            return False
    
    def send_pan_tilt(self, pan: int, tilt: int) -> bool:
        """
        Envía un comando de posición para servos pan/tilt.
        
        Args:
            pan (int): Ángulo de paneo (0-180).
            tilt (int): Ángulo de inclinación (0-90).
            
        Returns:
            bool: True si el comando se envió correctamente, False en caso contrario.
        """
        command = {'pan': pan, 'tilt': tilt}
        return self.send_json_command(command)
    
    def send_angle(self, angle: int) -> bool:
        """
        Envía un comando simple con un ángulo al dispositivo.
        
        Args:
            angle (int): Ángulo a enviar (0-180).
            
        Returns:
            bool: True si el comando se envió correctamente, False en caso contrario.
        """
        if not self.is_connected():
            return False
        
        try:
            self.connection.write(f'{angle}\n'.encode())
            return True
        except Exception as e:
            print(f"Error al enviar ángulo: {e}")
            return False

# Instancia global del gestor serial
serial_manager = SerialManager()