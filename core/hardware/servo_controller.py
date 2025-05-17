"""
Módulo para control de servomotores.
"""
from ..serial_manager import serial_manager
from config.settings import settings


class ServoController:
    """
    Clase responsable del control de servomotores mediante comunicación serial.
    """
    
    def __init__(self):
        """
        Inicializa el controlador de servos.
        """
        self.serial_manager = serial_manager
    def enviar_angulo(self, angulo):
        if not settings.serial_enabled:
            print(f"[ServoController] Envío de ángulo {angulo}° cancelado - Comunicación serial deshabilitada")
            return False
        
        # Verificar si hay conexión o intentar conectar con los parámetros de configuración
        if not self.serial_manager.is_connected():
            print(f"[ServoController] Intentando conectar a puerto {settings.serial_port} para enviar ángulo {angulo}°")
            self.serial_manager.connect(
                settings.serial_port, 
                settings.serial_baudrate,
                timeout=1.0,
                retries=1
            )
        
        # Enviar el ángulo
        if self.serial_manager.is_connected():
            print(f"[ServoController] Ángulo enviado correctamente: {angulo}°")
            resultado = self.serial_manager.send_angle(angulo)
            if resultado:
                print(f"[ServoController] Ángulo enviado correctamente: {angulo}°")
            else:
                print(f"[ServoController] Error al enviar ángulo {angulo}°")
            return resultado
        print(f"[ServoController] No se pudo establecer conexión para enviar ángulo {angulo}°")
        return False
        
    def habilitar_control(self, habilitado=True):
        settings.serial_enabled = habilitado
        
    def esta_habilitado(self):
        return settings.serial_enabled
        
    def establecer_puerto(self, puerto):
        settings.serial_port = puerto
        if self.serial_manager.is_connected():
            self.serial_manager.disconnect()
            
    def establecer_baudios(self, baudios):
        settings.serial_baudrate = baudios
        if self.serial_manager.is_connected():
            self.serial_manager.disconnect()
