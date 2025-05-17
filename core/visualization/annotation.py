"""
Módulo para anotaciones y visualizaciones en frames de video.
"""
import cv2
from ..hardware.servo_controller import ServoController


class FrameAnnotator:
    """
    Clase responsable de añadir anotaciones visuales a los frames de video.
    """
    
    def __init__(self):
        """
        Inicializa el anotador de frames.
        """
        self.servo_controller = ServoController()
        
    def annotate_frame(self, frame, boxes, rastreo_id, ultima_coords, ids_globales, 
                       frame_width, controlar_servo=False):
        annotated = frame.copy()
        coordenadas_texto = ""
        nueva_ultima_coords = ultima_coords

        # Verifica que hay IDs y cajas de detección
        if boxes.id is not None and boxes.xyxy is not None:
            # Procesa cada detección
            for i, id_tensor in enumerate(boxes.id):
                id_ = int(id_tensor.item())
                # Añade este ID al conjunto global
                ids_globales.add(id_)
                # Si es el ID que estamos rastreando
                if id_ == rastreo_id and i < len(boxes.xyxy):
                    coords = boxes.xyxy[i].tolist()
                    # Si las coordenadas cambiaron
                    if coords != ultima_coords:
                        print(f"ID {id_} coordenadas: {coords}")
                        nueva_ultima_coords = coords
                    x1, y1, x2, y2 = map(int, coords)
                    x_centro = (x1 + x2) // 2
                      # Control del servo si está habilitado
                    if controlar_servo:
                        comando = self._convertir_a_comando(x_centro, frame_width)
                        print(f"[FrameAnnotator] Calculando posición: centro_x={x_centro}/{frame_width} → ángulo={comando}°")
                        self.servo_controller.enviar_angulo(comando)
                    
                    # Añade texto de rastreo
                    cv2.putText(annotated, f"Rastreando ID: {id_}", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    coordenadas_texto = f"Coordenadas ID {id_}: ({x1}, {y1}), ({x2}, {y2})"

        # Añade contador de personas detectadas
        cv2.putText(annotated, f"Personas detectadas: {len(ids_globales)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Añade texto de coordenadas
        if coordenadas_texto:
            alto = annotated.shape[0]
            cv2.putText(annotated, coordenadas_texto, (10, alto - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 255, 100), 2)

        return annotated, nueva_ultima_coords
    
    def _convertir_a_comando(self, x_centro, frame_width):
        # El punto central es 90. Ajustamos en función de la posición central de la persona
        if x_centro < frame_width // 2:
            # Persona hacia la izquierda, mover hacia la izquierda
            return int(90 - ((frame_width // 2 - x_centro) / (frame_width // 2) * 45))
        else:
            # Persona hacia la derecha, mover hacia la derecha
            return int(90 + ((x_centro - frame_width // 2) / (frame_width // 2) * 45))
    
    @staticmethod
    def convertir_a_angulo(x_centro, frame_width):
        return int((x_centro / frame_width) * 180)
