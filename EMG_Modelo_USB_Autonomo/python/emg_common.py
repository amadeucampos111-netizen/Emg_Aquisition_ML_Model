"""Funções comuns de leitura, conexão robusta e características para dois canais Grove EMG."""
import time
import numpy as np
import serial
from serial.tools import list_ports

SAMPLE_RATE = 200
WINDOW_SAMPLES = 100       # 0,5 s
HOP_SAMPLES = 50           # 0,25 s
FEATURE_NAMES = ["MAV", "RMS", "WL", "ZC", "VAR"]

# Identificadores USB (VID, PID) para Arduino Uno R3 Original e clones comuns
ARDUINO_USB_IDS = {
    (0x2341, 0x0043): "Arduino Uno R3 (Original)",
    (0x2341, 0x0001): "Arduino Uno (Rev1/Rev2)",
    (0x2A03, 0x0043): "Arduino Uno R3 (Arduino.org)",
    (0x1A86, 0x7523): "Arduino Uno Clone (CH340)",
    (0x1A86, 0x5523): "Arduino Uno Clone (CH341)",
    (0x10C4, 0xEA60): "Arduino Uno Clone (CP2102)",
    (0x0403, 0x6001): "Arduino Uno Clone (FT232R)",
}


def find_arduino_ports():
    """Retorna lista ordenada de portas candidatas, priorizando VID/PID de Arduino Uno."""
    all_ports = list(list_ports.comports())
    matched = []
    others = []

    for p in all_ports:
        desc_lower = (p.description or "").lower()
        vid_pid = (p.vid, p.pid) if (p.vid is not None and p.pid is not None) else None
        if vid_pid in ARDUINO_USB_IDS:
            matched.append((p.device, ARDUINO_USB_IDS[vid_pid], True))
        elif any(k in desc_lower for k in ("arduino", "ch340", "cp210", "usb serial", "usb-serial")):
            matched.append((p.device, p.description or "USB Serial", True))
        else:
            others.append((p.device, p.description or "Porta Série", False))

    return matched + others


def open_arduino_serial(port, baud=115200, timeout=0.25, boot_wait=2.2, verify_stream=True):
    """
    Abre a porta série com o Arduino Uno R3 de forma segura:
    1. Aguarda o reset automático do bootloader (DTR).
    2. Limpa buffers residuais de entrada e saída.
    3. Executa handshake PING/PONG e verifica pacotes sEMG válidos.
    """
    ser = serial.Serial(port, baudrate=baud, timeout=timeout, write_timeout=0.5)
    try:
        # 1. Aguardar reset do bootloader provocado pela abertura da porta USB
        time.sleep(boot_wait)

        # 2. Descartar lixo acumulado durante o arranque
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        if not verify_stream:
            return ser

        # 3. Handshake ativo + validação do fluxo de amostras
        try:
            ser.write(b"PING\n")
            ser.flush()
        except serial.SerialException:
            pass

        deadline = time.monotonic() + 3.0
        valid_samples = 0
        pong_received = False

        while time.monotonic() < deadline:
            raw = ser.readline()
            if not raw:
                continue
            text = raw.decode("ascii", errors="ignore").strip()
            if not text:
                continue
            if "PONG" in text or "EMG_USB_READY" in text or "EMG_RECOGNIZER_READY" in text:
                pong_received = True
            if parse_sample(text) is not None:
                valid_samples += 1
            if valid_samples >= 3 or (pong_received and valid_samples >= 1):
                ser.reset_input_buffer()
                return ser

        ser.close()
        raise serial.SerialException(
            f"Porta {port} aberta, mas não enviou handshake nem pacotes EMG válidos. "
            "Confirma se o firmware de aquisição (emg_stream_hc05.ino) está carregado."
        )
    except Exception:
        if ser.is_open:
            ser.close()
        raise


def auto_connect_arduino(manual_port=None, baud=115200, timeout=0.25, verify_stream=True):
    """Deteta automaticamente o Arduino Uno R3 e devolve uma ligação serial pronta."""
    if manual_port:
        ser = open_arduino_serial(manual_port, baud=baud, timeout=timeout, verify_stream=verify_stream)
        return ser, manual_port

    candidates = find_arduino_ports()
    if not candidates:
        raise serial.SerialException(
            "Nenhuma porta série encontrada. Verifica o cabo USB e os drivers (CH340 / Arduino)."
        )

    errors = []
    for device, label, is_priority in candidates:
        try:
            ser = open_arduino_serial(device, baud=baud, timeout=timeout, verify_stream=verify_stream)
            return ser, device
        except (serial.SerialException, OSError) as exc:
            errors.append(f"{device} ({label}): {exc}")

    raise serial.SerialException(
        "Não foi possível estabelecer comunicação com o Arduino Uno.\n  - " + "\n  - ".join(errors)
    )


def reconnect_serial(port, baud=115200, timeout=0.25, retries=5, delay=1.5):
    """Tenta restabelecer a ligação caso ocorra uma falha momentânea no cabo USB."""
    for attempt in range(1, retries + 1):
        try:
            print(f"\n[!] Ligação perdida. A tentar reconectar ({attempt}/{retries})...")
            ser, active_port = auto_connect_arduino(manual_port=port, baud=baud, timeout=timeout, verify_stream=True)
            print(f"[✓] Ligação restabelecida em {active_port}.")
            return ser
        except (serial.SerialException, OSError):
            time.sleep(delay)
    raise serial.SerialException(f"Falha ao reconectar ao Arduino após {retries} tentativas.")


def parse_sample(line):
    """Lê o pacote ASCII sequence,adc1,adc2; ignora cabeçalhos e linhas inválidas."""
    try:
        text = line.decode("ascii", errors="ignore").strip() if isinstance(line, bytes) else str(line).strip()
        if not text or text.startswith("#") or text.startswith("PONG"):
            return None
        parts = text.split(",")
        if len(parts) != 3:
            return None
        seq, ch1, ch2 = (int(x) for x in parts)
        if not (0 <= ch1 <= 1023 and 0 <= ch2 <= 1023):
            return None
        return seq, ch1, ch2
    except (ValueError, TypeError):
        return None


def channel_features(x):
    x = np.asarray(x, dtype=np.float64)
    centered = x - np.mean(x)
    variance = float(np.mean(centered ** 2))
    sd = float(np.sqrt(variance))
    mav = float(np.mean(np.abs(centered)))
    wl = float(np.sum(np.abs(np.diff(x))))
    threshold = max(2.0, 0.01 * sd)
    a, b = centered[:-1], centered[1:]
    zc = int(np.sum(((a > threshold) & (b < -threshold)) |
                    ((a < -threshold) & (b > threshold))))
    return [mav, sd, wl, float(zc), variance]


def extract_features(window):
    arr = np.asarray(window, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError("A janela deve ter duas colunas: EMG1 e EMG2.")
    return np.asarray(channel_features(arr[:, 0]) + channel_features(arr[:, 1]), dtype=np.float64)
