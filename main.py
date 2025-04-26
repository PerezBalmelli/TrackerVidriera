from ultralytics import YOLO
import cv2

def inicializar_modelo(ruta_modelo='yolov8n.pt'):
    """
    Carga el modelo YOLOv8 especificado.

    Parámetros:
        ruta_modelo (str): Ruta al archivo del modelo .pt

    Retorna:
        YOLO: Modelo YOLO cargado.
    """
    return YOLO(ruta_modelo)

def abrir_video(ruta_video):
    """
    Abre un video desde la ruta indicada y prepara el objeto para escritura.

    Parámetros:
        ruta_video (str): Ruta del archivo de video a procesar.

    Retorna:
        cap (cv2.VideoCapture): Objeto para leer el video.
        out (cv2.VideoWriter): Objeto para guardar el video procesado.
        frame_width (int): Ancho del video.
        frame_height (int): Alto del video.
        fps (float): Cuadros por segundo del video.
    """
    cap = cv2.VideoCapture(ruta_video)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    out = cv2.VideoWriter('salida.avi', cv2.VideoWriter_fourcc(*'XVID'), fps, (frame_width, frame_height))
    return cap, out, frame_width, frame_height, fps

def detectar_personas(modelo, frame):
    """
    Realiza la detección y seguimiento de personas en un frame usando YOLOv8.

    Parámetros:
        modelo (YOLO): Modelo YOLO ya cargado.
        frame (ndarray): Frame de imagen a procesar.

    Retorna:
        results[0] (ultralytics.engine.results.Results): Resultados de la detección y tracking.
    """
    resultados = modelo.track(frame, persist=True, conf=0.6, classes=[0])  # Solo clase 0: persona
    return resultados[0]

def extraer_ids(boxes):
    """
    Extrae los IDs de los objetos detectados en el frame actual.

    Parámetros:
        boxes (Boxes): Contenedor de bounding boxes con IDs.

    Retorna:
        ids_esta_frame (set): Conjunto de IDs únicos en el frame actual.
    """
    ids_esta_frame = set()
    ids = boxes.id
    if ids is not None:
        for id_tensor in ids:
            ids_esta_frame.add(int(id_tensor.item()))
    return ids_esta_frame

def actualizar_rastreo(primer_id, rastreo_id, ids_esta_frame):
    """
    Gestiona la lógica de asignación o cambio de ID a rastrear.

    Parámetros:
        primer_id (int or None): Primer ID detectado.
        rastreo_id (int or None): ID actualmente rastreado.
        ids_esta_frame (set): IDs presentes en el frame actual.

    Retorna:
        primer_id (int): ID inicial (si ya fue detectado).
        rastreo_id (int): ID actualmente rastreado (puede cambiar).
        reiniciar_coords (bool): Indica si se deben reiniciar coordenadas.
    """
    if primer_id is None and ids_esta_frame:
        primer_id = rastreo_id = next(iter(ids_esta_frame))
        print(f"Primera persona detectada: ID {primer_id}")
    elif rastreo_id is not None and rastreo_id not in ids_esta_frame:
        print(f"ID {rastreo_id} ya no está en escena")
        if ids_esta_frame:
            nuevo_id = max(ids_esta_frame)
            print(f"Ahora rastreando a la última persona: ID {nuevo_id}")
            rastreo_id = nuevo_id
            return primer_id, rastreo_id, True
    return primer_id, rastreo_id, False

def dibujar_anotaciones(frame, boxes, rastreo_id, ultima_coords, ids_globales):
    """
    Dibuja anotaciones sobre el frame actual: cajas, texto e información de rastreo y coordenadas.

    Parámetros:
        frame (ndarray): Imagen original del frame.
        boxes (Boxes): Contenedor de cajas e IDs.
        rastreo_id (int): ID que se está rastreando actualmente.
        ultima_coords (list or None): Últimas coordenadas rastreadas para evitar repeticiones.
        ids_globales (set): Conjunto de IDs únicos vistos hasta ahora.

    Retorna:
        annotated (ndarray): Frame con anotaciones dibujadas.
        ultima_coords (list): Coordenadas actualizadas del ID rastreado.
    """
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
                cv2.putText(annotated, f"Rastreando ID: {id_}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                # Preparar texto con coordenadas para mostrarlo abajo
                coordenadas_texto = f"Coordenadas ID {id_}: ({x1}, {y1}), ({x2}, {y2})"

    # Mostrar número total de personas detectadas
    cv2.putText(annotated, f"Personas detectadas: {len(ids_globales)}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

    # Mostrar coordenadas en la parte inferior del video
    if coordenadas_texto:
        alto = annotated.shape[0]
        cv2.putText(annotated, coordenadas_texto, (10, alto - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 255, 100), 2)

    return annotated, ultima_coords

def main():
    """
    Función principal del programa.
    Carga el modelo, procesa el video cuadro por cuadro, rastrea a una persona
    y dibuja información en pantalla, guardando el resultado en un nuevo archivo.
    """
    video_path = './test4.mp4'
    model = inicializar_modelo()
    cap, out, _, _, _ = abrir_video(video_path)

    primer_id = None
    rastreo_id = None
    ids_globales = set()
    ultima_coords = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        result = detectar_personas(model, frame)
        boxes = result.boxes
        ids_esta_frame = extraer_ids(boxes)

        primer_id, rastreo_id, reiniciar_coords = actualizar_rastreo(primer_id, rastreo_id, ids_esta_frame)
        if reiniciar_coords:
            ultima_coords = None

        annotated_frame, ultima_coords = dibujar_anotaciones(result.plot(), boxes, rastreo_id, ultima_coords, ids_globales)

        cv2.imshow("Seguimiento", annotated_frame)
        out.write(annotated_frame)

        if cv2.waitKey(25) & 0xFF == ord('q'):
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
