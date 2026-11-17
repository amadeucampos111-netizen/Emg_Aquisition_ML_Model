# Resumo de ligações

## Durante a aquisição e treino por USB

- Grove EMG 1 SIG -> A0
- Grove EMG 2 SIG -> A2
- VCC e GND -> alimentação especificada para a revisão dos sensores; GND comum com o Uno.
- Arduino Uno -> PC por USB. Firmware de aquisição: `firmware/emg_stream_hc05/emg_stream_hc05.ino`.
- Monitor Série / Python: 115200 baud.
- O HC-05 não é necessário nesta fase.

## Durante a classificação autónoma

- Mantêm-se os sensores em A0 e A2.
- Carrega `firmware/emg_recognition_uno/emg_recognition_uno.ino` depois de gerar `model.h`.
- Alimenta o Uno por power bank/fonte adequada; o PC pode estar desligado.
- HC-05 opcional: TXD -> D10; RXD <- D11 através de divisor de tensão; GND comum; VCC conforme o breakout. Serve apenas para transmitir o rótulo previsto.

## Alimentação da mão biónica

- Os servos devem usar fonte separada dimensionada para a corrente dos motores.
- Liga o GND da fonte dos servos ao GND do Uno.
- Nunca alimentes os servos pelo pino 5 V do Uno.
