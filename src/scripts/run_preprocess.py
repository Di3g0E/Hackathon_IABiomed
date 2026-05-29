"""
Fase 1 — Aplica el pipeline de preprocesado a los audios locales y hace EDA.

- Lee metadata.csv
- Aplica build_preprocess_pipeline() (mono 16 kHz, recorte de silencio, normalización)
- Guarda WAV procesados en data/processed/<palabra>/
- Calcula duraciones (cruda vs procesada) y detecta clips problemáticos
- Genera figuras de distribución en results/
- Escribe data/processed/metadata.csv (con ruta procesada y duraciones)
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
import soundfile as sf
import librosa
import matplotlib

matplotlib.use("Agg")  # sin ventana: solo guardar figuras
import matplotlib.pyplot as plt

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
from pipeline.preprocessing import build_preprocess_pipeline, SR

RAIZ = os.path.dirname(SRC)
META_IN = os.path.join(RAIZ, "metadata.csv")
DIR_PROC = os.path.join(RAIZ, "data", "processed")
DIR_RES = os.path.join(RAIZ, "results")

DUR_MIN = 0.30  # seg: clips más cortos son sospechosos
DUR_MAX = 3.0   # seg: clips más largos pueden tener ruido/palabras extra


def main():
    df = pd.read_csv(META_IN)
    df["ruta_abs"] = df["ruta"].apply(lambda r: os.path.join(RAIZ, r))

    pipe = build_preprocess_pipeline()

    # --- duración cruda (antes de procesar) ---
    dur_cruda = []
    for ruta in df["ruta_abs"]:
        try:
            dur_cruda.append(librosa.get_duration(path=ruta))
        except Exception as e:
            dur_cruda.append(np.nan)
            print(f"[WARN] no se pudo leer duración de {ruta}: {e}")
    df["dur_cruda_s"] = dur_cruda

    # --- procesado robusto (por fichero, capturando errores) ---
    rutas_proc, dur_proc, fallos = [], [], []
    for ruta_abs, ruta_rel, palabra, fn in zip(
        df["ruta_abs"], df["ruta"], df["palabra"],
        df["ruta"].apply(lambda r: os.path.basename(r))
    ):
        try:
            # fit_transform: los transformadores no tienen estado, así que
            # ajustar por fichero es instantáneo y evita el NotFittedError.
            (onda,) = pipe.fit_transform([ruta_abs])
            destino_dir = os.path.join(DIR_PROC, palabra)
            os.makedirs(destino_dir, exist_ok=True)
            destino = os.path.join(destino_dir, os.path.splitext(fn)[0] + ".wav")
            sf.write(destino, onda, SR)
            rutas_proc.append(os.path.relpath(destino, RAIZ))
            dur_proc.append(len(onda) / SR)
        except Exception as e:
            rutas_proc.append("")
            dur_proc.append(np.nan)
            fallos.append((ruta_rel, str(e)))

    df["ruta_proc"] = rutas_proc
    df["dur_proc_s"] = dur_proc

    os.makedirs(DIR_RES, exist_ok=True)
    df.to_csv(os.path.join(DIR_PROC, "metadata.csv"), index=False, encoding="utf-8")

    # ---------- Resumen ----------
    print(f"\nAudios totales: {len(df)} | procesados OK: {(df['ruta_proc'] != '').sum()} | fallos: {len(fallos)}")
    if fallos:
        print("Fallos:")
        for r, e in fallos:
            print(f"  {r}: {e}")

    print("\nDuración procesada (s):")
    print(df["dur_proc_s"].describe().round(3).to_string())

    cortos = df[df["dur_proc_s"] < DUR_MIN]
    largos = df[df["dur_proc_s"] > DUR_MAX]
    print(f"\nClips < {DUR_MIN}s (revisar): {len(cortos)}")
    for _, r in cortos.iterrows():
        print(f"  {r['ruta']}  ({r['dur_proc_s']:.2f}s)")
    print(f"Clips > {DUR_MAX}s (revisar): {len(largos)}")
    for _, r in largos.iterrows():
        print(f"  {r['ruta']}  ({r['dur_proc_s']:.2f}s)")

    print(f"\nSilencio recortado de media: "
          f"{(df['dur_cruda_s'] - df['dur_proc_s']).mean():.2f}s por clip")

    # ---------- Figuras ----------
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    df["dur_proc_s"].plot.hist(bins=30, ax=axes[0, 0], color="#1f6f8b")
    axes[0, 0].set_title("Duración procesada (s)")
    axes[0, 0].set_xlabel("segundos")
    df["sexo"].value_counts().plot.bar(ax=axes[0, 1], color="#3a7d44")
    axes[0, 1].set_title("Clips por sexo")
    df["origen"].value_counts().plot.bar(ax=axes[1, 0], color="#9b59b6")
    axes[1, 0].set_title("Clips por origen")
    df["palabra"].value_counts().sort_values().plot.barh(ax=axes[1, 1], color="#e67e22")
    axes[1, 1].set_title("Clips por palabra")
    axes[1, 1].tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    fig_path = os.path.join(DIR_RES, "eda_distribuciones.png")
    fig.savefig(fig_path, dpi=110)
    print(f"\nFigura guardada: {os.path.relpath(fig_path, RAIZ)}")
    print(f"Metadata procesada: {os.path.relpath(os.path.join(DIR_PROC, 'metadata.csv'), RAIZ)}")


if __name__ == "__main__":
    main()
