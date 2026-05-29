"""
Splits POR HABLANTE para evitar fuga de hablante.

El mismo hablante aparece en varias palabras; si un hablante cae a la vez en
train y test, las métricas se inflan. Estas utilidades agrupan por `hablante`.
"""
from __future__ import annotations

from sklearn.model_selection import GroupKFold, StratifiedGroupKFold


def group_kfold(n_splits: int = 5):
    """K-fold que mantiene cada hablante íntegro en un único fold."""
    return GroupKFold(n_splits=n_splits)


def stratified_group_kfold(n_splits: int = 5):
    """Como group_kfold pero intentando conservar la proporción de clases.

    Útil con el desbalance de sexo (78/22) y origen.
    """
    return StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=42)


def iter_speaker_folds(df, y_col, n_splits: int = 5, stratify: bool = True):
    """Itera (train_idx, test_idx) usando `df['hablante']` como grupo.

    Parámetros
    ----------
    df : DataFrame con columnas 'hablante' y la de etiqueta `y_col`.
    """
    groups = df["hablante"].values
    y = df[y_col].values
    cv = stratified_group_kfold(n_splits) if stratify else group_kfold(n_splits)
    X_dummy = range(len(df))
    yield from cv.split(X_dummy, y, groups)
