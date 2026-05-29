"""
Fase 3 (T2) — Clasificación de ORIGEN del hablante.

Características ligeras: MFCC (media+std) + pitch. Clasificador LogReg/SVM con
validación cruzada POR HABLANTE (sin fuga). Se reportan dos escenarios:
  A) 3 clases: España / Latam / No nativo  (No nativo es minoritaria y con
     confound de palabra -> se interpreta con cautela)
  B) 2 clases: España vs Latam  (evaluación limpia, clases repartidas)

Ejecutar:  uv run python src/scripts/clasif_origen.py
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
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay, f1_score

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from pipeline.features import MFCCFeatures, PitchFeatures, SR
from pipeline.splits import stratified_group_kfold

META = os.path.join(RAIZ, "data", "processed", "metadata.csv")
DIR_RES = os.path.join(RAIZ, "results")


def cv_eval(X, y, groups, etiquetas, n_splits, clf_factory, nombre):
    cv = stratified_group_kfold(n_splits)
    y_pred = np.empty_like(y, dtype=object)
    t_tr = t_te = 0.0
    for tr, te in cv.split(X, y, groups):
        clf = clf_factory()
        a = time.perf_counter(); clf.fit(X[tr], y[tr]); t_tr += time.perf_counter() - a
        a = time.perf_counter(); y_pred[te] = clf.predict(X[te]); t_te += time.perf_counter() - a
    print(f"\n--- {nombre} ---")
    print(classification_report(y, y_pred, labels=etiquetas, digits=3, zero_division=0))
    f1m = f1_score(y, y_pred, labels=etiquetas, average="macro")
    print(f"F1 MACRO: {f1m:.3f} | train {t_tr*1000:.0f} ms | infer {t_te*1000:.0f} ms")
    return y_pred, f1m


def guarda_confusion(y, y_pred, etiquetas, titulo, fichero):
    cm = confusion_matrix(y, y_pred, labels=etiquetas)
    fig, ax = plt.subplots(figsize=(4.8, 4.2))
    ConfusionMatrixDisplay(cm, display_labels=etiquetas).plot(ax=ax, cmap="Purples", colorbar=False)
    ax.set_title(titulo)
    fig.tight_layout()
    fig.savefig(os.path.join(DIR_RES, fichero), dpi=120)


def logreg():
    return Pipeline([("esc", StandardScaler()),
                     ("clf", LogisticRegression(class_weight="balanced", max_iter=2000))])


def svm():
    return Pipeline([("esc", StandardScaler()),
                     ("clf", SVC(class_weight="balanced", kernel="rbf", C=10))])


def main():
    df = pd.read_csv(META)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    df["abs"] = df["ruta_proc"].apply(lambda r: os.path.join(RAIZ, r))
    print(f"Muestras: {len(df)} | origen: {dict(df['origen'].value_counts())} "
          f"| hablantes: {df['hablante'].nunique()}")

    print("\nExtrayendo MFCC + pitch...")
    t0 = time.perf_counter()
    ondas = [librosa.load(p, sr=SR, mono=True)[0].astype(np.float32) for p in df["abs"]]
    X = np.hstack([MFCCFeatures(sr=SR).fit_transform(ondas),
                   PitchFeatures(sr=SR).fit_transform(ondas)])
    print(f"Características: {X.shape} en {time.perf_counter()-t0:.1f}s")

    os.makedirs(DIR_RES, exist_ok=True)
    groups = df["hablante"].values

    # ===== Escenario A: 3 clases =====
    print("\n===== A) 3 clases (España / Latam / No nativo) =====")
    et3 = ["España", "Latam", "No nativo"]
    yp, _ = cv_eval(X, df["origen"].values, groups, et3, 4, logreg, "LogReg")
    guarda_confusion(df["origen"].values, yp, et3, "Origen 3 clases (LogReg)", "origen_3clases.png")

    # ===== Escenario B: España vs Latam =====
    print("\n===== B) 2 clases (España vs Latam, evaluación limpia) =====")
    m = df["origen"].isin(["España", "Latam"]).values
    Xb, yb, gb = X[m], df["origen"].values[m], groups[m]
    et2 = ["España", "Latam"]
    yp_lr, f1_lr = cv_eval(Xb, yb, gb, et2, 5, logreg, "LogReg")
    yp_sv, f1_sv = cv_eval(Xb, yb, gb, et2, 5, svm, "SVM rbf")
    mejor_yp = yp_lr if f1_lr >= f1_sv else yp_sv
    guarda_confusion(yb, mejor_yp, et2, "España vs Latam (mejor)", "origen_2clases.png")

    print("\nFiguras: results/origen_3clases.png, results/origen_2clases.png")


if __name__ == "__main__":
    main()
