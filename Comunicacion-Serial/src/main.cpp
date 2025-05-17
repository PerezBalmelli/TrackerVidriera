/*
 * ESP32 Pan/Tilt Receptor JSON con Servidor Web
 * 
 * Este sketch recibe comandos JSON a traves de la comunicacion serial
 * y muestra los valores recibidos de pan y tilt.
 * Tambien implementa un servidor web sencillo para visualizar los valores.
 * 
 * Formato JSON esperado: {"pan": valor_entero, "tilt": valor_entero}
 */
// Configuracion WiFi

#include <Arduino.h>
#include <ArduinoJson.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include "../include/env.cpp"

// Definiciones para servo si se conecta
// #define SERVO_PAN_PIN 18

// Valores actuales de pan y tilt
int currentPan = 90;  // Posicion inicial
int currentTilt = 90; // Posicion inicial

Servo myServo;  // Crear un objeto servo
int angulo = 90; // Angulo inicial, 90 es el centro
const int servoPin = 18; // Pines del ESP32 para conectar el servo, asegúrate de conectar al pin correcto

// Variables para estadisticas y pruebas de rendimiento
unsigned long totalMessages = 0;         // Total de mensajes recibidos
unsigned long stressTestMessages = 0;    // Mensajes recibidos durante prueba de estres
unsigned long lastMessageTime = 0;       // Timestamp del ultimo mensaje recibido
unsigned long stressTestStartTime = 0;   // Tiempo de inicio de la prueba de estres
unsigned long minInterval = ULONG_MAX;   // Intervalo minimo entre mensajes (µs)
unsigned long maxInterval = 0;           // Intervalo maximo entre mensajes (µs)
unsigned long totalInterval = 0;         // Suma total de intervalos para calcular promedio (µs)
bool stressTestActive = false;           // Bandera para indicar si hay una prueba activa
unsigned long lastErrorCount = 0;        // Contador de errores de parsing

// Historial de los ultimos 100 intervalos para analisis
#define INTERVAL_HISTORY_SIZE 100
unsigned long intervalHistory[INTERVAL_HISTORY_SIZE];
int intervalHistoryIndex = 0;

// Crear el servidor web en el puerto 80
WebServer server(80);

// Declaracion anticipada de funciones
void handleRoot();
void handleData();
void handleStats();
void handleResetStats();
void handleNotFound();
//void moveServos(int pan, int tilt);

// Funcion para manejar la pagina raiz
void handleRoot() {
  String html = "<!DOCTYPE html><html>";
  html += "<head><meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>ESP32 Pan/Tilt Control</title>";
  html += "<style>";
  html += "body { font-family: Arial, sans-serif; text-align: center; margin: 20px; }";
  html += "h1 { color: #0066cc; }";
  html += ".data { font-size: 24px; margin: 20px; }";
  html += ".nav { margin: 20px 0; }";
  html += "a.button { background-color: #4CAF50; color: white; padding: 10px 20px; ";
  html += "border: none; border-radius: 4px; cursor: pointer; margin: 5px; text-decoration: none; display: inline-block; }";
  html += "a.button:hover { background-color: #45a049; }";
  html += "a.button.stats { background-color: #2196F3; }";
  html += "</style>";
  html += "<script>";
  html += "function actualizarDatos() {";
  html += "  fetch('/datos').then(response => response.json())";
  html += "  .then(data => {";
  html += "    document.getElementById('panValue').textContent = data.pan;";
  html += "    document.getElementById('tiltValue').textContent = data.tilt;";
  html += "  });";
  html += "}";
  html += "setInterval(actualizarDatos, 1000);"; // Actualizar cada segundo
  html += "</script>";
  html += "</head><body>";
  html += "<h1>ESP32 Pan/Tilt Monitor</h1>";
  html += "<div class='data'>Pan: <span id='panValue'>" + String(currentPan) + "</span></div>";
  html += "<div class='data'>Tilt: <span id='tiltValue'>" + String(currentTilt) + "</span></div>";
  html += "<div class='nav'>";
  html += "<a href='/stats' class='button stats'>Ver Estadisticas de Rendimiento</a>";
  html += "</div>";
  html += "<p>Total de mensajes recibidos: " + String(totalMessages) + "</p>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

// Funcion para proporcionar datos en formato JSON
void handleData() {
  String jsonResponse = "{\"pan\":" + String(currentPan) + ",\"tilt\":" + String(currentTilt) + "}";
  server.send(200, "application/json", jsonResponse);
}

// Funcion para manejar rutas no encontradas
void handleNotFound() {
  server.send(404, "text/plain", "Pagina no encontrada");
}

/*
void moveServos(int pan, int tilt) {
  // Limitar los valores a un rango seguro (0-180 para servos estandar)
  pan = constrain(pan, 0, 180);
  tilt = constrain(tilt, 0, 180);
  
  
  Serial.println("Moviendo servos...");
}
*/

// Funcion para manejar la pagina de estadisticas
void handleStats() {
  String html = "<!DOCTYPE html><html>";
  html += "<head><meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<meta http-equiv='refresh' content='1'>"; // Auto-refresh cada segundo
  html += "<title>ESP32 Performance Stats</title>";
  html += "<style>";
  html += "body { font-family: Arial, sans-serif; margin: 20px; }";
  html += "h1 { color: #0066cc; }";
  html += "table { border-collapse: collapse; width: 100%; margin-top: 20px; }";
  html += "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }";
  html += "th { background-color: #f2f2f2; }";
  html += "tr:nth-child(even) { background-color: #f9f9f9; }";
  html += ".button { background-color: #f44336; color: white; padding: 10px 15px; ";
  html += "border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; margin-top: 20px; }";
  html += ".button-home { background-color: #4CAF50; }";
  html += "</style>";
  html += "</head><body>";
  html += "<h1>Estadisticas de Rendimiento</h1>";
  
  // Tabla principal de estadisticas
  html += "<table>";
  html += "<tr><th>Metrica</th><th>Valor</th></tr>";
  html += "<tr><td>Total de mensajes procesados</td><td>" + String(totalMessages) + "</td></tr>";
  
  // Estadisticas de la prueba de estres
  if (stressTestActive) {
    html += "<tr><td colspan='2'><strong>Prueba de estres en curso</strong></td></tr>";
    unsigned long elapsedTime = (millis() - stressTestStartTime);
    float messagesPerSecond = (stressTestMessages * 1000.0) / elapsedTime;
    
    html += "<tr><td>Tiempo transcurrido</td><td>" + String(elapsedTime / 1000.0, 2) + " segundos</td></tr>";
    html += "<tr><td>Mensajes durante prueba</td><td>" + String(stressTestMessages) + "</td></tr>";
    html += "<tr><td>Velocidad</td><td>" + String(messagesPerSecond, 2) + " mensajes/segundo</td></tr>";
  } 
  else if (stressTestMessages > 0) {
    html += "<tr><td colspan='2'><strong>Resultados de la ultima prueba de estres</strong></td></tr>";
    unsigned long testDuration = lastMessageTime - stressTestStartTime;
    float messagesPerSecond = (stressTestMessages * 1000.0) / testDuration;
    
    html += "<tr><td>Duracion de la prueba</td><td>" + String(testDuration / 1000.0, 2) + " segundos</td></tr>";
    html += "<tr><td>Mensajes procesados</td><td>" + String(stressTestMessages) + "</td></tr>";
    html += "<tr><td>Velocidad promedio</td><td>" + String(messagesPerSecond, 2) + " mensajes/segundo</td></tr>";
  }
  
  // Estadisticas de intervalos
  if (totalMessages > 1) {
    float avgInterval = totalInterval / (float)(totalMessages - 1);
    html += "<tr><td colspan='2'><strong>Estadisticas de intervalos</strong></td></tr>";
    html += "<tr><td>Intervalo minimo</td><td>" + String(minInterval / 1000.0, 3) + " ms</td></tr>";
    html += "<tr><td>Intervalo maximo</td><td>" + String(maxInterval / 1000.0, 3) + " ms</td></tr>";
    html += "<tr><td>Intervalo promedio</td><td>" + String(avgInterval / 1000.0, 3) + " ms</td></tr>";
  }
  
  // Informacion de errores
  html += "<tr><td>Errores de parsing JSON</td><td>" + String(lastErrorCount) + "</td></tr>";
  html += "</table>";
  
  // Tabla de historial de intervalos recientes
  if (totalMessages > 1) {
    html += "<h2>Historial de intervalos recientes (ms)</h2>";
    html += "<div style='overflow-x: auto;'><table style='width: auto;'><tr>";
    
    int displayCount = min((int)totalMessages - 1, INTERVAL_HISTORY_SIZE);
    int startIdx = (intervalHistoryIndex - displayCount + INTERVAL_HISTORY_SIZE) % INTERVAL_HISTORY_SIZE;
    
    for (int i = 0; i < displayCount; i++) {
      int idx = (startIdx + i) % INTERVAL_HISTORY_SIZE;
      html += "<td>" + String(intervalHistory[idx] / 1000.0, 1) + "</td>";
    }
    
    html += "</tr></table></div>";
  }
  
  // Botones de accion
  html += "<div>";
  html += "<a href='/' class='button button-home'>Pagina Principal</a> ";
  html += "<a href='/resetstats' class='button'>Reiniciar Estadisticas</a>";
  html += "</div>";
  
  html += "</body></html>";
  server.send(200, "text/html", html);
}

// Funcion para reiniciar estadisticas
void handleResetStats() {
  // Reiniciar contadores y estadisticas
  totalMessages = 0;
  stressTestMessages = 0;
  stressTestStartTime = 0;
  stressTestActive = false;
  lastMessageTime = 0;
  minInterval = ULONG_MAX;
  maxInterval = 0;
  totalInterval = 0;
  lastErrorCount = 0;
  
  // Limpiar historial
  for (int i = 0; i < INTERVAL_HISTORY_SIZE; i++) {
    intervalHistory[i] = 0;
  }
  intervalHistoryIndex = 0;
  
  // Redirigir a la pagina de estadisticas
  server.sendHeader("Location", "/stats", true);
  server.send(302, "text/plain", "");
}

void setup() {
  // Inicializar comunicacion serial
  Serial.begin(115200);
  
  // Tiempo para establecer la conexion serial
  delay(1000);
  
  Serial.println("ESP32 Pan/Tilt JSON Receiver con Servidor Web");
  
  // Inicializar pines para servos (si se conectan)
  // pinMode(SERVO_PAN_PIN, OUTPUT);
  // pinMode(SERVO_TILT_PIN, OUTPUT);
  
  Serial.println("Escaneando redes WiFi disponibles...");
  int numRedes = WiFi.scanNetworks();

  if (numRedes == 0) {
    Serial.println("No se encontraron redes.");
  } else {
    Serial.println("Redes WiFi encontradas:");
    for (int i = 0; i < numRedes; ++i) {
      Serial.print(i + 1);
      Serial.print(": ");
      Serial.print(WiFi.SSID(i));
      Serial.print(" (RSSI: ");
      Serial.print(WiFi.RSSI(i));
      Serial.println(" dBm)");
    }
  }

  // Conectar a WiFi
  WiFi.begin(ssid, password);
  Serial.print("Conectando a WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Conectado a WiFi, IP: ");
  Serial.println(WiFi.localIP());
  
  // Configurar rutas del servidor web
  server.on("/", handleRoot);
  server.on("/datos", handleData);
  server.on("/stats", handleStats);
  server.on("/resetstats", handleResetStats);
  server.onNotFound(handleNotFound);
  
  // Iniciar servidor web
  server.begin();
  Serial.println("Servidor HTTP iniciado");
  Serial.println("Para ver la pagina web, abre en tu navegador: http://" + WiFi.localIP().toString());
  Serial.println("Esperando comandos JSON por Serial... (ej: {\"pan\": 90, \"tilt\": 45})");

  // Inicializar servo
  myServo.setPeriodHertz(50);
  myServo.attach(servoPin, 544, 2400);
}

void loop() {
  // Manejar clientes web
  server.handleClient();
  
  // Si hay datos disponibles en el puerto serial
  if (Serial.available() > 0) {
    // Leer la cadena de caracteres recibida
    String angleString = Serial.readStringUntil('\n');
    // Convertir la cadena a un entero
    angulo = angleString.toInt();

    Serial.print("Recibido: ");
    Serial.print(angleString);

    // Verifica que el ángulo sea válido antes de mover el servo
    if (angulo >= 0 && angulo <= 180) {
      myServo.write(angulo);
      
      currentPan = angulo;

      Serial.print("Ángulo movido a: ");
      Serial.println(angulo);
      // Actualizar estadisticas basicas
      totalMessages++;
    } else {
      Serial.println("Ángulo inválido recibido");
    }
  }
  
  delay(10);
}
