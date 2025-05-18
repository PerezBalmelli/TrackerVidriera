"""
Módulo para el rastreo de objetos a través del tiempo.
"""


class ObjectTracker:
    """
    Clase responsable del rastreo de objetos/personas a través de múltiples frames.
    Mantiene el estado de los IDs rastreados y gestiona el cambio de objetivo.
    """
    
    def __init__(self, frames_espera=10):
        self.frames_espera = frames_espera
        self.primer_id = None
        self.rastreo_id = None
        self.frames_perdidos = 0
        self.ultima_coords = None
        self.ids_globales = set()  # Todos los IDs vistos
        
    def actualizar(self, ids_esta_frame):
        """Actualiza el estado de rastreo basado en los IDs detectados en el frame actual."""
        # Añadir todos los IDs detectados a los globales
        self.ids_globales.update(ids_esta_frame)
        
        # Si es la primera detección
        if self.primer_id is None and ids_esta_frame:
            self.primer_id = self.rastreo_id = next(iter(ids_esta_frame))
            print(f"Primera persona detectada: ID {self.primer_id}")
            self.frames_perdidos = 0
            return self.primer_id, self.rastreo_id, False, self.frames_perdidos
        
        # Si ya hay un ID de rastreo
        elif self.rastreo_id is not None:
            # Verificar si el ID ya no está presente
            if self.rastreo_id not in ids_esta_frame:
                self.frames_perdidos += 1
                # Si se superó el umbral de frames perdidos
                if self.frames_perdidos >= self.frames_espera:
                    print(f"ID {self.rastreo_id} ausente durante {self.frames_perdidos} frames. "
                          f"Buscando nuevo objetivo...")
                    # Si hay otros objetivos, cambiar al primero disponible
                    if ids_esta_frame:
                        nuevo_id = next(iter(ids_esta_frame))
                        print(f"Ahora rastreando a la nueva persona: ID {nuevo_id}")
                        self.rastreo_id = nuevo_id
                        self.frames_perdidos = 0
                        # Indicar que se cambió el objetivo (reiniciar coordenadas)
                        return self.primer_id, self.rastreo_id, True, self.frames_perdidos
            else:
                # El ID sigue presente, reiniciar contador
                self.frames_perdidos = 0
        
        return self.primer_id, self.rastreo_id, False, self.frames_perdidos
    
    def set_frames_espera(self, frames):
        self.frames_espera = max(1, frames)  # Mínimo 1 frame
    
    def reset(self):
        self.primer_id = None
        self.rastreo_id = None
        self.frames_perdidos = 0
        self.ultima_coords = None
        self.ids_globales.clear()
        
    def get_tracked_id(self):
        return self.rastreo_id
    
    def get_all_ids(self):
        return self.ids_globales.copy()
