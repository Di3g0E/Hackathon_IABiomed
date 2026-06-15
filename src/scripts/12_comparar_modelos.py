"""
Comparación de TODOS los modelos del sistema (fork móvil): detectores de origen/sexo con
MFCC vs ECAPA, y el modelo de edad full fp32 vs int8. (El reconocedor de fonemas full vs
int8 se mide en 10_comparar_cuantizado.py.) Imprime un informe consolidado.

Ejecutar:  uv run python src/scripts/12_comparar_modelos.py
"""
from __future__ import annotations

import os
import sys

# fuerza backend cloud (modelo de edad full) ANTES de importar config
os.environ.setdefault("HABLI_BACKEND", "cloud")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)
RAIZ_DATOS = RAIZ if os.path.isdir(os.path.join(RAIZ, "data", "processed")) \
    else os.path.join(os.path.dirname(RAIZ), "IABiomed")

import glob
import time

import numpy as np

from pipeline import detectores as det
from pipeline import cuantizacion as cz


def _clips_edad(n=15):
    wavs = []
    for d in sorted(glob.glob(os.path.join(RAIZ_DATOS, "data", "processed", "*"))):
        w = sorted(glob.glob(os.path.join(d, "*.wav")))
        if w:
            wavs.append(w[0])
        if len(wavs) >= n:
            break
    return wavs


def comparar_detectores():
    filas = []
    for tarea in ("origen", "sexo"):
        for feats in ("mfcc", "ecapa"):
            m = det.entrenar(tarea, RAIZ_DATOS, raiz_modelos=RAIZ, features=feats)
            suf = "" if feats == "mfcc" else f"_{feats}"
            kb = os.path.getsize(os.path.join(RAIZ, "models", f"det_{tarea}{suf}.npz")) / 1024
            filas.append((tarea, feats, m["accuracy_cv"], m["f1_macro_cv"],
                          m["dim"], m["lat_features_ms"], kb))
    return filas


def comparar_edad():
    import copy

    import librosa
    import torch
    from app import herramientas
    proc, full = herramientas._get_edad_model()        # full fp32 (backend cloud)
    int8 = cz.cuantizar_modelo(copy.deepcopy(full))
    mb_full, mb_int8 = cz.tamano_mb(full), cz.tamano_mb(int8)

    def pred(model, sig):
        iv = torch.from_numpy(proc(sig, sampling_rate=16000)["input_values"][0]).unsqueeze(0)
        with torch.no_grad():
            return float(model(iv).item()) * 100.0

    difs, lf, le = [], [], []
    for w in _clips_edad(15):
        sig, _ = librosa.load(w, sr=16000, mono=True)
        t = time.perf_counter(); a_f = pred(full, sig); lf.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter(); a_e = pred(int8, sig); le.append((time.perf_counter() - t) * 1000)
        difs.append(abs(a_f - a_e))
    return {"mb_full": mb_full, "mb_int8": mb_int8,
            "lat_full": sum(lf) / len(lf), "lat_int8": sum(le) / len(le),
            "dif_media_anios": sum(difs) / len(difs), "dif_max_anios": max(difs)}


def main():
    print(f"Datos: {os.path.join(RAIZ_DATOS, 'data', 'processed')}\n")

    print("### DETECTORES origen/sexo — MFCC vs ECAPA ###", flush=True)
    det_filas = comparar_detectores()
    print(f"\n{'tarea':8s}{'features':10s}{'accuracy':>10s}{'F1 macro':>10s}{'dim':>6s}"
          f"{'lat.feat':>10s}{'peso':>9s}")
    for (tarea, feats, acc, f1, dim, lat, kb) in det_filas:
        print(f"{tarea:8s}{feats:10s}{acc:>10.3f}{f1:>10.3f}{dim:>6d}{lat:>8.1f}ms{kb:>7.1f}KB")

    print("\n### MODELO DE EDAD — full fp32 vs int8 ###", flush=True)
    e = comparar_edad()
    print(f"{'sistema':12s}{'peso MB':>10s}{'latencia':>12s}")
    print(f"{'FULL fp32':12s}{e['mb_full']:>10.1f}{e['lat_full']:>9.0f} ms")
    print(f"{'INT8':12s}{e['mb_int8']:>10.1f}{e['lat_int8']:>9.0f} ms")
    print(f"Acuerdo full↔int8: diferencia media {e['dif_media_anios']:.2f} años "
          f"(máx {e['dif_max_anios']:.2f}); peso −{100*(1-e['mb_int8']/e['mb_full']):.0f}%, "
          f"velocidad {e['lat_full']/e['lat_int8']:.2f}×.")


if __name__ == "__main__":
    main()