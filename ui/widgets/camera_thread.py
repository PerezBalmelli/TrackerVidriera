"""
Módulo para el thread de captura de cámara en la aplicación TrackerVidriera.
"""
import logging
import cv2
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class CameraThread(QThread):
    """Thread para capturar frames de una cámara en segundo plano."""
    frame_received = pyqtSignal(object)
    camera_info_signal = pyqtSignal(str)
    camera_error_signal = pyqtSignal(str)

    def __init__(self, camera_id_tuple, parent=None):  # camera_id_tuple = (id, descriptive_name)
        super().__init__(parent)
        self.camera_id = camera_id_tuple[0]
        self.camera_name = camera_id_tuple[1]
        self.running = False
        self.cap = None
        self.fps = 30.0  # Default FPS

    def run(self):
        try:
            logger.info(f"Intentando abrir cámara ID {self.camera_id} ({self.camera_name}) para previsualización...")
            # Try different backends if default fails, especially on Windows
            backends = [cv2.CAP_ANY, cv2.CAP_DSHOW, cv2.CAP_MSMF]
            for backend in backends:
                self.cap = cv2.VideoCapture(self.camera_id, backend)
                if self.cap.isOpened():
                    logger.info(f"Cámara {self.camera_id} ({self.camera_name}) abierta con backend {backend}.")
                    break

            if not self.cap or not self.cap.isOpened():
                err_msg = f"Error: No se pudo abrir la cámara ID {self.camera_id} ({self.camera_name}) para previsualización."
                logger.error(err_msg)
                self.camera_error_signal.emit(err_msg)
                return

            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            detected_fps = self.cap.get(cv2.CAP_PROP_FPS)
            if detected_fps > 0: self.fps = detected_fps

            info_text = f"{self.camera_name}: {width}x{height} @ {self.fps:.2f} FPS"
            logger.info(
                f"Cámara {self.camera_id} ({self.camera_name}) (previsualización) abierta: {width}x{height} @ {self.fps:.2f} FPS")
            self.camera_info_signal.emit(info_text)

            self.running = True
            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    self.frame_received.emit(frame)
                else:
                    self.msleep(int(1000 / self.fps / 2))  # Wait a bit if no frame, shorter than full frame time

                sleep_duration = max(1, int(1000 / self.fps) - 10)  # Heuristic for sleep
                self.msleep(sleep_duration)

        except Exception as e:
            err_msg = f"Error en CameraThread (ID {self.camera_id}, {self.camera_name}, previsualización): {str(e)}"
            logger.error(err_msg, exc_info=True)
            self.camera_error_signal.emit(err_msg)
        finally:
            if self.cap:
                logger.info(f"Liberando cámara ID {self.camera_id} ({self.camera_name}) (previsualización).")
                self.cap.release()
            self.cap = None
            logger.info(f"CameraThread (ID {self.camera_id}, {self.camera_name}, previsualización) finalizado.")

    def stop(self):
        logger.info(f"Deteniendo CameraThread (previsualización) para ID {self.camera_id} ({self.camera_name})...")
        self.running = False
        if self.isRunning():
            self.wait(1000)
        if self.cap and self.cap.isOpened():
            logger.info(
                f"Asegurando liberación de cámara ID {self.camera_id} ({self.camera_name}) (previsualización) al detener.")
            self.cap.release()
        self.cap = None