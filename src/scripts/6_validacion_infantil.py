"""
Paso 6 — Validación con VOZ INFANTIL real (prueba de domain gap).

1) Descarga muestras públicas de habla infantil en español (Nexdata, sin login)
   si no están ya en data/raw/nexdata_child/.
2) (Opcional) detector de "niño" (audeering) -> confirma voces infantiles.
3) Reconocedor wav2vec2 + G2P español -> PER en habla infantil, comparado con
   el PER en adultos (indicativo: niños = habla continua; adultos = palabra aislada).

Ejecutar:  uv run python src/scripts/6_validacion_infantil.py
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

from pipeline.reconocedor import W2V, normaliza_sec
from pipeline.alineamiento import alinear, agregar
from pipeline.g2p_es import texto_a_fonemas

DIR_CHILD = os.path.join(RAIZ, "data", "raw", "nexdata_child")
DIR_RES = os.path.join(RAIZ, "results")
AGE_ID = "audeering/wav2vec2-large-robust-24-ft-age-gender"
PER_ADULTOS = 0.17
REPOS = [
    "Nexdata/Latin_American_Spanish_Children_Spontaneous_Speech_Data",
    "Nexdata/145_Hours_Spanish_Child_Spontaneous_Speech_Data",
]


def descargar():
    from huggingface_hub import snapshot_download
    for repo in REPOS:
        sub = os.path.join(DIR_CHILD, repo.split("/")[-1])
        try:
            snapshot_download(repo_id=repo, repo_type="dataset", local_dir=sub)
        except Exception as e:
            print(f"[WARN] {repo}: {e}")


class _Head(nn.Module):
    def __init__(self, config, n):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.final_dropout)
        self.out_proj = nn.Linear(config.hidden_size, n)

    def forward(self, x):
        x = self.dropout(x); x = torch.tanh(self.dense(x)); x = self.dropout(x)
        return self.out_proj(x)


def detector_nino(wavs):
    from transformers import Wav2Vec2Processor
    from transformers.models.wav2vec2.modeling_wav2vec2 import Wav2Vec2Model, Wav2Vec2PreTrainedModel

    class AgeGender(Wav2Vec2PreTrainedModel):
        _tied_weights_keys = []
        all_tied_weights_keys = {}

        def __init__(self, config):
            super().__init__(config)
            self.wav2vec2 = Wav2Vec2Model(config)
            self.age = _Head(config, 1)
            self.gender = _Head(config, 3)
            self.init_weights()

        def forward(self, x):
            h = torch.mean(self.wav2vec2(x)[0], dim=1)
            return self.age(h), torch.softmax(self.gender(h), dim=1)

    proc = Wav2Vec2Processor.from_pretrained(AGE_ID)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = AgeGender.from_pretrained(AGE_ID).to(dev).eval()
    edades, p_child = [], []
    for w in wavs:
        sig, _ = librosa.load(w, sr=16000)
        iv = torch.from_numpy(proc(sig, sampling_rate=16000)["input_values"][0]).unsqueeze(0).to(dev)
        with torch.no_grad():
            age, gen = model(iv)
        edades.append(float(age.item()) * 100); p_child.append(float(gen[0, 2].item()))
    print(f"  Edad estimada media: {np.mean(edades):.1f} años | P(niño) media: {np.mean(p_child):.2f} "
          f"| P(niño)>0.5: {sum(p > 0.5 for p in p_child)}/{len(wavs)}")


def main():
    wavs = sorted(glob.glob(os.path.join(DIR_CHILD, "**", "*.wav"), recursive=True))
    if not wavs:
        print("Descargando muestras infantiles (Nexdata)...")
        descargar()
        wavs = sorted(glob.glob(os.path.join(DIR_CHILD, "**", "*.wav"), recursive=True))
    print(f"Clips infantiles: {len(wavs)}")
    if not wavs:
        print("No se pudieron obtener audios infantiles."); return

    print("\nDetector de niño (audeering)...")
    try:
        detector_nino(wavs)
    except Exception as e:
        print(f"  [detector no cargado: {type(e).__name__}] -> se omite "
              f"(clips infantiles por construcción del dataset).")

    print("\nReconocedor wav2vec2 (T1) + G2P...")
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
        r = alinear(ref, normaliza_sec(w2v.reconoce(sig)))
        resultados.append(r)
        filas.append({"clip": os.path.basename(w), "n_ref": len(ref), "per": round(r.per, 3)})
    g = agregar(resultados)
    os.makedirs(DIR_RES, exist_ok=True)
    pd.DataFrame(filas).to_csv(os.path.join(DIR_RES, "validacion_infantil.csv"),
                               index=False, encoding="utf-8")
    print(f"\n=== Domain gap ===")
    print(f"  PER niños (habla continua): {g.per:.3f}  vs  adultos (palabra aislada): {PER_ADULTOS}")
    print(f"  -> degradación ~x{g.per/PER_ADULTOS:.1f} (indicativa)")
    print("Guardado: results/validacion_infantil.csv")


if __name__ == "__main__":
    main()