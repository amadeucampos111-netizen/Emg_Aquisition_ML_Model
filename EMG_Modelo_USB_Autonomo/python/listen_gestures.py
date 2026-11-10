"""Mostra no PC as previsões locais emitidas pelo Arduino via HC-05."""
import argparse
import serial

p = argparse.ArgumentParser()
p.add_argument("--port", required=True)
p.add_argument("--baud", type=int, default=38400)
a = p.parse_args()
print("À escuta dos resultados do Arduino. Ctrl+C para sair.")
try:
    with serial.Serial(a.port, a.baud, timeout=1) as ser:
        while True:
            line = ser.readline().decode("ascii", errors="replace").strip()
            if line:
                print(line)
except KeyboardInterrupt:
    print("\nTerminado.")
