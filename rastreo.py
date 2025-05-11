from ultralytics import YOLO
import cv2
import serial  # Necesitarás instalar pySerial si no lo tienes: pip install pyserial
ser = serial.Serial('COM3', 115200, timeout=1)

def inicializar_modelo(ruta_modelo='yolov8n.pt'):
    return YOLO(ruta_modelo)

def abrir_video(ruta_video):
    cap = cv2.VideoCapture(ruta_video)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    out = cv2.VideoWriter('salida.avi', cv2.VideoWriter_fourcc(*'XVID'), fps, (frame_width, frame_height))
    return cap, out, frame_width, frame_height, fps

def detectar_personas(modelo, frame):
    resultados = modelo.track(frame, persist=True, conf=0.6, classes=[0])  # Solo clase 0: persona
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
    ser.write(f'{angulo}\n'.encode())
    print(f'Ángulo enviado: {angulo}')

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
                angulo = convertir_a_angulo(x_centro, frame_width)
                enviar_angulo_a_esp32(angulo)
                cv2.putText(annotated, f"Rastreando ID: {id_}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                coordenadas_texto = f"Coordenadas ID {id_}: ({x1}, {y1}), ({x2}, {y2})"

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