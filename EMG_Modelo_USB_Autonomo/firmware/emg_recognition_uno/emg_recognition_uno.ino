/*
  Reconhecimento autónomo de gestos - Arduino Uno R3 + 2 Grove EMG + HC-05.
  O modelo linear é exportado para model.h pelo script Python train_export.py.
  Grove 1 SIG -> A0; Grove 2 SIG -> A1.
  HC-05 TXD -> D10; HC-05 RXD <- D11 através de divisor de tensão.
  O Arduino calcula características e classifica localmente. O HC-05 apenas
  transmite o resultado (não é necessário PC para o reconhecimento).
*/
#include <SoftwareSerial.h>
#include <math.h>
#include <avr/pgmspace.h>
#include <string.h>
#include "model.h"

const byte EMG1_PIN = A0;
const byte EMG2_PIN = A1;
const byte BT_RX_PIN = 10;
const byte BT_TX_PIN = 11;
const uint16_t SAMPLE_HZ = 200;
const uint32_t PERIOD_US = 1000000UL / SAMPLE_HZ;
const uint16_t WINDOW_N = 100;       // 0,5 s a 200 Hz
const uint16_t HOP_N = 50;           // nova decisão a cada 0,25 s

SoftwareSerial bt(BT_RX_PIN, BT_TX_PIN);
uint16_t samples[WINDOW_N][2];
uint16_t filled = 0;
uint32_t nextSampleUs;
char cmdBuf[16];
byte cmdIdx = 0;

void checkSerialHandshake() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      cmdBuf[cmdIdx] = '\0';
      if (cmdIdx > 0 && strcmp(cmdBuf, "PING") == 0) {
        Serial.println(F("PONG_EMG_RECOGNIZER_READY"));
      }
      cmdIdx = 0;
    } else if (cmdIdx < sizeof(cmdBuf) - 1) {
      cmdBuf[cmdIdx++] = c;
    }
  }
}

void calculateChannelFeatures(byte channel, float *out) {
  float mean = 0.0f;
  for (uint16_t i = 0; i < WINDOW_N; i++) mean += samples[i][channel];
  mean /= WINDOW_N;

  float sumAbs = 0.0f, sumSq = 0.0f, waveLen = 0.0f;
  for (uint16_t i = 0; i < WINDOW_N; i++) {
    const float v = (float)samples[i][channel] - mean;
    sumAbs += fabs(v);
    sumSq += v * v;
    if (i > 0) waveLen += fabs((float)samples[i][channel] - (float)samples[i-1][channel]);
  }
  const float variance = sumSq / WINDOW_N;
  const float sd = sqrt(variance);
  const float zcThreshold = (sd * 0.01f > 2.0f) ? sd * 0.01f : 2.0f;
  uint16_t zeroCrossings = 0;
  for (uint16_t i = 1; i < WINDOW_N; i++) {
    const float a = (float)samples[i-1][channel] - mean;
    const float b = (float)samples[i][channel] - mean;
    if (((a > zcThreshold) && (b < -zcThreshold)) || ((a < -zcThreshold) && (b > zcThreshold))) zeroCrossings++;
  }
  out[0] = sumAbs / WINDOW_N; // MAV
  out[1] = sd;                // RMS após remoção da média
  out[2] = waveLen;           // waveform length
  out[3] = (float)zeroCrossings;
  out[4] = variance;
}

void classifyWindow() {
#if MODEL_VALID
  float features[MODEL_N_FEATURES];
  calculateChannelFeatures(0, &features[0]);
  calculateChannelFeatures(1, &features[5]);

  float bestScore = -1.0e20f;
  float secondScore = -1.0e20f;
  uint8_t bestClass = 0;
  for (uint8_t c = 0; c < MODEL_N_CLASSES; c++) {
    float score = pgm_read_float(&MODEL_BIAS[c]);
    for (uint8_t j = 0; j < MODEL_N_FEATURES; j++) {
      const float mean = pgm_read_float(&MODEL_MEAN[j]);
      const float scale = pgm_read_float(&MODEL_SCALE[j]);
      const float coef = pgm_read_float(&MODEL_COEF[c][j]);
      const float normalized = (features[j] - mean) / scale;
      score += coef * normalized;
    }
    if (score > bestScore) {
      secondScore = bestScore;
      bestScore = score;
      bestClass = c;
    } else if (score > secondScore) {
      secondScore = score;
    }
  }
  const float margin = bestScore - secondScore;
  char label[16];
  strcpy_P(label, MODEL_LABELS[bestClass]);
  const char *decision = (margin < MODEL_MIN_GAP) ? "incerto" : label;

  // A classificacao e executada no Arduino. USB e Bluetooth sao apenas saidas.
  bt.print(F("GESTO,")); bt.print(decision); bt.write(',');
  bt.println(margin, 3);

  Serial.print(F("GESTO,")); Serial.print(decision);
  Serial.write(','); Serial.println(margin, 3);
#else
  bt.println(F("ERRO,SEM_MODELO_TREINADO"));
#endif
}

void setup() {
  pinMode(EMG1_PIN, INPUT);
  pinMode(EMG2_PIN, INPUT);
  Serial.begin(115200);
  bt.begin(38400);
  delay(300);
  bt.println(F("#EMG_RECOGNIZER_READY"));
  Serial.println(F("#EMG_RECOGNIZER_READY"));
#if MODEL_VALID
  Serial.println(F("Modelo carregado. Reconhecimento local ativo."));
#else
  Serial.println(F("SEM MODELO: recolhe dados e executa train_export.py para gerar model.h."));
#endif
  nextSampleUs = micros();
}

void loop() {
  checkSerialHandshake();

  const uint32_t now = micros();
  if ((int32_t)(now - nextSampleUs) >= 0) {
    nextSampleUs += PERIOD_US;
    samples[filled][0] = analogRead(EMG1_PIN);
    samples[filled][1] = analogRead(EMG2_PIN);
    filled++;

    if (filled >= WINDOW_N) {
      classifyWindow();
      // Janela deslizante: mantém os últimos WINDOW_N-HOP_N pontos.
      for (uint16_t i = 0; i < WINDOW_N - HOP_N; i++) {
        samples[i][0] = samples[i + HOP_N][0];
        samples[i][1] = samples[i + HOP_N][1];
      }
      filled = WINDOW_N - HOP_N;
    }
    if ((int32_t)(micros() - nextSampleUs) > (int32_t)(4UL * PERIOD_US)) {
      nextSampleUs = micros() + PERIOD_US;
    }
  }
}
