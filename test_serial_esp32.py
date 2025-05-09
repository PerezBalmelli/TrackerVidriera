"""
Script simple para probar la comunicación serial con ESP32
"""
import serial
import json
import time
import sys
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Prueba de comunicación serial con ESP32")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=1.0)
    return parser.parse_args()

def main():
    args = parse_args()
    print(f"Intentando conectar a ESP32 en {args.port} a {args.baud} baudios...")
    
    try:
        # Abrir conexión serial
        ser = serial.Serial(args.port, args.baud, timeout=args.timeout)
        print(f"✅ Conectado exitosamente a {args.port}")
        
        # Esperar que el ESP32 se reinicie después de la conexión
        time.sleep(2)
        print("Listo para enviar comandos. Presiona Ctrl+C para salir.")
        print("Comandos disponibles:")
        print("  pan,tilt   - Envía valores específicos de pan y tilt (ej: 90,45)")
        print("  test       - Ejecuta una secuencia de prueba")
        print("  stress     - Ejecuta una prueba de estrés")
        print("  q          - Salir")
        
        # Bucle principal
        while True:
            try:
                cmd = input("\n> ").strip()
                
                if not cmd:
                    continue
                
                if cmd.lower() == 'q':
                    break
                
                if cmd.lower() == 'stress':
                    print("Ejecutando prueba de estrés...")
                    # Número de comandos, intervalo y rango de posiciones para la prueba
                    num_commands = input("Número de comandos (default: 100): ").strip()
                    num_commands = int(num_commands) if num_commands.isdigit() else 100
                    
                    interval = input("Intervalo entre comandos en segundos (default: 0.05): ").strip()
                    interval = float(interval) if interval and interval.replace('.', '').isdigit() else 0.05
                    
                    print(f"Enviando {num_commands} comandos con intervalo de {interval}s...")
                    
                    import random
                    start_time = time.time()
                    for i in range(num_commands):
                        # Generar valores aleatorios para pan y tilt
                        pan = random.randint(0, 180)
                        tilt = random.randint(0, 90)
                        message = {'pan': pan, 'tilt': tilt}
                        json_cmd = json.dumps(message) + '\n'
                        ser.write(json_cmd.encode())
                        print(f"Enviado {i+1}/{num_commands}: {json_cmd.strip()}", end='\r')
                        time.sleep(interval)
                    
                    elapsed_time = time.time() - start_time
                    rate = num_commands / elapsed_time if elapsed_time > 0 else 0
                    print(f"\nPrueba completada: {num_commands} comandos en {elapsed_time:.2f} segundos ({rate:.2f} comandos/seg)")
                    continue
                
                if cmd.lower() == 'test':
                    print("Ejecutando secuencia de prueba...")
                    test_values = [
                        (0, 0),
                        (90, 45),
                        (180, 90),
                        (90, 45),
                        (0, 0),
                        (99, 99)
                    ]
                    
                    for pan, tilt in test_values:
                        message = {'pan': pan, 'tilt': tilt}
                        json_cmd = json.dumps(message) + '\n'
                        ser.write(json_cmd.encode())
                        print(f"Enviado: {json_cmd.strip()}")
                        time.sleep(1)  # Esperar entre comandos
                    
                    print("Secuencia de prueba completada.")
                    continue
                
                # Verificar si es un comando pan,tilt
                if ',' in cmd:
                    try:
                        pan, tilt = map(int, cmd.split(','))
                        message = {'pan': pan, 'tilt': tilt}
                        json_cmd = json.dumps(message) + '\n'
                        ser.write(json_cmd.encode())
                        print(f"Enviado: {json_cmd.strip()}")
                    except ValueError:
                        print("❌ Error: Formato incorrecto. Usa 'pan,tilt' como números enteros.")
                else:
                    print("❌ Comando desconocido")
            
            except KeyboardInterrupt:
                break
        
        print("\nCerrando conexión...")
        ser.close()
        print("Conexión cerrada. ¡Adiós!")
        
    except serial.SerialException as e:
        print(f"❌ Error al conectar: {e}")
        if "PermissionError" in str(e) or "Access is denied" in str(e):
            print("\nEl puerto COM3 ya está en uso por otra aplicación.")
            print("Por favor cierra el Monitor Serial de PlatformIO u otros programas usando el puerto.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())