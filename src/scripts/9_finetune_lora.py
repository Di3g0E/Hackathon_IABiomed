"""
SCAFFOLD — Fine-tuning LoRA del reconocedor para voz infantil (NO se ejecuta por defecto).

Es la versión "definitiva" de la adaptación infantil (la ligera, ya operativa, es el pitch-shift
de pipeline/preproc_infantil.py). Aquí queda LISTO el esqueleto para cuando haya datos:

  1) Datos: descargar OpenSLR Latam (adulto, gratis) y/o grabaciones reales de las 32 palabras
     (Clínica Amado). 2) Aumentado VTLP (Vocal Tract Length Perturbation) para SIMULAR voz infantil
     a partir de adulto. 3) LoRA (peft) sobre wav2vec2-xlsr-espeak con el EXTRACTOR CONGELADO
     (cabe en 4 GB de VRAM). 4) Guardar el adapter y apuntarlo con config.LORA_ADAPTER -> se cargaría
     como 3ª estrategia del reconocedor, comparable en el A/B (scripts/8) sin perder lo actual.

Requisitos cuando se vaya a ejecutar:  uv add peft datasets soundfile
Lanzar (consciente):  uv run python src/scripts/9_finetune_lora.py --ejecutar --datos <dir>

Mientras tanto, ejecutarlo sin --ejecutar solo imprime el plan y comprueba dependencias.
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

W2V_ID = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"
DIR_ADAPTER = os.path.join(RAIZ, "data", "lora_infantil")


def vtlp(wav, sr=16000, alpha=None):
    """Vocal Tract Length Perturbation: deforma el eje de frecuencias para simular un tracto
    vocal más corto (voz infantil) a partir de voz adulta. alpha~[1.1,1.3] = más infantil."""
    import numpy as np
    if alpha is None:
        alpha = 1.2
    n_fft = 1024
    import librosa
    S = librosa.stft(np.asarray(wav, dtype="float32"), n_fft=n_fft)
    freqs = np.linspace(0, 1, S.shape[0])
    warped = np.minimum(freqs * alpha, 1.0)
    S2 = np.zeros_like(S)
    for i, f in enumerate(warped):
        j = int(f * (S.shape[0] - 1))
        S2[j] += S[i]
    return librosa.istft(S2, length=len(wav))


def plan():
    print("PLAN del fine-tuning LoRA infantil (scaffold):")
    print("  1. Datos    -> OpenSLR Latam + (futuro) 32 palabras reales de la Clínica Amado")
    print("  2. Aumentado-> VTLP (alpha 1.1-1.3) sobre adulto para simular voz infantil")
    print("  3. Modelo   -> %s con extractor CONGELADO + LoRA (peft) en las capas de atención" % W2V_ID)
    print("  4. Salida   -> adapter en %s ; usar con LORA_ADAPTER=<ruta>" % os.path.relpath(DIR_ADAPTER, RAIZ))
    falta = []
    for m in ("peft", "datasets"):
        try:
            __import__(m)
        except Exception:
            falta.append(m)
    print("  Dependencias:", "OK" if not falta else f"faltan -> uv add {' '.join(falta)}")
    print("  Para entrenar de verdad:  uv run python src/scripts/9_finetune_lora.py --ejecutar --datos <dir>")


def entrenar(dir_datos):
    """Esqueleto del entrenamiento real. Requiere peft/datasets y datos preparados."""
    from peft import LoraConfig, get_peft_model     # noqa: F401  (import tardío, opcional)
    from transformers import AutoModelForCTC, AutoFeatureExtractor, TrainingArguments  # noqa: F401
    raise NotImplementedError(
        "Esqueleto: implementar el bucle de entrenamiento cuando haya datos en %s. "
        "Pasos: cargar wav+transcripción IPA, aplir VTLP como augmentación, congelar el "
        "extractor, envolver el modelo con LoRA (target q_proj/v_proj), Trainer CTC, guardar "
        "el adapter en %s." % (dir_datos, DIR_ADAPTER))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ejecutar", action="store_true", help="lanza el entrenamiento real (consciente)")
    ap.add_argument("--datos", default=None, help="carpeta con los datos preparados")
    args = ap.parse_args()
    if not args.ejecutar:
        plan()
        return
    if not args.datos:
        print("Falta --datos <dir>. Aborta."); return
    entrenar(args.datos)


if __name__ == "__main__":
    main()
