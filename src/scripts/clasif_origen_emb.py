"""
Fase 3b (T2) — Origen con embeddings preentrenados (ECAPA y XLS-R).

Compara ambos contra el baseline MFCC. Para cada uno:
  - 3 clases (España/Latam/No nativo) y 2 clases (España vs Latam), CV por hablante
  - voto por hablante (agrega las palabras de cada hablante) -> más realista

Ejecutar:  uv run python src/scripts/clasif_origen_emb.py
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd
import librosa
from sklearn.metrics import f1_score

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

# Inicializa torch/transformers ANTES que speechbrain: speechbrain instala un
# hook de import perezoso (k2) que rompe la inicialización de torch.distributed.
import torch  # noqa: E402,F401
from transformers import AutoModel, AutoFeatureExtractor  # noqa: E402,F401

from pipeline.embeddings import EcapaEmbedding, XLSREmbedding
from scripts.clasif_origen import cv_eval, logreg, guarda_confusion, SR

META = os.path.join(RAIZ, "data", "processed", "metadata.csv")


def voto_por_hablante(hablantes, y_true, y_pred):
    """Agrega las predicciones de cada hablante por mayoría."""
    sp = {}
    for h, t, p in zip(hablantes, y_true, y_pred):
        sp.setdefault(h, {"true": t, "preds": []})
        sp[h]["preds"].append(p)
    yt = [v["true"] for v in sp.values()]
    yp = [Counter(v["preds"]).most_common(1)[0][0] for v in sp.values()]
    return np.array(yt), np.array(yp)


def main():
    df = pd.read_csv(META)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    df["abs"] = df["ruta_proc"].apply(lambda r: os.path.join(RAIZ, r))
    print(f"Muestras: {len(df)} | hablantes: {df['hablante'].nunique()}")
    print("Cargando audios...")
    ondas = [librosa.load(p, sr=SR, mono=True)[0].astype(np.float32) for p in df["abs"]]

    grp = df["hablante"].values
    y_all = df["origen"].values
    m2 = df["origen"].isin(["España", "Latam"]).values

    for emb_cls in (EcapaEmbedding, XLSREmbedding):
        print(f"\n========== {emb_cls.NOMBRE} ==========")
        t0 = time.perf_counter()
        emb = emb_cls()
        X = emb.embed_many(ondas)
        print(f"Embeddings: {X.shape} en {time.perf_counter()-t0:.1f}s")

        print("\n[3 clases]")
        cv_eval(X, y_all, grp, ["España", "Latam", "No nativo"], 4, logreg, emb_cls.NOMBRE)

        print("\n[2 clases: España vs Latam]")
        yp2, _ = cv_eval(X[m2], y_all[m2], grp[m2], ["España", "Latam"], 5, logreg, emb_cls.NOMBRE)
        guarda_confusion(y_all[m2], yp2, ["España", "Latam"],
                         f"Origen 2 clases — {emb_cls.NOMBRE}",
                         f"origen_2clases_{emb_cls.NOMBRE.split('-')[0].lower()}.png")

        yt, ypv = voto_por_hablante(grp[m2], y_all[m2], yp2)
        f1v = f1_score(yt, ypv, labels=["España", "Latam"], average="macro")
        print(f"  Voto por hablante (2 clases): F1 MACRO = {f1v:.3f}  "
              f"({len(yt)} hablantes)")


if __name__ == "__main__":
    main()
