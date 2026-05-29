"""
Validación con VOZ INFANTIL real (prueba de domain gap).

1) Detector de "niño" (audeering) -> confirma que son voces infantiles (gating).
2) Reconocedor wav2vec2 (el de T1) + G2P español sobre la transcripción ->
   PER en habla infantil espontánea, para cuantificar el domain gap frente al
   PER 0.17 medido en adultos (OJO: adultos = palabra aislada; niños = habla
   continua, así que la comparación es indicativa, no estricta).

Ejecutar:  uv run python src/scripts/validar_infantil.py
"""
from __future__ import annotations

import os
import sys
import glob

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd
import librosa
import torch
import torch.nn as nn

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from scripts.reconocer_fonemas import W2V, normaliza_sec
from pipeline.alineamiento import alinear, agregar
from pipeline.g2p_es import texto_a_fonemas

DIR_CHILD = os.path.join(RAIZ, "data", "raw", "nexdata_child")
DIR_RES = os.path.join(RAIZ, "results")
AGE_ID = "audeering/wav2vec2-large-robust-24-ft-age-gender"
PER_ADULTOS = 0.17


# ---- Detector edad/sexo audeering (cabeza personalizada del model card) ----
class _Head(nn.Module):
    def __init__(self, config, n):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.final_dropout)
        self.out_proj = nn.Linear(config.hidden_size, n)

    def forward(self, x):
        x = self.dropout(x); x = torch.tanh(self.dense(x)); x = self.dropout(x)
        return self.out_proj(x)


def carga_age_gender():
    from transformers import Wav2Vec2Processor
    from transformers.models.wav2vec2.modeling_wav2vec2 import Wav2Vec2Model, Wav2Vec2PreTrainedModel

    class AgeGender(Wav2Vec2PreTrainedModel):
        _tied_weights_keys = []
        all_tied_weights_keys = {}

        def __init__(self, config):
            super().__init__(config)
            self.wav2vec2 = Wav2Vec2Model(config)
            self.age = _Head(config, 1)
            self.gender = _Head(config, 3)  # [female, male, child]
            self.init_weights()

        def forward(self, x):
            h = torch.mean(self.wav2vec2(x)[0], dim=1)
            return self.age(h), torch.softmax(self.gender(h), dim=1)

    proc = Wav2Vec2Processor.from_pretrained(AGE_ID)
    model = AgeGender.from_pretrained(AGE_ID).eval()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    return proc, model.to(dev), dev


def main():
    wavs = sorted(glob.glob(os.path.join(DIR_CHILD, "**", "*.wav"), recursive=True))
    if not wavs:
        print("No hay audios infantiles. Ejecuta antes descargar_infantil.py")
        return
    print(f"Clips infantiles: {len(wavs)}")

    # 1) Detector de niño (opcional; los clips son infantiles por construcción)
    print("\nCargando detector edad/sexo (audeering)...")
    try:
        proc, agem, dev = carga_age_gender()
        edades, p_child = [], []
        for w in wavs:
            sig, _ = librosa.load(w, sr=16000)
            iv = torch.from_numpy(proc(sig, sampling_rate=16000)["input_values"][0]).unsqueeze(0).to(dev)
            with torch.no_grad():
                age, gen = agem(iv)
            edades.append(float(age.item()) * 100)
            p_child.append(float(gen[0, 2].item()))
        print(f"  Edad estimada media: {np.mean(edades):.1f} años")
        print(f"  P(niño) media: {np.mean(p_child):.2f} | clips con P(niño)>0.5: "
              f"{sum(p > 0.5 for p in p_child)}/{len(wavs)}")
    except Exception as e:
        print(f"  [detector no cargado: {type(e).__name__}] -> se omite "
              f"(los clips ya son infantiles por construcción del dataset).")

    # 2) Reconocedor de fonemas + PER contra G2P de la transcripción
    print("\nCargando reconocedor wav2vec2 (T1)...")
    w2v = W2V()
    resultados, filas = [], []
    for w in wavs:
        t = os.path.splitext(w)[0] + ".txt"
        if not os.path.exists(t):
            continue
        ref = texto_a_fonemas(open(t, encoding="utf-8").read())
        if len(ref) < 3:
            continue
        sig, _ = librosa.load(w, sr=16000)
        hip = normaliza_sec(w2v.reconoce(sig))
        r = alinear(ref, hip)
        resultados.append(r)
        filas.append({"clip": os.path.basename(w), "n_ref": len(ref),
                      "per": round(r.per, 3),
                      "ref": " ".join(ref[:25]), "hip": " ".join(hip[:25])})
    glob_res = agregar(resultados)
    df = pd.DataFrame(filas)
    os.makedirs(DIR_RES, exist_ok=True)
    df.to_csv(os.path.join(DIR_RES, "validacion_infantil.csv"), index=False, encoding="utf-8")

    print(f"\n=== Domain gap (reconocedor de fonemas) ===")
    print(f"  PER en NIÑOS (habla continua): {glob_res.per:.3f}")
    print(f"  PER en ADULTOS (palabra aislada, ref.): {PER_ADULTOS:.3f}")
    print(f"  -> degradación ~x{glob_res.per/PER_ADULTOS:.1f} (indicativa)")
    print("\nEjemplos:")
    for f in filas[:4]:
        print(f"  [{f['clip']}] PER={f['per']}")
        print(f"     ref: {f['ref']}")
        print(f"     hip: {f['hip']}")
    print("\nGuardado: results/validacion_infantil.csv")


if __name__ == "__main__":
    main()
