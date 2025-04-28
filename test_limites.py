import os
import cv2
import pytest
from rastreo import inicializar_modelo, detectar_personas, extraer_ids, actualizar_rastreo, dibujar_anotaciones


@pytest.fixture(scope="module")
def modelo():
    return inicializar_modelo()


@pytest.fixture(scope="module")
def video_capture():
    video_path = "Test2.mp4"
    if not os.path.exists(video_path):
        pytest.skip(f"El archivo {video_path} no existe.")
    cap = cv2.VideoCapture(video_path)
    yield cap
    cap.release()


def test_rastreo_en_frames_limitados(modelo, video_capture):
    """Testea el rastreo en un video donde se procesan pocos frames, hasta el límite máximo."""

    max_frames = 30  # Puedo cambiar esto para hacer más exhaustivo
    frame_count = 0
    primer_id = None
    rastreo_id = None
    ids_globales = set()
    ultima_coords = None
    frames_perdidos = 0

    while frame_count < max_frames:
        ret, frame = video_capture.read()
        if not ret:
            break

        result = detectar_personas(modelo, frame)
        assert result is not None, f"Resultado de detección vacío en frame {frame_count}"

        boxes = result.boxes
        ids_frame = extraer_ids(boxes)
        assert isinstance(ids_frame, set), f"extraer_ids debe retornar un set, pero obtuvo: {type(ids_frame)}"

        anterior_id = rastreo_id
        primer_id, rastreo_id, reiniciar, frames_perdidos = actualizar_rastreo(
            primer_id, rastreo_id, ids_frame, frames_perdidos, frames_espera=5
        )

        if anterior_id is not None and rastreo_id != anterior_id and frames_perdidos == 0:
            print(f"Cambio de ID rastreado en frame {frame_count}: de {anterior_id} a {rastreo_id}")

        annotated_frame, ultima_coords = dibujar_anotaciones(
            result.plot(), boxes, rastreo_id, ultima_coords, ids_globales
        )
        assert annotated_frame is not None, f"El frame anotado es None en el frame {frame_count}"
        assert isinstance(ultima_coords, (
        list, type(None))), f"ultima_coords debe ser lista o None, pero obtuvo: {type(ultima_coords)}"

        frame_count += 1

    assert frame_count == max_frames, f"Se esperaban {max_frames} frames, pero solo se procesaron {frame_count}."
    assert len(ids_globales) >= 3, f"Se esperaban al menos 3 IDs únicos, pero solo se detectaron {len(ids_globales)}."


def test_video_sin_personas(modelo):
    """Prueba un video vacío para asegurarse de que no haya errores al no encontrar personas."""

    video_path = "TestSinGente.mp4"  # Suponiendo que este video no tiene personas
    assert os.path.exists(video_path), "El archivo Test1_sin_personas.mp4 no existe."
    cap = cv2.VideoCapture(video_path)

    frame_count = 0
    primer_id = None
    rastreo_id = None
    ids_globales = set()
    ultima_coords = None
    frames_perdidos = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        result = detectar_personas(modelo, frame)
        assert result is not None, f"Resultado de detección vacío en frame {frame_count}"

        boxes = result.boxes
        ids_frame = extraer_ids(boxes)
        assert isinstance(ids_frame, set), f"extraer_ids debe retornar un set, pero obtuvo: {type(ids_frame)}"

        anterior_id = rastreo_id
        primer_id, rastreo_id, reiniciar, frames_perdidos = actualizar_rastreo(
            primer_id, rastreo_id, ids_frame, frames_perdidos, frames_espera=5
        )

        annotated_frame, ultima_coords = dibujar_anotaciones(
            result.plot(), boxes, rastreo_id, ultima_coords, ids_globales
        )
        assert annotated_frame is not None, f"El frame anotado es None en el frame {frame_count}"

        frame_count += 1

    cap.release()
    assert frame_count > 0, "No se pudieron procesar frames del video."
    assert len(ids_globales) == 0, f"No debe haber IDs detectados, pero se detectaron {len(ids_globales)}."


def test_video_extremo(modelo):
    """Prueba condiciones extremas como un video completamente blanco o muy borroso."""

    video_path = "TestBorroso.mp4"  # Suponiendo que este video es blanco o borroso
    assert os.path.exists(video_path), "El archivo Test2_blanco_o_borroso.mp4 no existe."
    cap = cv2.VideoCapture(video_path)

    frame_count = 0
    primer_id = None
    rastreo_id = None
    ids_globales = set()
    ultima_coords = None
    frames_perdidos = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        result = detectar_personas(modelo, frame)
        assert result is not None, f"Resultado de detección vacío en frame {frame_count}"

        boxes = result.boxes
        ids_frame = extraer_ids(boxes)
        assert isinstance(ids_frame, set), f"extraer_ids debe retornar un set, pero obtuvo: {type(ids_frame)}"

        anterior_id = rastreo_id
        primer_id, rastreo_id, reiniciar, frames_perdidos = actualizar_rastreo(
            primer_id, rastreo_id, ids_frame, frames_perdidos, frames_espera=5
        )

        annotated_frame, ultima_coords = dibujar_anotaciones(
            result.plot(), boxes, rastreo_id, ultima_coords, ids_globales
        )
        assert annotated_frame is not None, f"El frame anotado es None en el frame {frame_count}"

        frame_count += 1

    cap.release()
    assert frame_count > 0, "No se pudieron procesar frames del video."
    assert len(
        ids_globales) == 0, f"No debe haber IDs detectados en un video vacío o borroso, pero se detectaron {len(ids_globales)}."


def test_rastreo_id_no_presente():
    """Test cuando un ID rastreado ya no está presente en el video y debe ser reasignado."""

    ids_esta_frame = {2, 3}  # ID 1 ya no está presente
    primer_id = 1
    rastreo_id = 1
    frames_perdidos = 10  # Simulamos que el ID se pierde durante 10 frames

    primer_id, rastreo_id, reiniciar, frames_perdidos = actualizar_rastreo(
        primer_id, rastreo_id, ids_esta_frame, frames_perdidos, frames_espera=5
    )

    assert rastreo_id != 1, "El ID rastreado no debe seguir siendo el mismo después de perderlo por varios frames."


def test_rastreo_maximo_frames_perdidos():
    """Test cuando se pierden demasiados frames consecutivos y debe reiniciarse el rastreo."""

    ids_esta_frame = {1}
    primer_id = 1
    rastreo_id = 1
    frames_perdidos = 10  # Simulamos una pérdida continua

    primer_id, rastreo_id, reiniciar, frames_perdidos = actualizar_rastreo(
        primer_id, rastreo_id, ids_esta_frame, frames_perdidos, frames_espera=5
    )

    assert rastreo_id == 1, "El ID rastreado debería ser 1 después de no perder más frames."
    assert frames_perdidos == 0, "El contador de frames perdidos debería resetearse."

