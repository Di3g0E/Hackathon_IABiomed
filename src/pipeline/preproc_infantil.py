"""
Adaptación a voz infantil en TEST-TIME (sin tocar el modelo ni reentrenar).

La voz infantil tiene F0 y formantes más altos que la adulta con la que se entrenó el modelo
(domain gap documentado: PER niños 0.29 vs adultos 0.17). Truco clásico de ASR infantil: BAJAR
el tono del audio del niño unos semitonos para acercarlo al rango adulto antes de reconocer.

Es REVERSIBLE y conmutable (config.MODO_INFANTIL): no modifica el camino adulto. El fine-tuning
LoRA+VTLP (scripts/9_finetune_lora.py) es la versión "definitiva", aquí dejada como scaffold.
"""
from __future__ import annotations

SR = 16_000


def adapta_infantil(wav, semitonos=4.0):
    """Baja el tono `semitonos` (acerca la voz infantil al rango adulto). Si librosa falla,
    devuelve la onda original (no rompe el flujo)."""
    try:
        import librosa
        import numpy as np
        y = np.asarray(wav, dtype="float32")
        if y.size == 0:
            return wav
        return librosa.effects.pitch_shift(y, sr=SR, n_steps=-abs(float(semitonos)))
    except Exception:
        return wav
