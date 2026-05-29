"""
Fase 3c (T2) — Clasificador de origen CON CONFIANZA + override manual.

Diseño human-in-the-loop (alineado con el flujo de registro de la app):
  - El clasificador (XLS-R + LogReg) propone el origen con una CONFIANZA.
  - Si confianza >= umbral  -> autocompletar.
  - Si confianza <  umbral  -> "consultar al usuario" (lo indica manualmente).
  - El usuario siempre puede CORREGIR; como el origen es por hablante, una
    sola corrección se propaga a todas sus palabras (y activa la referencia
    fonémica específica del dialecto en T1).

Cachea los embeddings XLS-R para no recalcularlos en cada ejecución.

Ejecutar:  uv run python src/scripts/origen_confianza.py
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
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from pipeline.embeddings import XLSREmbedding
from pipeline.splits import stratified_group_kfold

META = os.path.join(RAIZ, "data", "processed", "metadata.csv")
DIR_RES = os.path.join(RAIZ, "results")
CACHE_NPY = os.path.join(RAIZ, "data", "processed", "emb_xlsr.npy")
CACHE_RUT = os.path.join(RAIZ, "data", "processed", "emb_xlsr_rutas.txt")
SR = 16_000
UMBRALES = [0.50, 0.60, 0.70, 0.80, 0.90]


def embeddings_cacheados(df):
    rutas = list(df["ruta_proc"])
    if os.path.exists(CACHE_NPY) and os.path.exists(CACHE_RUT):
        with open(CACHE_RUT, encoding="utf-8") as f:
            if f.read().splitlines() == rutas:
                print("Embeddings XLS-R cargados de caché.")
                return np.load(CACHE_NPY)
    print("Calculando embeddings XLS-R (se cachean para próximas ejecuciones)...")
    ondas = [librosa.load(os.path.join(RAIZ, r), sr=SR, mono=True)[0].astype(np.float32)
             for r in rutas]
    X = XLSREmbedding().embed_many(ondas)
    np.save(CACHE_NPY, X)
    with open(CACHE_RUT, "w", encoding="utf-8") as f:
        f.write("\n".join(rutas))
    return X


def proba_oof(X, y, groups, n_splits=4):
    """Probabilidades out-of-fold (CV por hablante) -> confianza honesta."""
    clases = np.array(sorted(set(y)))
    proba = np.zeros((len(y), len(clases)))
    for tr, te in stratified_group_kfold(n_splits).split(X, y, groups):
        clf = Pipeline([("esc", StandardScaler()),
                        ("clf", LogisticRegression(class_weight="balanced", max_iter=2000))])
        clf.fit(X[tr], y[tr])
        # alinear columnas a 'clases'
        idx = [list(clf.classes_).index(c) for c in clases]
        proba[te] = clf.predict_proba(X[te])[:, idx]
    pred = clases[proba.argmax(1)]
    conf = proba.max(1)
    return pred, conf, clases


def main():
    df = pd.read_csv(META)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    y = df["origen"].values
    groups = df["hablante"].values

    X = embeddings_cacheados(df)
    pred, conf, _ = proba_oof(X, y, groups)
    acc_global = (pred == y).mean()
    print(f"\nClasificador XLS-R + LogReg (3 clases) | accuracy global: {acc_global:.3f}")

    # ---- Curva cobertura / fiabilidad por umbral (nivel clip) ----
    print("\nUmbral de confianza -> qué pasa:")
    print(f"  {'umbral':>6} {'auto%':>7} {'acc(auto)':>10} {'consultar%':>11}")
    covs, accs = [], []
    for u in UMBRALES:
        m = conf >= u
        cov = m.mean()
        acc = (pred[m] == y[m]).mean() if m.any() else float("nan")
        covs.append(cov); accs.append(acc)
        print(f"  {u:>6.2f} {cov*100:>6.0f}% {acc:>9.3f} {(1-cov)*100:>10.0f}%")

    # ---- Nivel hablante (origen es por hablante) ----
    spk = {}
    for h, t, p, c in zip(groups, y, pred, conf):
        spk.setdefault(h, {"true": t, "preds": [], "confs": []})
        spk[h]["preds"].append(p); spk[h]["confs"].append(c)
    # decisión por hablante: predicción mayoritaria + confianza media
    auto_ok = auto_n = consultar = 0
    ejemplos_consultar = []
    for h, v in spk.items():
        from collections import Counter
        p = Counter(v["preds"]).most_common(1)[0][0]
        c = float(np.mean(v["confs"]))
        if c >= 0.70:
            auto_n += 1; auto_ok += int(p == v["true"])
        else:
            consultar += 1
            if len(ejemplos_consultar) < 5:
                ejemplos_consultar.append((h, p, round(c, 2), v["true"]))
    print(f"\nA nivel HABLANTE (umbral 0.70): {auto_n} autocompletados "
          f"(acc {auto_ok/auto_n:.2f} si auto), {consultar} a consultar al usuario.")
    print("Ejemplos marcados 'consultar al usuario' (baja confianza):")
    for h, p, c, t in ejemplos_consultar:
        print(f"    {h:18s} sugerido={p:9s} conf={c}  (real={t})")

    # ---- Demo de override manual + propagación ----
    print("\nDemo override manual: el usuario corrige un hablante -> se propaga a todas sus palabras")
    h_demo = ejemplos_consultar[0][0] if ejemplos_consultar else groups[0]
    overrides = {h_demo: "España"}  # ejemplo: el usuario indica el origen
    n_clips = int((groups == h_demo).sum())
    print(f"    override[{h_demo}] = 'España'  -> corrige sus {n_clips} clips y activa "
          f"referencia fonémica España (T1) para ese hablante.")

    # ---- Figura cobertura/fiabilidad ----
    os.makedirs(DIR_RES, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot([u for u in UMBRALES], [c * 100 for c in covs], "o-", label="Cobertura (auto%)")
    ax.plot([u for u in UMBRALES], [a * 100 for a in accs], "s-", label="Fiabilidad (acc auto%)")
    ax.set_xlabel("Umbral de confianza"); ax.set_ylabel("%"); ax.set_ylim(0, 100)
    ax.set_title("Origen: cobertura vs fiabilidad (human-in-the-loop)"); ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(os.path.join(DIR_RES, "origen_confianza.png"), dpi=120)
    print(f"\nFigura: results/origen_confianza.png")


if __name__ == "__main__":
    main()
