"""
Fase 2 (T3) — Clasificación de sexo (hombre/mujer) a partir del audio.

Quick win basado en F0/pitch. Metodología honesta:
  - características con PitchFeatures (pipeline reutilizable)
  - validación cruzada POR HABLANTE (StratifiedGroupKFold) -> sin fuga de hablante
  - clase 'balanced' por el desbalance 78/22
  - métricas macro (P/R/F1) + matriz de confusión + tiempos (criterios del reto)

Ejecutar:  uv run python src/scripts/clasif_sexo.py
"""
from __future__ import annotations

import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd
import librosa
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay, f1_score

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
from pipeline.features import PitchFeatures, SR
from pipeline.splits import stratified_group_kfold

RAIZ = os.path.dirname(SRC)
META_PROC = os.path.join(RAIZ, "data", "processed", "metadata.csv")
DIR_RES = os.path.join(RAIZ, "results")
N_SPLITS = 5


def cargar_ondas(rutas_abs):
    ondas = []
    for r in rutas_abs:
        onda, _ = librosa.load(r, sr=SR, mono=True)
        ondas.append(onda.astype(np.float32))
    return ondas


def main():
    df = pd.read_csv(META_PROC)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    df["ruta_proc_abs"] = df["ruta_proc"].apply(lambda r: os.path.join(RAIZ, r))

    y = df["sexo"].values
    groups = df["hablante"].values
    print(f"Muestras: {len(df)} | clases: {dict(pd.Series(y).value_counts())} "
          f"| hablantes: {len(set(groups))}")

    # --- Extracción de características (una vez) ---
    print("\nExtrayendo F0/pitch (pYIN)...")
    t0 = time.perf_counter()
    ondas = cargar_ondas(df["ruta_proc_abs"])
    X = PitchFeatures(sr=SR).fit_transform(ondas)
    t_feat = time.perf_counter() - t0
    print(f"Características: {X.shape} en {t_feat:.1f}s ({t_feat/len(df)*1000:.0f} ms/clip)")

    # --- CV por hablante ---
    cv = stratified_group_kfold(N_SPLITS)
    y_pred = np.empty_like(y, dtype=object)
    t_train = t_infer = 0.0
    for tr, te in cv.split(X, y, groups):
        clf = Pipeline([
            ("escala", StandardScaler()),
            ("logreg", LogisticRegression(class_weight="balanced", max_iter=1000)),
        ])
        a = time.perf_counter(); clf.fit(X[tr], y[tr]); t_train += time.perf_counter() - a
        a = time.perf_counter(); y_pred[te] = clf.predict(X[te]); t_infer += time.perf_counter() - a

    # --- Métricas ---
    etiquetas = ["hombre", "mujer"]
    print("\n=== Resultados (CV por hablante, 5 folds) ===")
    print(classification_report(y, y_pred, labels=etiquetas, digits=3, zero_division=0))
    print(f"F1 MACRO: {f1_score(y, y_pred, labels=etiquetas, average='macro'):.3f}")
    print(f"\nTiempos: extracción {t_feat:.1f}s | entrenamiento {t_train*1000:.0f} ms "
          f"| inferencia {t_infer*1000:.0f} ms ({t_infer/len(df)*1000:.2f} ms/clip)")

    # --- Figura: matriz de confusión ---
    os.makedirs(DIR_RES, exist_ok=True)
    cm = confusion_matrix(y, y_pred, labels=etiquetas)
    fig, ax = plt.subplots(figsize=(4.5, 4))
    ConfusionMatrixDisplay(cm, display_labels=etiquetas).plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title("Sexo — CV por hablante")
    fig.tight_layout()
    out = os.path.join(DIR_RES, "sexo_confusion.png")
    fig.savefig(out, dpi=120)
    print(f"Figura: {os.path.relpath(out, RAIZ)}")


if __name__ == "__main__":
    main()
