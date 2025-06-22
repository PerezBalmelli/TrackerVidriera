# HumanTracker - Sistema de Seguimiento de Personas

Software de visión por computadora que detecta y sigue personas en tiempo real a través de una fuente de video, con una interfaz gráfica para su control y configuración.

## Características Principales

- Detección y seguimiento de personas en tiempo real.
- Interfaz gráfica intuitiva construida con PyQt.
- Configuración de modelo de IA (YOLOv8n, YOLOv8s).
- Soporte para múltiples fuentes de video (cámara en vivo, archivos de video).
- Comunicación serial para interactuar con hardware externo (ej. servomotores).
- Exportación de video con el seguimiento visualizado.

## Instalación (Usuario Final)

1. Ve a la sección de **Releases** en la página de GitHub del proyecto.
2. Descarga el archivo `HumanTracker_vX.X.zip` más reciente.
3. Descomprime el archivo en una carpeta de tu elección.
4. Ejecuta `HumanTracker.exe`.

## Instalación (Desarrolladores)

Para configurar el entorno de desarrollo, sigue estos pasos:

1. **Clona el repositorio:**
   ```powershell
   git clone https://github.com/PerezBalmelli/TrackerVidriera.git
   cd TrackerVidriera
   ```

2. **Crea y activa un entorno virtual:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Instala las dependencias:**
   ```powershell
   pip install -r requirements.txt
   ```

## Uso Básico

1. Ejecuta el script principal desde la raíz del proyecto:
   ```powershell
   python test_ui_refactored.py
   ```
2. Usa la interfaz para seleccionar una fuente de video (cámara o archivo).
3. Haz clic en "Iniciar" para comenzar el seguimiento.

## Licencia

Este proyecto está bajo la Licencia MIT.
