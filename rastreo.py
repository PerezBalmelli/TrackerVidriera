from ultralytics import YOLO
import cv2
import serial  # Necesitarás instalar pySerial si no lo tienes: pip install pyserial
import time

# Variable global para el puerto serial
ser = None

def inicializar_serial(puerto='COM3', baudrate=115200, reintentos=1):
    """
    Inicializa la conexión serial con el dispositivo.
    
    Args:
        puerto (str): Puerto serial a utilizar.
        baudrate (int): Velocidad de comunicación.
        reintentos (int): Número de intentos de conexión.
        
    Returns:
        bool: True si la conexión fue exitosa, False en caso contrario.
    """
    global ser
    
    # Si ya existe una conexión, la devolvemos
    if ser is not None and ser.is_open:
        return True
        
    # Intentar establecer la conexión
    for intento in range(reintentos):
        try:
            ser = serial.Serial(puerto, baudrate, timeout=1)
            print(f"Conexión serial establecida en {puerto} a {baudrate} baudios")
            return True
        except serial.SerialException as e:
            print(f"Error al conectar al puerto {puerto}: {e}")
            if intento < reintentos - 1:
                print(f"Reintentando en 1 segundo ({intento+1}/{reintentos})...")
                time.sleep(1)
    
    # Si llegamos aquí, no pudimos establecer la conexión
    print(f"No se pudo establecer la conexión serial después de {reintentos} intentos")
    ser = None
    return False

def inicializar_modelo(ruta_modelo='yolov8n.pt'):
    return YOLO(ruta_modelo)

def abrir_video(ruta_video):
    cap = cv2.VideoCapture(ruta_video)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    out = cv2.VideoWriter('salida.avi', cv2.VideoWriter_fourcc(*'XVID'), fps, (frame_width, frame_height))
    return cap, out, frame_width, frame_height, fps

def detectar_personas(modelo, frame, confidence=0.6):
    resultados = modelo.track(frame, persist=True, conf=confidence, classes=[0])  # Solo clase 0: persona
    return resultados[0]

def extraer_ids(boxes):
    ids_esta_frame = set()
    ids = boxes.id
    if ids is not None:
        for id_tensor in ids:
            ids_esta_frame.add(int(id_tensor.item()))
    return ids_esta_frame

def actualizar_rastreo(primer_id, rastreo_id, ids_esta_frame, frames_perdidos, frames_espera=10):
    if primer_id is None and ids_esta_frame:
        primer_id = rastreo_id = next(iter(ids_esta_frame))
        print(f"Primera persona detectada: ID {primer_id}")
        frames_perdidos = 0
    elif rastreo_id is not None:
        if rastreo_id not in ids_esta_frame:
            frames_perdidos += 1
            if frames_perdidos >= frames_espera:
                print(f"ID {rastreo_id} ausente durante {frames_perdidos} frames. Buscando nuevo objetivo...")
                if ids_esta_frame:
                    nuevo_id = next(iter(ids_esta_frame))
                    print(f"Ahora rastreando a la nueva persona: ID {nuevo_id}")
                    rastreo_id = nuevo_id
                    frames_perdidos = 0
                    return primer_id, rastreo_id, True, frames_perdidos
        else:
            frames_perdidos = 0
    return primer_id, rastreo_id, False, frames_perdidos

def convertir_a_angulo(x_centro, frame_width):
    angulo = int((x_centro / frame_width) * 180)
    return angulo

def enviar_angulo_a_esp32(angulo, puerto='COM3', baudrate=115200):
    global ser
    
    try:
        if ser is None or not ser.is_open:
            # Intentar inicializar la conexión serial (un solo intento rápido)
            if not inicializar_serial(puerto, baudrate, reintentos=1):
                print(f"No se pudo enviar el ángulo {angulo} (sin conexión serial)")
                return False
        
        ser.write(f'{angulo}\n'.encode())
        print(f'Ángulo enviado: {angulo}')
        return True
    except Exception as e:
        print(f"Error al enviar ángulo: {e}")
        return False

def convertir_a_comando(x_centro, frame_width):
    """
    Convierte la posición del centro al comando adecuado para un servo de rotación continua.

    Parámetros:
        x_centro (int): Coordenada x del centro de la persona.
        frame_width (int): Ancho del frame de video.
    
    Retorna:
        comando (int): Comando PWM para el servo (aproximadamente 0-180).
    """
    # El punto central es 90. Ajustamos en función de la posición central de la persona
    if x_centro < frame_width // 2:
        # Persona hacia la izquierda, mover hacia la izquierda
        return int(90 - ((frame_width // 2 - x_centro) / (frame_width // 2) * 45))
    else:
        # Persona hacia la derecha, mover hacia la derecha
        return int(90 + ((x_centro - frame_width // 2) / (frame_width // 2) * 45))

def dibujar_anotaciones(frame, boxes, rastreo_id, ultima_coords, ids_globales, frame_width):
    annotated = frame.copy()
    coordenadas_texto = ""

    if boxes.id is not None and boxes.xyxy is not None:
        for i, id_tensor in enumerate(boxes.id):
            id_ = int(id_tensor.item())
            ids_globales.add(id_)
            if id_ == rastreo_id and i < len(boxes.xyxy):
                coords = boxes.xyxy[i].tolist()
                if coords != ultima_coords:
                    print(f"ID {id_} coordenadas: {coords}")
                    ultima_coords = coords
                x1, y1, x2, y2 = map(int, coords)
                x_centro = (x1 + x2) // 2
                comando = convertir_a_comando(x_centro, frame_width)  # Usamos la nueva función
                enviar_angulo_a_esp32(comando)
                cv2.putText(annotated, f"Rastreando ID: {id_}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                coordenadas_texto = f"Coordenadas ID {id_}: ({x1}, {y1}), ({x2}, {y2})"
    # else:
    #     #Es para parar CR
    #     print(f"Comando para servo: 90")
    #     enviar_angulo_a_esp32(90)


    cv2.putText(annotated, f"Personas detectadas: {len(ids_globales)}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

    if coordenadas_texto:
        alto = annotated.shape[0]
        cv2.putText(annotated, coordenadas_texto, (10, alto - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 255, 100), 2)

    return annotated, ultima_coords

def main():
    video_path = './test4.mp4'
    model = inicializar_modelo()
    cap, out, frame_width, _, _ = abrir_video(video_path)

    primer_id = None
    rastreo_id = None
    ids_globales = set()
    ultima_coords = None
    frames_perdidos = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        result = detectar_personas(model, frame)
        boxes = result.boxes
        ids_esta_frame = extraer_ids(boxes)

        primer_id, rastreo_id, reiniciar_coords, frames_perdidos = actualizar_rastreo(
            primer_id, rastreo_id, ids_esta_frame, frames_perdidos
        )
        if reiniciar_coords:
            ultima_coords = None

        annotated_frame, ultima_coords = dibujar_anotaciones(
            result.plot(), boxes, rastreo_id, ultima_coords, ids_globales, frame_width
        )

        cv2.imshow("Seguimiento", annotated_frame)
        out.write(annotated_frame)

        if cv2.waitKey(25) & 0xFF == ord('q'):
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()