# Firmware ESP32 para HumanTracker

Este directorio contiene el firmware para el microcontrolador ESP32, encargado de la comunicación serial y el control de servomotores en el sistema HumanTracker.

## Requisitos

- [PlatformIO](https://platformio.org/) instalado (recomendado como extensión de VS Code)
- Placa ESP32 compatible

## Estructura del directorio

- `src/` : Código fuente principal del firmware
- `include/` : Archivos de cabecera. Tener en cuenta env para configuración de WiFi en fase de pruebas.
- `lib/` : Librerías adicionales
- `platformio.ini` : Configuración del proyecto PlatformIO

## Instalación y carga del firmware

Puedes compilar y cargar el firmware de dos maneras:

### Opción 1: Usando la extensión PlatformIO en VS Code (recomendado)

1. Abre este directorio (`Comunicacion-Serial/`) con VS Code.
2. Conecta tu ESP32 por USB.
3. Usa los botones de la barra inferior de PlatformIO para:
   - Compilar ("Build")
   - Subir el firmware ("Upload")
   - Abrir el monitor serial ("Monitor")

### Opción 2: Usando la terminal (requiere PlatformIO en el PATH)

1. Abre una terminal en este directorio.
2. Compila el firmware:
   ```sh
   platformio run
   ```
3. Sube el firmware al ESP32:
   ```sh
   platformio run --target upload
   ```
4. (Opcional) Abre el monitor serial:
   ```sh
   platformio device monitor
   ```

> Nota: Si el comando `platformio` no funciona, asegúrate de que PlatformIO esté instalado globalmente y agregado al PATH del sistema, o usa la extensión de VS Code.

## Configuración

- Edita `platformio.ini` para cambiar la placa objetivo o parámetros de compilación.
- Modifica los archivos en `src/` para ajustar la lógica de control o la comunicación serial.

## Configuración del puerto COM y parámetros

Para cargar el firmware y comunicarte con el ESP32, debes seleccionar el puerto COM correcto:

- En VS Code, la extensión PlatformIO detecta automáticamente los puertos disponibles. Puedes elegir el puerto desde la barra inferior ("PlatformIO: Select Serial Port") antes de subir el firmware o abrir el monitor.
- También puedes fijar el puerto por defecto editando el archivo `platformio.ini`:
  ```ini
  upload_port = COM3
  monitor_port = COM3
  ```

**Baudrate recomendado:** 115200 (puedes cambiarlo en `platformio.ini` con `monitor_speed = 115200`).

## Buenas prácticas para desarrollo

- Mantén el código modular: utiliza la carpeta `src/` para la lógica principal y `lib/` para librerías reutilizables.
- Documenta las funciones y módulos con comentarios claros.
- Antes de hacer cambios importantes, crea una rama nueva en git.
- Realiza pruebas en hardware real tras cada cambio relevante.
- Si agregas nuevas dependencias, decláralas en `platformio.ini` o en la carpeta `lib/`.
- Sigue la convención de nombres y estilo del proyecto.

## Integración con HumanTracker

El firmware está diseñado para recibir comandos seriales desde la aplicación Python de HumanTracker y controlar hardware externo en respuesta (mover servomotores para seguimiento físico).

Consulta el README principal del proyecto para detalles sobre la comunicación y el protocolo de comandos.

## Licencia

Este firmware forma parte del proyecto HumanTracker y está bajo la Licencia MIT.
