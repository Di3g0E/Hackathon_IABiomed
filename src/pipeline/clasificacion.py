"""
Utilidades de clasificación con validación POR HABLANTE (compartidas por T2/T3).

Incluye factorías de modelos ligeros, evaluación con CV por hablante, probabilidades
out-of-fold (para confianza), matriz de confusión, voto por hablante y barrido de
umbral de confianza (human-in-the-loop).
"""
from __future__ import annotations

import time
from collections import Counter

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (classification_report, confusion_matrix,
                             ConfusionMatrixDisplay, f1_score)

from pipeline.splits import stratified_group_kfold


def logreg():
    return Pipeline([("esc", StandardScaler()),
                     ("clf", LogisticRegression(class_weight="balanced", max_iter=2000))])


def svm():
    return Pipeline([("esc", StandardScaler()),
                     ("clf", SVC(class_weight="balanced", kernel="rbf", C=10))])


def cv_eval(X, y, groups, etiquetas, n_splits, clf_factory, nombre):
    """CV por hablante; imprime informe y devuelve (y_pred, f1_macro)."""
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


def proba_oof(X, y, groups, n_splits=4):
    """Probabilidades out-of-fold -> (pred, confianza=max proba, clases)."""
    clases = np.array(sorted(set(y)))
    proba = np.zeros((len(y), len(clases)))
    for tr, te in stratified_group_kfold(n_splits).split(X, y, groups):
        clf = logreg()
        clf.fit(X[tr], y[tr])
        idx = [list(clf.classes_).index(c) for c in clases]
        proba[te] = clf.predict_proba(X[te])[:, idx]
    return clases[proba.argmax(1)], proba.max(1), clases


def guarda_confusion(y, y_pred, etiquetas, titulo, ruta_png, cmap="Blues"):
    cm = confusion_matrix(y, y_pred, labels=etiquetas)
    fig, ax = plt.subplots(figsize=(4.8, 4.2))
    ConfusionMatrixDisplay(cm, display_labels=etiquetas).plot(ax=ax, cmap=cmap, colorbar=False)
    ax.set_title(titulo); fig.tight_layout(); fig.savefig(ruta_png, dpi=120)
    plt.close(fig)


def voto_por_hablante(hablantes, y_true, y_pred):
    """Agrega por mayoría las predicciones de cada hablante."""
    sp = {}
    for h, t, p in zip(hablantes, y_true, y_pred):
        sp.setdefault(h, {"true": t, "preds": []})
        sp[h]["preds"].append(p)
    yt = np.array([v["true"] for v in sp.values()])
    yp = np.array([Counter(v["preds"]).most_common(1)[0][0] for v in sp.values()])
    return yt, yp


def barrido_confianza(pred, conf, y, umbrales=(0.5, 0.6, 0.7, 0.8, 0.9)):
    """Tabla cobertura/fiabilidad por umbral (human-in-the-loop)."""
    print(f"  {'umbral':>6} {'auto%':>7} {'acc(auto)':>10} {'consultar%':>11}")
    covs, accs = [], []
    for u in umbrales:
        m = conf >= u
        cov = float(m.mean())
        acc = float((pred[m] == y[m]).mean()) if m.any() else float("nan")
        covs.append(cov); accs.append(acc)
        print(f"  {u:>6.2f} {cov*100:>6.0f}% {acc:>9.3f} {(1-cov)*100:>10.0f}%")
    return covs, accs


def figura_confianza(umbrales, covs, accs, titulo, ruta_png):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(umbrales, [c*100 for c in covs], "o-", label="Cobertura (auto%)")
    ax.plot(umbrales, [a*100 for a in accs], "s-", label="Fiabilidad (acc auto%)")
    ax.set_xlabel("Umbral de confianza"); ax.set_ylabel("%"); ax.set_ylim(0, 105)
    ax.set_title(titulo); ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(ruta_png, dpi=120); plt.close(fig)