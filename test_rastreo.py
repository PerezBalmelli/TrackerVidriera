# test_rastreo.py

import pytest
import numpy as np
import cv2
from unittest.mock import MagicMock

from rastreo import (
    inicializar_modelo,
    abrir_video,
    detectar_personas,
    extraer_ids,
    actualizar_rastreo,
    dibujar_anotaciones
)

# ---- Test de inicializar_modelo ----
def test_inicializar_modelo():
    modelo = inicializar_modelo()
    assert modelo is not None

# ---- Test de abrir_video ----
def test_abrir_video(tmp_path):
    """Probar que abre correctamente un video falso."""
    # Crear un pequeño video de prueba
    ruta_video = str(tmp_path / "test.avi")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    out = cv2.VideoWriter(ruta_video, cv2.VideoWriter_fourcc(*'XVID'), 10, (100, 100))
    for _ in range(5):
        out.write(frame)
    out.release()

    cap, out_writer, width, height, fps = abrir_video(ruta_video)
    assert cap.isOpened()
    assert width == 100
    assert height == 100
    assert fps == 10
    cap.release()
    out_writer.release()

# ---- Test de extraer_ids ----
def test_extraer_ids_con_ids():
    boxes = MagicMock()
    boxes.id = [MagicMock(item=lambda: 1), MagicMock(item=lambda: 2)]
    ids = extraer_ids(boxes)
    assert ids == {1, 2}

def test_extraer_ids_sin_ids():
    boxes = MagicMock()
    boxes.id = None
    ids = extraer_ids(boxes)
    assert ids == set()

# ---- Tests de actualizar_rastreo ----
def test_actualizar_rastreo_primer_id_none():
    """Debe asignar el primer ID si no hay aún uno asignado."""
    primer_id, rastreo_id, reiniciar, frames_perdidos = actualizar_rastreo(None, None, {5}, 0)
    assert primer_id == 5
    assert rastreo_id == 5
    assert reiniciar is False
    assert frames_perdidos == 0

def test_actualizar_rastreo_id_no_en_frame():
    """Debe reasignar el rastreo_id si ya no está presente después de esperar frames suficientes."""
    primer_id = 1
    rastreo_id = 1
    frames_perdidos = 9  # Simular que ya lleva 9 frames
    ids_esta_frame = {2, 3}

    primer_id, rastreo_id, reiniciar, frames_perdidos = actualizar_rastreo(primer_id, rastreo_id, ids_esta_frame, frames_perdidos, frames_espera=10)

    assert rastreo_id == 3
    assert reiniciar is True
    assert frames_perdidos == 0

def test_actualizar_rastreo_id_presente():
    """No debe cambiar nada si el ID sigue presente."""
    primer_id, rastreo_id, reiniciar, frames_perdidos = actualizar_rastreo(1, 1, {1, 2, 3}, 0)
    assert primer_id == 1
    assert rastreo_id == 1
    assert reiniciar is False
    assert frames_perdidos == 0

# ---- Test de dibujar_anotaciones ----
def test_dibujar_anotaciones():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    boxes = MagicMock()
    boxes.id = [MagicMock(item=lambda: 7)]
    boxes.xyxy = [np.array([100, 100, 200, 200])]

    rastreo_id = 7
    ultima_coords = None
    ids_globales = set()

    annotated_frame, nueva_coords = dibujar_anotaciones(frame, boxes, rastreo_id, ultima_coords, ids_globales)

    assert isinstance(annotated_frame, np.ndarray)
    assert nueva_coords == [100, 100, 200, 200]
    assert 7 in ids_globales

# ---- Test de detectar_personas ----
def test_detectar_personas():
    """Probar detectar_personas simulando resultados."""
    modelo_mock = MagicMock()
    resultado_mock = MagicMock()
    modelo_mock.track.return_value = [resultado_mock]

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    resultados = detectar_personas(modelo_mock, frame)

    assert resultados == resultado_mock
