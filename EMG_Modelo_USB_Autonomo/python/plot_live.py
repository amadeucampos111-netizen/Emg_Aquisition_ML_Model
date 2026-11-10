"""Gráfico em tempo real dos dois canais EMG recebidos por USB."""
import argparse
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import serial
from emg_common import parse_sample, SAMPLE_RATE

p = argparse.ArgumentParser()
p.add_argument("--port", required=True)
p.add_argument("--baud", type=int, default=115200)
p.add_argument("--seconds", type=int, default=5)
a = p.parse_args()
ser = serial.Serial(a.port, a.baud, timeout=0.01)
n = max(100, a.seconds * SAMPLE_RATE)
y1, y2 = deque([0] * n, maxlen=n), deque([0] * n, maxlen=n)
fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
l1, = ax1.plot([], [], lw=0.8)
l2, = ax2.plot([], [], lw=0.8)
ax1.set_title("Grove EMG 1 — A0"); ax2.set_title("Grove EMG 2 — A1")
ax2.set_xlabel("Amostras recentes"); ax1.set_ylabel("ADC"); ax2.set_ylabel("ADC")
ax1.set_ylim(0, 1023); ax2.set_ylim(0, 1023)

def update(_):
    for _ in range(80):
        item = parse_sample(ser.readline())
        if item:
            _, v1, v2 = item
            y1.append(v1); y2.append(v2)
    x = list(range(n))
    l1.set_data(x, list(y1)); l2.set_data(x, list(y2))
    ax1.set_xlim(0, n); ax2.set_xlim(0, n)
    return l1, l2

ani = FuncAnimation(fig, update, interval=50, blit=False, cache_frame_data=False)
try:
    plt.tight_layout(); plt.show()
finally:
    ser.close()
