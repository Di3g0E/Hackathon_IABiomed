"""
Preparación de datos: construcción de metadata y preprocesado de audio.

- construir_metadata(raiz): parsea los nombres de archivo de
  data/raw/Base_datos_palabras/ y escribe data/metadata.csv.
- preprocesar(raiz): aplica el pipeline de preprocesado, guarda WAV en
  data/processed/, escribe data/processed/metadata.csv y la figura EDA.
"""
from __future__ import annotations

import csv
import os
import unicodedata

import numpy as np
import pandas as pd
import soundfile as sf
import librosa
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pipeline.preprocessing import build_preprocess_pipeline, SR

SEX_TOKENS = {"h": "hombre", "m": "mujer"}
ESPANA = {"esp"}
LATAM = {"arg", "mex", "col", "chile", "ven", "peru", "cuba", "para",
         "gua", "cr", "bol", "uru", "ecu", "pan", "rd", "hon", "nic", "salv", "py"}
NO_NATIVO = {"eeuu", "fra", "ita", "ale", "ger", "uk", "usa", "bra", "por"}
DUDOSOS = {"eeuu", "usa"}

DUR_MIN, DUR_MAX = 0.30, 3.0


def normaliza(texto: str) -> str:
    return unicodedata.normalize("NFC", texto).strip().lower()


def pais_a_origen(pais: str) -> str:
    if pais in ESPANA:
        return "España"
    if pais in LATAM:
        return "Latam"
    if pais in NO_NATIVO:
        return "No nativo"
    return "DESCONOCIDO"


def _parse_tokens(tokens):
    hablante = tokens[0] if tokens else ""
    sexo_raw, sin_sexo = "", []
    for t in tokens[1:]:
        tl = t.lower()
        if tl in SEX_TOKENS and not sexo_raw:
            sexo_raw = tl
        else:
            sin_sexo.append(tl)
    return hablante, sexo_raw, "_".join(sin_sexo) if sin_sexo else ""


def construir_metadata(raiz: str) -> pd.DataFrame:
    base = os.path.join(raiz, "data", "raw", "Base_datos_palabras")
    filas = []
    for carpeta in sorted(os.listdir(base)):
        ruta_carpeta = os.path.join(base, carpeta)
        if not os.path.isdir(ruta_carpeta):
            continue
        palabra = normaliza(carpeta)
        for fn in sorted(os.listdir(ruta_carpeta)):
            if not fn.lower().endswith(".mp3"):
                continue
            tokens = normaliza(os.path.splitext(fn)[0]).split("_")
            hablante, sexo_raw, pais = _parse_tokens(tokens[1:] if len(tokens) > 1 else tokens)
            sexo = SEX_TOKENS.get(sexo_raw, "DESCONOCIDO")
            origen = pais_a_origen(pais)
            revisar = []
            if sexo == "DESCONOCIDO":
                revisar.append("sin_sexo")
            if origen == "DESCONOCIDO":
                revisar.append(f"pais_desconocido:{pais}")
            if pais in DUDOSOS:
                revisar.append("origen_dudoso")
            filas.append({
                "ruta": os.path.join("data", "raw", "Base_datos_palabras", carpeta, fn),
                "palabra": palabra, "hablante": hablante, "sexo": sexo,
                "pais": pais, "origen": origen, "revisar": ";".join(revisar),
            })
    salida = os.path.join(raiz, "data", "metadata.csv")
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ruta", "palabra", "hablante", "sexo",
                                          "pais", "origen", "revisar"])
        w.writeheader()
        w.writerows(filas)
    df = pd.DataFrame(filas)
    print(f"metadata: {len(df)} audios | sexo {dict(df.sexo.value_counts())} | "
          f"origen {dict(df.origen.value_counts())} | hablantes {df.hablante.nunique()}")
    return df


def preprocesar(raiz: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(raiz, "data", "metadata.csv"))
    df["ruta_abs"] = df["ruta"].apply(lambda r: os.path.join(raiz, r))
    dir_proc = os.path.join(raiz, "data", "processed")
    dir_res = os.path.join(raiz, "results")
    os.makedirs(dir_proc, exist_ok=True)
    os.makedirs(dir_res, exist_ok=True)
    pipe = build_preprocess_pipeline()

    dur_cruda, rutas_proc, dur_proc, fallos = [], [], [], []
    for ruta_abs, palabra, fn in zip(df["ruta_abs"], df["palabra"],
                                     df["ruta"].apply(os.path.basename)):
        try:
            dur_cruda.append(librosa.get_duration(path=ruta_abs))
        except Exception:
            dur_cruda.append(np.nan)
        try:
            (onda,) = pipe.fit_transform([ruta_abs])
            destino_dir = os.path.join(dir_proc, palabra)
            os.makedirs(destino_dir, exist_ok=True)
            destino = os.path.join(destino_dir, os.path.splitext(fn)[0] + ".wav")
            sf.write(destino, onda, SR)
            rutas_proc.append(os.path.relpath(destino, raiz))
            dur_proc.append(len(onda) / SR)
        except Exception as e:
            rutas_proc.append(""); dur_proc.append(np.nan)
            fallos.append((fn, str(e)))
    df["dur_cruda_s"] = dur_cruda
    df["ruta_proc"] = rutas_proc
    df["dur_proc_s"] = dur_proc
    df.to_csv(os.path.join(dir_proc, "metadata.csv"), index=False, encoding="utf-8")

    print(f"preprocesado: OK {(df['ruta_proc'] != '').sum()}/{len(df)} | fallos {len(fallos)} | "
          f"dur media {df['dur_proc_s'].mean():.2f}s")
    cortos = (df["dur_proc_s"] < DUR_MIN).sum()
    largos = (df["dur_proc_s"] > DUR_MAX).sum()
    if cortos or largos:
        print(f"  clips fuera de rango: {cortos} cortos (<{DUR_MIN}s), {largos} largos (>{DUR_MAX}s)")

    # EDA
    fig, ax = plt.subplots(2, 2, figsize=(13, 9))
    df["dur_proc_s"].plot.hist(bins=30, ax=ax[0, 0], color="#1f6f8b")
    ax[0, 0].set_title("Duración procesada (s)"); ax[0, 0].set_xlabel("segundos")
    df["sexo"].value_counts().plot.bar(ax=ax[0, 1], color="#3a7d44"); ax[0, 1].set_title("Clips por sexo")
    df["origen"].value_counts().plot.bar(ax=ax[1, 0], color="#9b59b6"); ax[1, 0].set_title("Clips por origen")
    df["palabra"].value_counts().sort_values().plot.barh(ax=ax[1, 1], color="#e67e22")
    ax[1, 1].set_title("Clips por palabra"); ax[1, 1].tick_params(axis="y", labelsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(dir_res, "eda_distribuciones.png"), dpi=110)
    return df