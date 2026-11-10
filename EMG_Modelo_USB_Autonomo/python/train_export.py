"""Treina classificador linear leve e exporta coeficientes para o Arduino Uno."""
import argparse
import os
import re
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from emg_common import extract_features, WINDOW_SAMPLES, HOP_SAMPLES
from gesture_config import DEFAULT_LABELS, GESTURES

LABEL_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")


def make_windows(df, window, hop):
    required = {"emg1", "emg2", "label", "repetition", "session"}
    if not required.issubset(df.columns):
        raise SystemExit(f"CSV deve conter as colunas: {sorted(required)}. Volta a recolher os dados com a versão atual de collect_data.py.")
    X, y, groups = [], [], []
    # Cada repetição é um grupo indivisível para reduzir fuga de dados entre treino e teste.
    for (session, label, repetition), group in df.groupby(["session", "label", "repetition"], sort=False):
        values = group[["emg1", "emg2"]].to_numpy(dtype=float)
        if len(values) < window:
            continue
        group_id = f"{session}_{label}_{repetition}"
        for start in range(0, len(values) - window + 1, hop):
            X.append(extract_features(values[start:start + window]))
            y.append(str(label))
            groups.append(group_id)
    if not X:
        raise SystemExit("Não existem janelas completas. Recolhe mais dados por repetição.")
    return np.asarray(X), np.asarray(y), np.asarray(groups)


def fmt(v):
    value = f"{float(v):.9g}"
    if "." not in value and "e" not in value.lower():
        value += ".0"
    return value + "f"


def export_header(pipeline, output_path, min_gap):
    scaler = pipeline.named_steps["standardscaler"]
    clf = pipeline.named_steps["linearsvc"]
    labels = [str(x) for x in clf.classes_]
    for label in labels:
        if not LABEL_RE.fullmatch(label):
            raise SystemExit(f"Etiqueta '{label}' inválida. Usa 1-15 caracteres ASCII: letras, números e underscore.")
    n_classes, n_features = clf.coef_.shape
    lines = [
        "// Gerado automaticamente por python/train_export.py. Não editar manualmente.",
        "#pragma once", "#include <avr/pgmspace.h>",
        "#define MODEL_VALID 1",
        f"#define MODEL_N_CLASSES {n_classes}",
        f"#define MODEL_N_FEATURES {n_features}",
        f"#define MODEL_MIN_GAP {fmt(min_gap)}",
        f"const char MODEL_LABELS[MODEL_N_CLASSES][16] PROGMEM = {{",
    ]
    lines += [f'  "{label}",' for label in labels]
    lines += ["};", "const float MODEL_MEAN[MODEL_N_FEATURES] PROGMEM = {"]
    lines += ["  " + ", ".join(fmt(x) for x in scaler.mean_) + "", "};"]
    lines += ["const float MODEL_SCALE[MODEL_N_FEATURES] PROGMEM = {"]
    lines += ["  " + ", ".join(fmt(x) for x in scaler.scale_) + "", "};"]
    lines += ["const float MODEL_COEF[MODEL_N_CLASSES][MODEL_N_FEATURES] PROGMEM = {"]
    for row in clf.coef_:
        lines.append("  {" + ", ".join(fmt(x) for x in row) + "},")
    lines += ["};", "const float MODEL_BIAS[MODEL_N_CLASSES] PROGMEM = {"]
    lines += ["  " + ", ".join(fmt(x) for x in clf.intercept_) + "", "};", ""]
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    p = argparse.ArgumentParser(description="Treina e exporta um classificador EMG para Arduino Uno")
    p.add_argument("--input", default="data/emg_dataset.csv")
    p.add_argument("--model", default="models/emg_linear_model.joblib")
    p.add_argument("--header", default="firmware/emg_recognition_uno/model.h")
    p.add_argument("--c", type=float, default=0.5, help="Regularização do classificador LinearSVC")
    p.add_argument("--min-gap", type=float, default=0.35, help="Margem mínima para aceitar uma previsão no Arduino")
    args = p.parse_args()

    df = pd.read_csv(args.input)
    # Treina apenas as classes ativas em gesture_config.py. Assim, dados antigos
    # de experiências anteriores não reintroduzem gestos removidos.
    active_labels = DEFAULT_LABELS
    df["label"] = df["label"].astype(str)
    df = df[df["label"].isin(active_labels)].copy()
    missing = [label for label in active_labels if label not in set(df["label"])]
    if missing:
        raise SystemExit("Ainda faltam dados para estes gestos: " + ", ".join(missing) +
                         ". Recolhe exemplos de todos os gestos ativos antes do treino.")
    # O firmware Uno usa uma janela fixa de 100 amostras e avanço de 50.
    X, y, groups = make_windows(df, WINDOW_SAMPLES, HOP_SAMPLES)
    classes, counts = np.unique(y, return_counts=True)
    if len(classes) < 2:
        raise SystemExit("São necessárias pelo menos duas classes.")
    if len(np.unique(groups)) < 5:
        raise SystemExit("Recolhe mais repetições independentes (idealmente 8-10 por gesto).")
    print("Gestos ativos:", ", ".join(active_labels))
    print("Janelas por classe:")
    for name, count in zip(classes, counts):
        print(f"  {name}: {count}")

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, test_idx = next(splitter.split(X, y, groups))
    model = make_pipeline(
        StandardScaler(),
        LinearSVC(C=args.c, class_weight="balanced", max_iter=30000, random_state=42),
    )
    model.fit(X[train_idx], y[train_idx])
    pred = model.predict(X[test_idx])
    print(f"\nAcurácia em repetições não usadas no treino: {accuracy_score(y[test_idx], pred):.3f}")
    print(classification_report(y[test_idx], pred, zero_division=0))
    print("Matriz de confusão (linhas=real; colunas=previsto):")
    print(confusion_matrix(y[test_idx], pred, labels=model.classes_))

    # Para o modelo embarcado, treina novamente com todos os dados disponíveis.
    model.fit(X, y)
    os.makedirs(os.path.dirname(args.model) or ".", exist_ok=True)
    joblib.dump({"model": model, "window_samples": WINDOW_SAMPLES, "hop_samples": HOP_SAMPLES,
                 "sample_rate": 200, "classes": model.classes_.tolist()}, args.model)
    export_header(model, args.header, args.min_gap)
    print(f"\nModelo Python: {args.model}")
    print(f"Cabeçalho Arduino: {args.header}")
    print("Agora abre em Arduino IDE o sketch em firmware/emg_recognition_uno/ e carrega-o no Uno.")
    print("Nota: a margem mínima é um limiar inicial; ajusta-a com testes reais e validação independente.")


if __name__ == "__main__":
    main()
