// #include <Arduino.h>
// #include <ESP32Servo.h>

// Servo miServo;
// const int PIN_SERVO = 18;

// void setup() {
//   Serial.begin(115200);
//   miServo.setPeriodHertz(50);
//   miServo.attach(PIN_SERVO, 544, 2400);
  
//   // Detener al inicio
//   miServo.write(90);  // Posición neutral = detener
//   delay(2000);
// }

// void loop() {
//   // Girar en una dirección
//   Serial.println("Girando lento en sentido horario");
//   miServo.write(70);  // Velocidad baja
//   delay(4000);
  
//   // Detener
//   Serial.println("Deteniendo");
//   miServo.write(90);  // Stop
//   delay(2000);
  
//   // Girar en la otra dirección
//   Serial.println("Girando lento en sentido antihorario");
//   miServo.write(110);  // Velocidad baja en dirección opuesta
//   delay(4000);
  
//   // Detener de nuevo
//   Serial.println("Deteniendo");
//   miServo.write(90);  // Stop
//   delay(2000);
// }