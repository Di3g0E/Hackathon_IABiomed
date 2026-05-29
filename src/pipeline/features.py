"""
Extractores de características de audio como transformadores scikit-learn.

Entrada: lista de formas de onda (salida del pipeline de preprocesado).
Salida:  matriz (n_muestras, n_features) lista para un clasificador.

PitchFeatures se centra en la F0 (frecuencia fundamental ~ tono de voz), que
separa muy bien hombre/mujer en adultos, más unas pocas características
espectrales/energéticas baratas. Pensado para ser LIGERO (criterio del reto).
"""
from __future__ import annotations

import numpy as np
import librosa
from sklearn.base import BaseEstimator, TransformerMixin

SR = 16_000


class PitchFeatures(BaseEstimator, TransformerMixin):
    """Estadísticos de F0 + características espectrales simples por clip."""

    NOMBRES = [
        "f0_media", "f0_mediana", "f0_std", "f0_min", "f0_max",
        "frac_sonora", "centroide_espectral", "rms",
    ]

    def __init__(self, sr: int = SR, fmin: float = 65.0, fmax: float = 400.0):
        self.sr = sr
        self.fmin = fmin   # límite inferior F0 (voz grave masculina)
        self.fmax = fmax   # límite superior F0 (voz aguda femenina/infantil)

    def fit(self, X, y=None):
        return self

    def _features_una(self, onda: np.ndarray) -> list[float]:
        if onda is None or onda.size < self.sr // 20:  # < ~50 ms
            return [0.0] * len(self.NOMBRES)
        # F0 con pYIN (probabilístico, robusto)
        f0, voiced, _ = librosa.pyin(onda, sr=self.sr, fmin=self.fmin, fmax=self.fmax)
        f0v = f0[~np.isnan(f0)]
        if f0v.size == 0:
            f0_stats = [0.0, 0.0, 0.0, 0.0, 0.0]
            frac = 0.0
        else:
            f0_stats = [float(np.mean(f0v)), float(np.median(f0v)),
                        float(np.std(f0v)), float(np.min(f0v)), float(np.max(f0v))]
            frac = float(np.mean(voiced)) if voiced is not None else 0.0
        centroide = float(np.mean(librosa.feature.spectral_centroid(y=onda, sr=self.sr)))
        rms = float(np.mean(librosa.feature.rms(y=onda)))
        return f0_stats + [frac, centroide, rms]

    def transform(self, X):
        return np.array([self._features_una(o) for o in X], dtype=np.float64)

    def get_feature_names_out(self, input_features=None):
        return np.array(self.NOMBRES)


class MFCCFeatures(BaseEstimator, TransformerMixin):
    """MFCC (timbre/articulación) resumidos por media y desviación.

    Los MFCC capturan la "huella" espectral del tracto vocal -> útiles para
    acento/origen. Por clip se resume cada coeficiente con media y std
    (2*n_mfcc características), barato y robusto en clips cortos.
    """

    def __init__(self, sr: int = SR, n_mfcc: int = 13):
        self.sr = sr
        self.n_mfcc = n_mfcc

    def fit(self, X, y=None):
        return self

    def _features_una(self, onda: np.ndarray) -> np.ndarray:
        if onda is None or onda.size < self.sr // 20:
            return np.zeros(2 * self.n_mfcc, dtype=np.float64)
        mfcc = librosa.feature.mfcc(y=onda, sr=self.sr, n_mfcc=self.n_mfcc)
        return np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1)])

    def transform(self, X):
        return np.array([self._features_una(o) for o in X], dtype=np.float64)

    def get_feature_names_out(self, input_features=None):
        return np.array([f"mfcc{i}_media" for i in range(self.n_mfcc)] +
                        [f"mfcc{i}_std" for i in range(self.n_mfcc)])
