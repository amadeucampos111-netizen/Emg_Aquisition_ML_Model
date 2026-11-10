/*
  Ponte USB <-> HC-05 para configurar a UART do HC-05.
  Coloca o HC-05 em modo AT (normalmente manter KEY/EN premido ao alimentar).
  Liga TXD do HC-05 a D10; RXD do HC-05 a D11 através de divisor de tensão.
  Abre o Monitor Série a 9600 baud e seleciona "Ambos NL e CR".
  Envia AT e depois AT+UART=38400,0,0. Confirma OK em cada resposta.
  Alguns clones usam comandos/modos diferentes; consulta a documentação do módulo.
*/
#include <SoftwareSerial.h>
SoftwareSerial hc05(10, 11); // RX, TX
void setup() {
  Serial.begin(9600);
  hc05.begin(38400); // velocidade AT típica
  Serial.println(F("Ponte HC-05 AT pronta. Envia AT; depois AT+UART=38400,0,0."));
}
void loop() {
  while (hc05.available()) Serial.write(hc05.read());
  while (Serial.available()) hc05.write(Serial.read());
}
