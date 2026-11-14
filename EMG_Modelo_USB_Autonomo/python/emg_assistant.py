#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assistente EMG: deteção automática da ligação, recolha guiada e treino.
Executar a partir da pasta raiz do projeto: python python/emg_assistant.py
"""
from __future__ import annotations
import argparse
import csv
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

try:
    import serial
except ImportError:
    raise SystemExit("Falta pyserial. Executa: python -m pip install -r requirements.txt")

from emg_common import (
    find_arduino_ports,
    open_arduino_serial,
    parse_sample,
    reconnect_serial,
)
from gesture_config import DEFAULT_LABELS, GESTURES

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "emg_dataset.csv"
TRAIN_SCRIPT = PROJECT_ROOT / "python" / "train_export.py"
BAUD_CANDIDATES = (115200,)


def banner():
    print("\n" + "=" * 66)
    print("       ASSISTENTE AUTOMÁTICO — SISTEMA sEMG / ARDUINO UNO")
    print("=" * 66)


def list_serial_ports():
    candidates = find_arduino_ports()
    if not candidates:
        print("Não foram encontradas portas série.")
    else:
        print("\nPortas série detetadas:")
        for device, label, is_priority in candidates:
            tag = "[Arduino/USB]" if is_priority else "[Outra]"
            print(f"  {device:12} | {tag:13} | {label}")
    return candidates


def detect_connection(manual_port=None, manual_baud=None):
    candidates_ports = list_serial_ports()
    if manual_port:
        bauds = (manual_baud,) if manual_baud else BAUD_CANDIDATES
        candidates = [(manual_port, "Porta manual", b) for b in bauds]
    else:
        candidates = []
        for device, label, _ in candidates_ports:
            for baud in BAUD_CANDIDATES:
                candidates.append((device, label, baud))

    print("\nA procurar e validar handshake com o Arduino Uno...")
    for device, label, baud in candidates:
        print(f"  A testar {device} ({label}) a {baud} baud...", end=" ", flush=True)
        try:
            ser = open_arduino_serial(device, baud=baud, timeout=0.2, verify_stream=True)
            ser.close()
            print("OK — Handshake e fluxo EMG confirmados.")
            return device, baud
        except (serial.SerialException, OSError) as exc:
            print(f"falhou ({exc})")

    raise RuntimeError(
        "Não foi encontrado um fluxo EMG válido. Confirma o cabo USB, drivers (CH340/Arduino) "
        "e se o firmware firmware/emg_stream_hc05/emg_stream_hc05.ino está carregado no Uno."
    )


def collect_session(port, baud, seconds, repetitions, labels, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    new_file = not output.exists() or output.stat().st_size == 0
    session = datetime.now().strftime("%Y%m%d_%H%M%S")
    total = 0
    print(f"\nLigação ativa: {port} ({baud} baud)")
    print(f"Dataset: {output}")
    print("\nINSTRUÇÕES:")
    print("- Coloca os elétrodos e mantém a mesma posição durante a sessão.")
    print("- Durante cada gravação, mantém apenas o gesto indicado.")
    print("- Relaxa completamente durante as pausas.")
    print("- Podes interromper com Ctrl+C; os dados já escritos são preservados.")

    ser = None
    try:
        ser = open_arduino_serial(port, baud=baud, timeout=0.2, verify_stream=True)
        with output.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow(["sequence", "emg1", "emg2", "label",
                                 "repetition", "session"])
                f.flush()
            for li, label in enumerate(labels, 1):
                print(f"\n[{li}/{len(labels)}] Próximo gesto: {label}")
                print("  " + GESTURES.get(label, "Gesto adicional definido pelo utilizador."))
                input("Prepara o gesto e prime ENTER quando estiveres pronto...")
                for rep in range(1, repetitions + 1):
                    input(f"  Repetição {rep}/{repetitions}: prime ENTER para começar...")
                    try:
                        ser.reset_input_buffer()
                    except (serial.SerialException, OSError):
                        ser = reconnect_serial(port, baud=baud, timeout=0.2)

                    print(f"  A recolher {seconds:g} s...", end="", flush=True)
                    start = time.monotonic()
                    rows = 0
                    while time.monotonic() - start < seconds:
                        try:
                            raw = ser.readline()
                        except (serial.SerialException, OSError):
                            ser = reconnect_serial(port, baud=baud, timeout=0.2)
                            continue
                        item = parse_sample(raw)
                        if item is None:
                            continue
                        seq, a, b = item
                        writer.writerow([seq, a, b, label, rep, session])
                        rows += 1
                    f.flush()
                    total += rows
                    print(f" {rows} amostras")
                    if rows < int(seconds * 80):
                        print("  AVISO: poucas amostras recebidas. Verifica a ligação e a taxa de transmissão.")
                    if rep < repetitions:
                        time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nRecolha interrompida. Os dados existentes foram guardados.")
    except serial.SerialException as exc:
        raise RuntimeError(f"Erro durante a comunicação série: {exc}") from exc
    finally:
        if ser is not None and ser.is_open:
            ser.close()

    print(f"\nAmostras adicionadas nesta sessão: {total}")
    print(f"Dataset atualizado: {output}")
    return total


def train_model():
    if not TRAIN_SCRIPT.exists():
        raise RuntimeError(f"Não encontrei o script de treino: {TRAIN_SCRIPT}")
    print("\nA iniciar treino e avaliação do modelo...")
    result = subprocess.run([sys.executable, str(TRAIN_SCRIPT)],
                            cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print("\nO treino não foi concluído. Confirma se existem dados suficientes "
              "e se cada classe tem várias repetições.")
        return False
    print("\nTreino concluído. O ficheiro model.h foi atualizado.")
    print("Para utilizar o novo modelo, abre e volta a carregar o sketch "
          "em firmware/emg_recognition_uno/ no Arduino Uno.")
    return True


def main():
    ap = argparse.ArgumentParser(description="Recolha e treino automatizados de EMG")
    ap.add_argument("--port", help="Forçar porta, por exemplo COM7 ou /dev/ttyUSB0")
    ap.add_argument("--baud", type=int, help="Forçar baud rate")
    ap.add_argument("--seconds", type=float, default=5.0,
                    help="Duração de cada repetição (padrão: 5 s)")
    ap.add_argument("--repetitions", type=int, default=8,
                    help="Repetições por gesto (padrão: 8)")
    ap.add_argument("--labels", default=",".join(DEFAULT_LABELS),
                    help="Gestos separados por vírgulas; por defeito usa gesture_config.py")
    ap.add_argument("--output", default=str(DATA_FILE),
                    help="Caminho do CSV de dados")
    ap.add_argument("--train-only", action="store_true",
                    help="Treinar com o dataset existente, sem recolher")
    ap.add_argument("--no-train", action="store_true",
                    help="Terminar após recolher, sem treinar")
    args = ap.parse_args()

    banner()
    if args.train_only:
        train_model()
        return
    if args.seconds < 1 or args.repetitions < 2:
        raise SystemExit("Usa --seconds >= 1 e --repetitions >= 2.")
    labels = [x.strip() for x in args.labels.split(",") if x.strip()]
    if len(labels) < 2:
        raise SystemExit("São necessárias pelo menos duas classes.")
    output = Path(args.output)
    if not output.is_absolute():
        output = PROJECT_ROOT / output

    try:
        port, baud = detect_connection(args.port, args.baud)
        collect_session(port, baud, args.seconds, args.repetitions, labels, output)
        if not args.no_train:
            train_model()
    except (RuntimeError, OSError) as exc:
        raise SystemExit(f"\nERRO: {exc}")


if __name__ == "__main__":
    main()
