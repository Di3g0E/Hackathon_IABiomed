"""
Detección de actividad de voz (VAD) + puerta de calidad de captura.

Silero-VAD (red pequeña, CPU, MIT) en vez del umbral de energía: detecta DÓNDE hay voz humana
(no solo si hay sonido fuerte). Da: recorte preciso al habla, distinción silencio/voz-débil,
nº de tramos de voz (varios hablantes), y junto a SNR/clipping una PUERTA DE CALIDAD que explica
por qué repetir ("no se oyó", "demasiado ruido", "se oye a más de una persona", "saturado").

Si Silero no está disponible (sin red la 1ª vez, etc.) cae al detector de energía anterior, así
que el flujo NUNCA se rompe.
"""
from __future__ import annotations

import numpy as np

SR = 16_000
PICO_MIN = 0.02            # fallback de energía (igual que app.py)
DUR_VOZ_MIN = 0.12         # s mínimos de voz
SNR_MIN_DB = 8.0           # por debajo => demasiado ruido
CLIP_MAX = 0.02            # fracción de muestras saturadas por encima de la cual => saturado

_VAD = None                # (modelo, get_speech_timestamps) o False si no disponible


def _cargar():
    global _VAD
    if _VAD is None:
        try:
            import torch
            modelo, utils = torch.hub.load("snakers4/silero-vad", "silero_vad",
                                           trust_repo=True, onnx=False)
            _VAD = (modelo, utils[0])      # utils[0] = get_speech_timestamps
        except Exception:
            _VAD = False
    return _VAD


def disponible():
    return bool(_cargar())


def segmentos_voz(wav, sr=SR):
    """Lista de tramos de voz [{ini, fin}] en segundos. [] si no hay voz / sin Silero."""
    vad = _cargar()
    if not vad:
        return []
    import torch
    modelo, get_ts = vad
    y = torch.as_tensor(np.asarray(wav, dtype="float32"))
    ts = get_ts(y, modelo, sampling_rate=sr)
    return [{"ini": round(t["start"] / sr, 3), "fin": round(t["end"] / sr, 3)} for t in ts]


def recorta_voz(wav, sr=SR):
    """Recorta la onda al primer-último tramo de voz (Silero) o por energía si no está."""
    segs = segmentos_voz(wav, sr)
    if segs:
        a = int(segs[0]["ini"] * sr)
        b = int(segs[-1]["fin"] * sr)
        return np.asarray(wav, dtype="float32")[a:b]
    return np.asarray(wav, dtype="float32")


def _snr_db(wav, segs, sr):
    y = np.asarray(wav, dtype="float32")
    if not segs:
        return 0.0
    mask = np.zeros(len(y), dtype=bool)
    for s in segs:
        mask[int(s["ini"] * sr):int(s["fin"] * sr)] = True
    voz = y[mask]
    ruido = y[~mask]
    pv = float(np.mean(voz ** 2)) if voz.size else 0.0
    pn = float(np.mean(ruido ** 2)) if ruido.size else 0.0
    if pv <= 0:
        return 0.0
    if pn <= 1e-9:
        return 40.0
    return round(float(10.0 * np.log10(pv / pn)), 1)


def calidad(wav, sr=SR):
    """Puerta de calidad. Devuelve {hay_voz, n_segmentos, dur_voz, snr_db, clipping, motivo}.
    'motivo' (o None) es la causa para pedir repetir."""
    y = np.asarray(wav, dtype="float32")
    clip = float(np.mean(np.abs(y) > 0.99)) if y.size else 0.0
    segs = segmentos_voz(y, sr)
    if _cargar():
        dur_voz = round(sum(s["fin"] - s["ini"] for s in segs), 3)
        hay_voz = dur_voz >= DUR_VOZ_MIN
        n_seg = len(segs)
        snr = _snr_db(y, segs, sr)
    else:   # fallback de energía
        pico = float(np.max(np.abs(y))) if y.size else 0.0
        hay_voz = pico >= PICO_MIN and len(y) / sr >= DUR_VOZ_MIN
        dur_voz = round(len(y) / sr, 3) if hay_voz else 0.0
        n_seg = 1 if hay_voz else 0
        snr = None

    motivo = None
    if not hay_voz:
        motivo = "no se oyó la voz (¿micro lejos o no habló?)"
    elif clip > CLIP_MAX:
        motivo = "el sonido está saturado (baja el volumen o aleja el micro)"
    elif snr is not None and snr < SNR_MIN_DB:
        motivo = "hay demasiado ruido de fondo"
    elif n_seg >= 3:
        motivo = "se oye a más de una persona o varios intentos"
    return {"hay_voz": hay_voz, "n_segmentos": n_seg, "dur_voz": dur_voz,
            "snr_db": snr, "clipping": round(clip, 3), "motivo": motivo,
            "vad": "silero" if _cargar() else "energia"}
