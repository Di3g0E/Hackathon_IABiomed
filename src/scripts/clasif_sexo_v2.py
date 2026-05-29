"""
Fase 2b (T3) — Sexo mejorado con embeddings XLS-R + confianza + override manual.

Reutiliza los embeddings XLS-R cacheados (mismos de T2) en lugar de las 8
características de pitch del baseline (F1 0.742). Añade umbral de confianza:
si la seguridad < umbral -> preguntar al usuario (human-in-the-loop).

Ejecutar:  uv run python src/scripts/clasif_sexo_v2.py
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay, f1_score

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from scripts.origen_confianza import embeddings_cacheados, proba_oof, META, DIR_RES

UMBRALES = [0.50, 0.60, 0.70, 0.80, 0.90]
F1_BASELINE_F0 = 0.742


def main():
    df = pd.read_csv(META)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    y = df["sexo"].values
    groups = df["hablante"].values
    print(f"Muestras: {len(df)} | clases: {dict(pd.Series(y).value_counts())}")

    X = embeddings_cacheados(df)
    pred, conf, _ = proba_oof(X, y, groups, n_splits=5)

    etiquetas = ["hombre", "mujer"]
    print("\n=== T3 Sexo con XLS-R (CV por hablante) ===")
    print(classification_report(y, pred, labels=etiquetas, digits=3, zero_division=0))
    f1m = f1_score(y, pred, labels=etiquetas, average="macro")
    print(f"F1 MACRO: {f1m:.3f}   (baseline F0+LogReg: {F1_BASELINE_F0})  "
          f"-> {'+' if f1m>=F1_BASELINE_F0 else ''}{(f1m-F1_BASELINE_F0):.3f}")

    # ---- Confianza + preguntar al usuario ----
    print("\nUmbral de confianza -> qué pasa:")
    print(f"  {'umbral':>6} {'auto%':>7} {'acc(auto)':>10} {'consultar%':>11}")
    covs, accs = [], []
    for u in UMBRALES:
        m = conf >= u
        cov = m.mean()
        acc = (pred[m] == y[m]).mean() if m.any() else float("nan")
        covs.append(cov); accs.append(acc)
        print(f"  {u:>6.2f} {cov*100:>6.0f}% {acc:>9.3f} {(1-cov)*100:>10.0f}%")

    bajos = [(df['hablante'][i], pred[i], round(float(conf[i]), 2), y[i])
             for i in np.argsort(conf)[:5]]
    print("\nClips de menor confianza (se preguntaría al usuario):")
    for h, p, c, t in bajos:
        print(f"    {h:18s} sugerido={p:7s} conf={c}  (real={t})")

    # ---- Figuras ----
    os.makedirs(DIR_RES, exist_ok=True)
    cm = confusion_matrix(y, pred, labels=etiquetas)
    fig, ax = plt.subplots(figsize=(4.5, 4))
    ConfusionMatrixDisplay(cm, display_labels=etiquetas).plot(ax=ax, cmap="Greens", colorbar=False)
    ax.set_title(f"Sexo XLS-R (F1 macro {f1m:.2f})")
    fig.tight_layout(); fig.savefig(os.path.join(DIR_RES, "sexo_xlsr_confusion.png"), dpi=120)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(UMBRALES, [c*100 for c in covs], "o-", label="Cobertura (auto%)")
    ax.plot(UMBRALES, [a*100 for a in accs], "s-", label="Fiabilidad (acc auto%)")
    ax.set_xlabel("Umbral de confianza"); ax.set_ylabel("%"); ax.set_ylim(0, 105)
    ax.set_title("Sexo: cobertura vs fiabilidad"); ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(DIR_RES, "sexo_confianza.png"), dpi=120)
    print("\nFiguras: results/sexo_xlsr_confusion.png, results/sexo_confianza.png")


if __name__ == "__main__":
    main()
