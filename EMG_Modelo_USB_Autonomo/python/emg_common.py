"""Funções comuns de leitura e características para dois canais Grove EMG."""
import numpy as np

SAMPLE_RATE = 200
WINDOW_SAMPLES = 100       # 0,5 s
HOP_SAMPLES = 50           # 0,25 s
FEATURE_NAMES = ["MAV", "RMS", "WL", "ZC", "VAR"]


def parse_sample(line):
    """Lê o pacote ASCII sequence,adc1,adc2; ignora cabeçalhos e linhas inválidas."""
    try:
        text = line.decode("ascii", errors="ignore").strip() if isinstance(line, bytes) else str(line).strip()
        if not text or text.startswith("#"):
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
