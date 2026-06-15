"""
Paso 10 — Entrena y PERSISTE los detectores desplegables de ORIGEN (T2) y SEXO (T3).

Backbone ECAPA-TDNN ligero (~20 MB) compartido. Para cada tarea:
  1) evalúa con CV por hablante (F1 macro + accuracy + latencia),
  2) entrena el modelo final sobre TODOS los datos disponibles y lo guarda en
     models/detector_<tarea>.joblib (cargable con pipeline.detectores).

REENTRENO CON DATOS DE USUARIOS: el detector de SEXO suma, además de los datos
base (adultos de Forvo), los audios que los usuarios aportan con consentimiento
(data/entrenamiento/etiquetas.csv -> palabra,edad,sexo,ruta,id_anon). A medida
que se acumulen audios infantiles reales, el detector se adapta a voz de 3-6
años (donde el sexo por voz es intrínsecamente difícil). Si hay suficientes
muestras infantiles se reporta además una CV SOLO con niños.

Ejecutar:  uv run python src/scripts/10_detectores.py
"""
from __future__ import annotations

import os
import sys
import time
import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# transformers antes que speechbrain (evita el conflicto del hook lazy de k2)
import torch  # noqa: F401
from transformers import AutoModel  # noqa: F401

import numpy as np
import pandas as pd
import librosa

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from pipeline.embeddings import cargar_embeddings_ecapa
from pipeline.clasificacion import cv_eval, logreg, proba_oof, barrido_confianza
from pipeline.detectores import entrenar_detector, get_ecapa
from sklearn.metrics import accuracy_score

META = os.path.join(RAIZ, "data", "processed", "metadata.csv")
DIR_ENTR = os.path.join(RAIZ, "data", "entrenamiento")
ET_ORIGEN3 = ["España", "Latam", "No nativo"]
ET_ORIGEN2 = ["España", "Latam"]
ET_SEXO = ["hombre", "mujer"]
UMBRALES = [0.50, 0.60, 0.70, 0.80, 0.90]


def _datos_usuarios():
    """Audios aportados por usuarios con etiqueta de sexo (data/entrenamiento)."""
    csv = os.path.join(DIR_ENTR, "etiquetas.csv")
    if not os.path.exists(csv):
        return None
    df = pd.read_csv(csv)
    df = df[df["sexo"].isin(ET_SEXO)].copy()
    df = df[df["ruta"].apply(lambda r: os.path.exists(os.path.join(DIR_ENTR, str(r))))]
    return df.reset_index(drop=True) if len(df) else None


def _cv(X, y, groups, etiquetas, n_splits, nombre):
    pred, f1m = cv_eval(X, y, groups, etiquetas, n_splits, logreg, nombre)
    acc = accuracy_score(y, pred)
    print(f"   accuracy: {acc:.3f}")
    return f1m, acc


def main():
    df = pd.read_csv(META)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    print(f"Datos base: {len(df)} clips | {df['hablante'].nunique()} hablantes")

    # Embeddings ECAPA del corpus base (cacheados en disco)
    t0 = time.perf_counter()
    Xb = cargar_embeddings_ecapa(df, RAIZ)
    t_emb = time.perf_counter() - t0
    print(f"ECAPA base: {Xb.shape} | {t_emb*1000:.0f} ms total "
          f"({t_emb*1000/len(df):.1f} ms/clip si recalcula)")

    # ===================== ORIGEN (T2) =====================
    print("\n" + "=" * 60 + "\nORIGEN (España / Latam / No nativo)\n" + "=" * 60)
    yo, go = df["origen"].values, df["hablante"].values
    m2 = df["origen"].isin(ET_ORIGEN2).values
    print(f"Distribución: {dict(df['origen'].value_counts())}")
    print("\n[CV España vs Latam]")
    _cv(Xb[m2], yo[m2], go[m2], ET_ORIGEN2, 5, "ECAPA -> origen 2 clases")
    print("\n[CV 3 clases]")
    f1_o3, acc_o3 = _cv(Xb, yo, go, ET_ORIGEN3, 4, "ECAPA -> origen 3 clases")
    pred, conf, _ = proba_oof(Xb[m2], yo[m2], go[m2], n_splits=5)
    print("\nConfianza (human-in-the-loop, España vs Latam):")
    barrido_confianza(pred, conf, yo[m2], UMBRALES)
    _m, ruta_o = entrenar_detector(
        "origen", Xb, yo, raiz=RAIZ, meta={
            "fecha": datetime.date.today().isoformat(), "n": int(len(df)),
            "clases": ET_ORIGEN3, "f1_macro_3clases": round(float(f1_o3), 3),
            "accuracy_3clases": round(float(acc_o3), 3),
            "nota": "Acento desde palabra suelta es difícil; 'No nativo' poco fiable "
                    "(confound 'piedra'). Usar con umbral + override de registro.",
        })
    print(f"\n>> Guardado: {os.path.relpath(ruta_o, RAIZ)}")

    # ===================== SEXO (T3) =====================
    print("\n" + "=" * 60 + "\nSEXO (hombre / mujer)\n" + "=" * 60)
    ys, gs = df["sexo"].values, df["hablante"].values
    print(f"Distribución base: {dict(df['sexo'].value_counts())}")
    print("\n[CV solo datos base (adultos)]")
    f1_s, acc_s = _cv(Xb, ys, gs, ET_SEXO, 5, "ECAPA -> sexo (base)")

    # --- sumar datos aportados por usuarios (reentreno) ---
    du = _datos_usuarios()
    Xs, ys_all, gs_all = Xb, ys, gs
    meta_sexo = {"fecha": datetime.date.today().isoformat(), "n_base": int(len(df)),
                 "n_usuarios": 0, "f1_macro_base": round(float(f1_s), 3),
                 "accuracy_base": round(float(acc_s), 3)}
    if du is not None:
        print(f"\nDatos de usuarios (consentimiento): {len(du)} clips | "
              f"edades {sorted(set(du['edad'].dropna()))}")
        ondas_u = [librosa.load(os.path.join(DIR_ENTR, r), sr=16000, mono=True)[0]
                   .astype(np.float32) for r in du["ruta"]]
        Xu = get_ecapa().embed_many(ondas_u)
        Xs = np.vstack([Xb, Xu])
        ys_all = np.concatenate([ys, du["sexo"].values])
        gs_all = np.concatenate([gs, ("u_" + du["id_anon"].astype(str)).values])
        meta_sexo["n_usuarios"] = int(len(du))
        print("\n[CV base + usuarios]")
        f1_c, acc_c = _cv(Xs, ys_all, gs_all, ET_SEXO, 5, "ECAPA -> sexo (base+usuarios)")
        meta_sexo.update(f1_macro=round(float(f1_c), 3), accuracy=round(float(acc_c), 3))
        # CV solo niños si hay suficientes
        ed = pd.to_numeric(du["edad"], errors="coerce")
        mn = (ed <= 6).values
        if mn.sum() >= 30 and du.loc[mn, "sexo"].nunique() == 2:
            print("\n[CV SOLO niños <=6 (dominio objetivo)]")
            gn = ("u_" + du.loc[mn, "id_anon"].astype(str)).values
            _cv(Xu[mn], du.loc[mn, "sexo"].values, gn, ET_SEXO,
                min(5, du.loc[mn, "sexo"].value_counts().min()), "ECAPA -> sexo (niños)")
        else:
            print(f"\n(Aún sin CV infantil: {int(mn.sum())} clips <=6 años; "
                  "se necesitan >=30 con ambos sexos. El modelo igualmente los incorpora.)")
    else:
        print("\n(Sin datos de usuarios todavía: data/entrenamiento/etiquetas.csv no existe. "
              "El detector se entrena con adultos; reejecuta este script cuando haya "
              "audios infantiles con consentimiento para adaptarlo a voz de 3-6 años.)")
        meta_sexo.update(f1_macro=round(float(f1_s), 3), accuracy=round(float(acc_s), 3))

    meta_sexo["nota"] = ("Sexo por voz es poco fiable en niños 3-6 (F0/formantes casi "
                         "idénticos pre-pubertad). Umbral alto + dato de registro como "
                         "respaldo. Reentrenar al acumular audio infantil real.")
    _m, ruta_s = entrenar_detector("sexo", Xs, ys_all, raiz=RAIZ, meta=meta_sexo)
    print(f"\n>> Guardado: {os.path.relpath(ruta_s, RAIZ)}")

    # ===================== latencia/peso de inferencia =====================
    print("\n" + "=" * 60 + "\nLATENCIA / PESO (inferencia desplegada)\n" + "=" * 60)
    o = librosa.load(os.path.join(RAIZ, df["ruta_proc"].iloc[0]), sr=16000, mono=True)[0]
    bk = get_ecapa()
    for _ in range(2):
        bk.embed_many([o])               # warm-up
    t = time.perf_counter()
    for _ in range(10):
        bk.embed_many([o])
    ms_emb = (time.perf_counter() - t) / 10 * 1000
    dev = getattr(bk, "dev", "cpu")
    tam_o = os.path.getsize(ruta_o) / 1024
    tam_s = os.path.getsize(ruta_s) / 1024
    print(f"  Backbone:            ECAPA-TDNN (~20 MB, {dev})")
    print(f"  Embedding:           {ms_emb:.1f} ms/clip (cuello de botella)")
    print(f"  Clasificador:        <0.1 ms/clip (LogReg)")
    print(f"  Modelo origen:       {tam_o:.0f} KB")
    print(f"  Modelo sexo:         {tam_s:.0f} KB")
    print("\nCargar en la app:  from pipeline.detectores import cargar_detector")
    print("                   cargar_detector('origen', RAIZ).predict(onda_o_ruta)")


if __name__ == "__main__":
    main()
