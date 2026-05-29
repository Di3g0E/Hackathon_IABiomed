"""
Paso 2 — T3: clasificación de SEXO (hombre/mujer).

Compara baseline ligero (F0/pitch) con XLS-R, ambos con CV por hablante, y aplica
umbral de confianza + (override manual conceptual): si la confianza < umbral se
deriva al usuario.

Ejecutar:  uv run python src/scripts/2_sexo.py
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
import librosa

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from pipeline.features import PitchFeatures, SR
from pipeline.embeddings import cargar_embeddings_xlsr
from pipeline.clasificacion import (cv_eval, logreg, proba_oof, guarda_confusion,
                                    barrido_confianza, figura_confianza)

META = os.path.join(RAIZ, "data", "processed", "metadata.csv")
DIR_RES = os.path.join(RAIZ, "results")
ETIQ = ["hombre", "mujer"]
UMBRALES = [0.50, 0.60, 0.70, 0.80, 0.90]


def main():
    df = pd.read_csv(META)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    y, groups = df["sexo"].values, df["hablante"].values
    print(f"Muestras: {len(df)} | clases: {dict(pd.Series(y).value_counts())}")

    # Baseline F0/pitch
    print("\n[Baseline F0/pitch]")
    ondas = [librosa.load(os.path.join(RAIZ, r), sr=SR, mono=True)[0].astype(np.float32)
             for r in df["ruta_proc"]]
    Xf0 = PitchFeatures(sr=SR).fit_transform(ondas)
    cv_eval(Xf0, y, groups, ETIQ, 5, logreg, "F0 + LogReg")

    # XLS-R (final)
    print("\n[XLS-R]")
    X = cargar_embeddings_xlsr(df, RAIZ)
    cv_eval(X, y, groups, ETIQ, 5, logreg, "XLS-R + LogReg")

    pred, conf, _ = proba_oof(X, y, groups, n_splits=5)
    print("\nConfianza (autocompletar vs preguntar al usuario):")
    covs, accs = barrido_confianza(pred, conf, y, UMBRALES)

    os.makedirs(DIR_RES, exist_ok=True)
    guarda_confusion(y, pred, ETIQ, "Sexo XLS-R", os.path.join(DIR_RES, "sexo_confusion.png"), "Greens")
    figura_confianza(UMBRALES, covs, accs, "Sexo: cobertura vs fiabilidad",
                     os.path.join(DIR_RES, "sexo_confianza.png"))
    print("\nFiguras: results/sexo_confusion.png, results/sexo_confianza.png")


if __name__ == "__main__":
    main()