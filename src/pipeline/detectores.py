"""
Detectores DESPLEGABLES de ORIGEN (T2) y SEXO (T3) para inferencia en la app.

A diferencia de los scripts de evaluación (2_sexo, 3_origen, que solo hacían
validación cruzada e imprimían F1), aquí cada detector:

  - usa UN backbone ECAPA-TDNN ligero (~20 MB), cargado UNA vez y COMPARTIDO entre
    ambos detectores (get_ecapa());
  - lleva un clasificador ligero (StandardScaler + LogReg) ya ENTRENADO y
    persistido en disco con joblib (models/detector_<tarea>.joblib, ~KB);
  - expone .predict(audio) -> dict {etiqueta, confianza, probas, decision}
    con HUMAN-IN-THE-LOOP: si la confianza < umbral -> decision='consultar'
    (se pregunta al usuario / se usa el dato de registro), igual que el resto del
    proyecto (origen_confianza, sexo v2).

Peso/latencia: el coste dominante es el backbone (ECAPA, ~20 MB, rápido incluso
en CPU). El clasificador es de KB y microsegundos. Elegido frente a XLS-R-300m
(~1.2 GB) para minimizar peso/VRAM (criterio del reto + 4 GB de la RTX 3050).

NOTA CLÍNICA (sexo en niños 3-6): antes de la pubertad la F0 (tono) y los
formantes de niños y niñas son casi idénticos -> el sexo por voz es
intrínsecamente poco fiable en esa franja (techo ~70-80 % en la literatura, vs
~98 % en adultos). El detector se entrena con los datos disponibles y está
pensado para REENTRENARSE con los audios que aporten los usuarios
(data/entrenamiento, vía consentimiento) para adaptarse a voz infantil real.
Mientras tanto, el umbral de confianza deriva los casos dudosos al dato de
registro en vez de arriesgar un falso positivo.
"""
from __future__ import annotations

import os
import threading

import numpy as np
import joblib


# ----------------------------------------------------------------- backbone único
_ECAPA = None
_ECAPA_LOCK = threading.Lock()


def get_ecapa():
    """Backbone ECAPA-TDNN como singleton perezoso (compartido por origen y sexo)."""
    global _ECAPA
    if _ECAPA is None:
        with _ECAPA_LOCK:
            if _ECAPA is None:
                # Fuerza la carga de librosa.core.audio ANTES que SpeechBrain: si se
                # importa después, su lazy-loader (inspect.stack) choca con el módulo
                # perezoso k2 de SpeechBrain y revienta al cargar audio.
                import librosa.core.audio  # noqa: F401
                from pipeline.embeddings import EcapaEmbedding
                _ECAPA = EcapaEmbedding()
    return _ECAPA


def _carga_onda(x, sr=16000):
    if isinstance(x, str):
        import librosa
        return librosa.load(x, sr=sr, mono=True)[0].astype(np.float32)
    return np.asarray(x, dtype=np.float32)


def _a_lista(audio, sr=16000):
    """Normaliza la entrada a (lista_de_ondas, es_unico).

    Acepta: ruta (str), una onda (np.ndarray 1D), o una lista de rutas/ondas.
    """
    es_unico = isinstance(audio, str) or (isinstance(audio, np.ndarray) and audio.ndim == 1)
    items = [audio] if es_unico else list(audio)
    return [_carga_onda(x, sr) for x in items], es_unico


# ------------------------------------------------------------------- detector base
class Detector:
    """Clasificador ligero sobre embeddings ECAPA, con confianza y human-in-the-loop."""

    TAREA = "base"
    UMBRAL_DEF = 0.60

    def __init__(self, modelo=None, raiz=None, backbone=None, umbral=None):
        if modelo is None:
            modelo = self.ruta_modelo(raiz)
        if isinstance(modelo, str):
            if not os.path.exists(modelo):
                raise FileNotFoundError(
                    f"No existe el modelo entrenado: {modelo}. "
                    f"Entrénalo con `uv run python src/scripts/10_detectores.py`.")
            modelo = joblib.load(modelo)
        self.pipe = modelo["pipe"]
        self.clases = list(modelo.get("clases", getattr(self.pipe, "classes_", [])))
        self.umbral = float(umbral if umbral is not None else modelo.get("umbral", self.UMBRAL_DEF))
        self.backbone = modelo.get("backbone", "ECAPA-TDNN")
        self.meta = modelo.get("meta", {})
        self._bk = backbone

    @classmethod
    def ruta_modelo(cls, raiz=None):
        raiz = raiz or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(raiz, "models", f"detector_{cls.TAREA}.joblib")

    def _embed(self, ondas):
        bk = self._bk or get_ecapa()
        return bk.embed_many(ondas)

    def _decide(self, X, umbral):
        u = self.umbral if umbral is None else float(umbral)
        proba = self.pipe.predict_proba(X)
        clases = list(self.pipe.classes_)
        out = []
        for p in proba:
            i = int(np.argmax(p))
            conf = float(p[i])
            out.append({
                "tarea": self.TAREA,
                "etiqueta": clases[i],
                "confianza": round(conf, 3),
                "probas": {c: round(float(v), 3) for c, v in zip(clases, p)},
                "decision": "auto" if conf >= u else "consultar",
                "umbral": u,
            })
        return out

    def predict(self, audio, umbral=None):
        """audio: ruta | onda (np 1D) | lista de rutas/ondas.
        Devuelve un dict (entrada única) o lista de dicts (lote)."""
        ondas, es_unico = _a_lista(audio)
        res = self._decide(self._embed(ondas), umbral)
        return res[0] if es_unico else res

    def predict_desde_embeddings(self, X, umbral=None):
        """Para evaluación/lotes cuando ya tienes los embeddings ECAPA calculados."""
        return self._decide(np.asarray(X, dtype=np.float64), umbral)


class DetectorOrigen(Detector):
    TAREA = "origen"
    UMBRAL_DEF = 0.70   # acento desde palabra suelta es difícil -> umbral alto


class DetectorSexo(Detector):
    TAREA = "sexo"
    UMBRAL_DEF = 0.80   # conservador en niños (sexo por voz poco fiable pre-pubertad)


# ------------------------------------------------------------------- API utilitaria
def cargar_detector(tarea, raiz=None, backbone=None, umbral=None):
    cls = {"origen": DetectorOrigen, "sexo": DetectorSexo}[tarea]
    return cls(raiz=raiz, backbone=backbone, umbral=umbral)


def entrenar_detector(tarea, X, y, raiz=None, umbral=None, meta=None, ruta=None):
    """Entrena (StandardScaler+LogReg balanceado) sobre embeddings ECAPA y lo persiste.
    Devuelve (modelo_dict, ruta)."""
    from pipeline.clasificacion import logreg
    cls = {"origen": DetectorOrigen, "sexo": DetectorSexo}[tarea]
    pipe = logreg()
    pipe.fit(np.asarray(X, dtype=np.float64), np.asarray(y))
    modelo = {
        "pipe": pipe,
        "clases": list(pipe.classes_),
        "umbral": float(umbral if umbral is not None else cls.UMBRAL_DEF),
        "backbone": "ECAPA-TDNN",
        "meta": meta or {},
    }
    ruta = ruta or cls.ruta_modelo(raiz)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    joblib.dump(modelo, ruta)
    return modelo, ruta
