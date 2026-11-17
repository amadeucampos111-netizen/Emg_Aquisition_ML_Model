/*
  AQUISICAO sEMG — Arduino Uno R3 + 2 canais Grove EMG
  Sensor 1 SIG -> A0; Sensor 2 SIG -> A2; VCC/GND conforme o fabricante.
  Envia por USB: sequencia,adc1,adc2\n
  Responde a comandos "PING" com "PONG_EMG_READY" para handshake seguro com Python.
  Taxa de amostragem: 200 amostras/s por par de canais.
  Monitor Serie / Python: 115200 baud.

  Este firmware serve APENAS para recolher dados rotulados no PC.
  Depois do treino, carregar emg_recognition_uno.ino para classificar
  autonomamente, sem PC.
*/
const byte EMG1_PIN = A0;
const byte EMG2_PIN = A2;
const uint16_t SAMPLE_HZ = 200;
const uint32_t PERIOD_US = 1000000UL / SAMPLE_HZ;

uint32_t nextSampleUs = 0;
uint16_t sampleNumber = 0;
char cmdBuf[16];
byte cmdIdx = 0;

void checkSerialHandshake() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      cmdBuf[cmdIdx] = '\0';
      if (cmdIdx > 0 && strcmp(cmdBuf, "PING") == 0) {
        Serial.println(F("PONG_EMG_READY"));
      }
      cmdIdx = 0;
    } else if (cmdIdx < sizeof(cmdBuf) - 1) {
      cmdBuf[cmdIdx++] = c;
    }
  }
}

void setup() {
  pinMode(EMG1_PIN, INPUT);
  pinMode(EMG2_PIN, INPUT);
  Serial.begin(115200);
  delay(300);
  Serial.println(F("#EMG_USB_READY,200"));
  nextSampleUs = micros();
}

void loop() {
  checkSerialHandshake();

  uint32_t now = micros();
  if ((int32_t)(now - nextSampleUs) >= 0) {
    nextSampleUs += PERIOD_US;

    uint16_t ch1 = analogRead(EMG1_PIN);
    uint16_t ch2 = analogRead(EMG2_PIN);

    Serial.print(sampleNumber++);
    Serial.write(',');
    Serial.print(ch1);
    Serial.write(',');
    Serial.println(ch2);

    // Recupera a temporizacao se uma operacao atrasar o ciclo.
    if ((int32_t)(micros() - nextSampleUs) > (int32_t)(4UL * PERIOD_US)) {
      nextSampleUs = micros() + PERIOD_US;
    }
  }
}
