"""
Paso 4 — T1: reconocimiento de FONEMAS (Allosaurus vs wav2vec2) + equidad.

Mide P/R/F1 y PER contra la referencia canónica de Bosch (plegado dialectal),
con desglose por origen (auditoría de sesgo).

Ejecutar:  uv run python src/scripts/4_fonemas.py
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

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from pipeline.reconocedor import W2V, Allo, normaliza_sec, buscar_ref
from pipeline.alineamiento import alinear, agregar

META = os.path.join(RAIZ, "data", "processed", "metadata.csv")
DIR_RES = os.path.join(RAIZ, "results")


def evalua(nombre, reconoce_fn, df, usa_path):
    por_clip, por_origen = [], {}
    t0 = time.perf_counter()
    for _, r in df.iterrows():
        ref = buscar_ref(r["palabra"])
        if usa_path:
            hip = normaliza_sec(reconoce_fn(r["abs"]))
        else:
            wav, _ = librosa.load(r["abs"], sr=16000)
            hip = normaliza_sec(reconoce_fn(wav))
        res = alinear(ref, hip)
        por_clip.append(res)
        por_origen.setdefault(r["origen"], []).append(res)
    dur = time.perf_counter() - t0
    g = agregar(por_clip)
    print(f"\n### {nombre} ###  ({dur:.1f}s, {dur/len(df)*1000:.0f} ms/clip)")
    print(f"  P={g.precision:.3f}  R={g.recall:.3f}  F1={g.f1:.3f}  PER={g.per:.3f}")
    for orig, lst in sorted(por_origen.items()):
        go = agregar(lst)
        print(f"    {orig:10s} n={len(lst):3d}  F1={go.f1:.3f}  PER={go.per:.3f}")
    return g


def main():
    df = pd.read_csv(META)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    df["abs"] = df["ruta_proc"].apply(lambda r: os.path.join(RAIZ, r))
    print(f"Clips: {len(df)}")

    print("\nCargando wav2vec2...")
    g_w2v = evalua("wav2vec2-xlsr-espeak", W2V().reconoce, df, usa_path=False)
    print("\nCargando Allosaurus...")
    g_allo = evalua("Allosaurus", Allo().reconoce_path, df, usa_path=True)

    os.makedirs(DIR_RES, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4))
    nombres, gs = ["wav2vec2", "Allosaurus"], [g_w2v, g_allo]
    x = np.arange(2)
    ax.bar(x - 0.2, [g.precision for g in gs], 0.2, label="Precision")
    ax.bar(x, [g.recall for g in gs], 0.2, label="Recall")
    ax.bar(x + 0.2, [g.f1 for g in gs], 0.2, label="F1")
    ax.set_xticks(x); ax.set_xticklabels(nombres); ax.set_ylim(0, 1)
    ax.set_title("Reconocimiento de fonemas — comparación"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(DIR_RES, "fonemas_comparacion.png"), dpi=120)
    print("\nFigura: results/fonemas_comparacion.png")


if __name__ == "__main__":
    main()