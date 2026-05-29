"""
Paso 3 — T2: clasificación de ORIGEN (España / Latam / No nativo).

Compara características ligeras (MFCC+pitch) con embeddings (ECAPA, XLS-R), CV por
hablante. El mejor (XLS-R) se evalúa con umbral de confianza + voto por hablante
(human-in-the-loop: si la confianza < umbral, se pregunta al usuario; la corrección
manual se propaga a todas las palabras del hablante).

Ejecutar:  uv run python src/scripts/3_origen.py
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

# transformers antes que speechbrain (evita el conflicto del hook lazy de k2)
import torch  # noqa: F401
from transformers import AutoModel  # noqa: F401

from pipeline.features import MFCCFeatures, PitchFeatures, SR
from pipeline.embeddings import EcapaEmbedding, cargar_embeddings_xlsr
from pipeline.clasificacion import (cv_eval, logreg, proba_oof, guarda_confusion,
                                    voto_por_hablante, barrido_confianza, figura_confianza)
from sklearn.metrics import f1_score

META = os.path.join(RAIZ, "data", "processed", "metadata.csv")
DIR_RES = os.path.join(RAIZ, "results")
ET3 = ["España", "Latam", "No nativo"]
ET2 = ["España", "Latam"]
UMBRALES = [0.50, 0.60, 0.70, 0.80, 0.90]


def main():
    df = pd.read_csv(META)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    y, groups = df["origen"].values, df["hablante"].values
    m2 = df["origen"].isin(ET2).values
    print(f"Muestras: {len(df)} | origen: {dict(df['origen'].value_counts())}")
    ondas = [librosa.load(os.path.join(RAIZ, r), sr=SR, mono=True)[0].astype(np.float32)
             for r in df["ruta_proc"]]

    print("\n===== Comparación de características (España vs Latam, F1) =====")
    Xmfcc = np.hstack([MFCCFeatures(sr=SR).fit_transform(ondas),
                       PitchFeatures(sr=SR).fit_transform(ondas)])
    cv_eval(Xmfcc[m2], y[m2], groups[m2], ET2, 5, logreg, "MFCC+pitch")
    cv_eval(EcapaEmbedding().embed_many(ondas)[m2], y[m2], groups[m2], ET2, 5, logreg, "ECAPA")
    X = cargar_embeddings_xlsr(df, RAIZ)
    cv_eval(X[m2], y[m2], groups[m2], ET2, 5, logreg, "XLS-R")

    print("\n===== XLS-R: 3 clases =====")
    cv_eval(X, y, groups, ET3, 4, logreg, "XLS-R 3 clases")

    print("\n===== XLS-R: confianza + voto (España vs Latam) =====")
    pred, conf, _ = proba_oof(X[m2], y[m2], groups[m2], n_splits=5)
    covs, accs = barrido_confianza(pred, conf, y[m2], UMBRALES)
    yt, ypv = voto_por_hablante(groups[m2], y[m2], pred)
    print(f"  Voto por hablante: F1 MACRO = {f1_score(yt, ypv, labels=ET2, average='macro'):.3f} "
          f"({len(yt)} hablantes)")

    os.makedirs(DIR_RES, exist_ok=True)
    guarda_confusion(y[m2], pred, ET2, "Origen España vs Latam (XLS-R)",
                     os.path.join(DIR_RES, "origen_confusion.png"), "Purples")
    figura_confianza(UMBRALES, covs, accs, "Origen: cobertura vs fiabilidad",
                     os.path.join(DIR_RES, "origen_confianza.png"))
    print("\nFiguras: results/origen_confusion.png, results/origen_confianza.png")


if __name__ == "__main__":
    main()