"""
Pipeline de preprocesado de audio reutilizable (scikit-learn).

Diseño: transformadores SIN estado (fit() no aprende nada) para que el MISMO
objeto trate de forma idéntica los datos de Forvo (test), OpenSLR (train) y
cualquier dato futuro. Encadenados con sklearn.Pipeline.

Entrada del pipeline:  lista de rutas a ficheros de audio (mp3/wav/...).
Salida:                lista de formas de onda (np.ndarray float32, mono, 16 kHz).

Uso:
    from preprocessing import build_preprocess_pipeline
    pipe = build_preprocess_pipeline()
    ondas = pipe.transform(["a.mp3", "b.mp3"])
"""
from __future__ import annotations

import numpy as np
import librosa
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline

SR = 16_000  # sample rate objetivo (estándar en modelos de voz)


class AudioLoader(BaseEstimator, TransformerMixin):
    """Carga audio desde ruta -> onda mono float32 remuestreada a `sr`."""

    def __init__(self, sr: int = SR, mono: bool = True):
        self.sr = sr
        self.mono = mono

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        ondas = []
        for ruta in X:
            onda, _ = librosa.load(ruta, sr=self.sr, mono=self.mono)
            ondas.append(onda.astype(np.float32))
        return ondas


class SilenceTrimmer(BaseEstimator, TransformerMixin):
    """Recorta silencio al inicio y final (umbral en dB bajo el pico)."""

    def __init__(self, top_db: int = 30):
        self.top_db = top_db

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        recortadas = []
        for onda in X:
            if onda.size == 0:
                recortadas.append(onda)
                continue
            onda_trim, _ = librosa.effects.trim(onda, top_db=self.top_db)
            # Si el recorte deja vacío (audio muy silencioso), conservamos el original
            recortadas.append(onda_trim if onda_trim.size > 0 else onda)
        return recortadas


class PeakNormalizer(BaseEstimator, TransformerMixin):
    """Normaliza la amplitud al pico objetivo (evita clips muy bajos/altos)."""

    def __init__(self, target_peak: float = 0.97):
        self.target_peak = target_peak

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        norm = []
        for onda in X:
            pico = float(np.max(np.abs(onda))) if onda.size else 0.0
            if pico > 0:
                norm.append((onda * (self.target_peak / pico)).astype(np.float32))
            else:
                norm.append(onda)
        return norm


def build_preprocess_pipeline(sr: int = SR, top_db: int = 30,
                              target_peak: float = 0.97) -> Pipeline:
    """Devuelve el pipeline de preprocesado estándar del proyecto."""
    return Pipeline([
        ("cargar", AudioLoader(sr=sr)),
        ("recortar_silencio", SilenceTrimmer(top_db=top_db)),
        ("normalizar", PeakNormalizer(target_peak=target_peak)),
    ])
