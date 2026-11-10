"""Recolhe dados rotulados do Arduino através do HC-05 (ou USB)."""
import argparse
import csv
import os
import time
from datetime import datetime
import serial
from emg_common import parse_sample
from gesture_config import DEFAULT_LABELS, GESTURES


def main():
    p = argparse.ArgumentParser(description="Recolha de dados EMG de 2 canais")
    p.add_argument("--port", required=True, help="Porta COM do HC-05, por exemplo COM7")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--seconds", type=float, default=5.0, help="Segundos por repetição")
    p.add_argument("--repetitions", type=int, default=8)
    p.add_argument("--output", default="data/emg_dataset.csv")
    p.add_argument("--labels", default=",".join(DEFAULT_LABELS), help="Lista de classes separadas por vírgula")
    args = p.parse_args()
    labels = [x.strip() for x in args.labels.split(",") if x.strip()]
    if len(labels) < 2:
        raise SystemExit("Indica pelo menos duas classes.")
    if args.seconds < 1 or args.repetitions < 2:
        raise SystemExit("Usa pelo menos 1 segundo e 2 repetições por classe.")

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    new_file = not os.path.exists(args.output)
    session = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("Classes:", ", ".join(labels))
    for label in labels:
        print(f"  - {label}: {GESTURES.get(label, 'Gesto adicional definido pelo utilizador.')}")
    print("Mantém o gesto estável e evita contrair desnecessariamente o ombro.")

    try:
        with serial.Serial(args.port, args.baud, timeout=0.25) as ser, \
                open(args.output, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow(["sequence", "emg1", "emg2", "label", "repetition", "session"])
            time.sleep(2)
            ser.reset_input_buffer()
            for label in labels:
                input(f"\nPrepara '{label}'. ENTER para iniciar as repetições...")
                for rep in range(1, args.repetitions + 1):
                    input(f"  Repetição {rep}/{args.repetitions}: ENTER e mantém durante {args.seconds:g} s...")
                    ser.reset_input_buffer()
                    start = time.monotonic()
                    rows = 0
                    while time.monotonic() - start < args.seconds:
                        sample = parse_sample(ser.readline())
                        if sample is None:
                            continue
                        seq, a, b = sample
                        writer.writerow([seq, a, b, label, rep, session])
                        rows += 1
                    f.flush()
                    print(f"    {rows} amostras guardadas")
                    time.sleep(1.0)
    except serial.SerialException as exc:
        raise SystemExit(f"Erro na porta série: {exc}")
    print(f"\nDataset guardado em: {args.output}")
    print("Repete a recolha noutra sessão e com os elétrodos reposicionados para testar robustez.")


if __name__ == "__main__":
    main()
