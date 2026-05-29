"""
Fase 4b — Reconocimiento de fonemas y comparación de modelos.

Compara dos reconocedores (Allosaurus y wav2vec2-xlsr-53-espeak-cv-ft) sobre los
audios adultos, midiendo contra la referencia canónica de Bosch.

Estrategia dialect-robusta (acordada): se PLIEGAN (fold) las equivalencias
sistemáticas a una forma común, aplicada por igual a referencia e hipótesis, para
no penalizar acentos:
  - seseo:  θ = s
  - yeísmo: ʎ = ʝ
  - róticas: ɾ = r (no penalizar confusión tap/vibrante)
  - alófonos: β→b ð→d ɣ→g ŋ→n ɹ→r ...
  - glides: j→i  w→u
  - alófonos vocálicos: ɔ→o ɛ→e ɨ/ɪ→i ʊ→u æ→a
Tokens desconocidos (ruido del modelo) -> 'X' (cuentan como error, no se ocultan).

Ejecutar:  uv run python src/scripts/reconocer_fonemas.py
"""
from __future__ import annotations

import os
import sys
import json
import time
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd
import librosa
import torch
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
from pipeline.alineamiento import alinear, agregar
from pipeline.fonemas_canonicos import REF

RAIZ = os.path.dirname(SRC)
META = os.path.join(RAIZ, "data", "processed", "metadata.csv")
DIR_RES = os.path.join(RAIZ, "results")
W2V_ID = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"

# --- Plegado de equivalencias ---
FOLD = {
    "β": "b", "ð": "d", "ɣ": "g", "ɡ": "g", "ŋ": "n", "ɱ": "m",
    "ɹ": "r", "ʁ": "r", "ʀ": "r", "ɾ": "r", "r": "r",      # róticas -> r
    "θ": "s",                                               # seseo
    "ʝ": "ʎ", "ɟ": "ʎ", "ʄ": "ʎ",                           # yeísmo
    "j": "i", "w": "u",                                     # glides
    "ɔ": "o", "ɛ": "e", "ɪ": "i", "ɨ": "i", "ʊ": "u",
    "æ": "a", "ə": "e", "ɐ": "a", "ʌ": "a", "y": "i", "ʏ": "i",
    "c": "k", "q": "k", "χ": "x", "ʃ": "tʃ", "ʧ": "tʃ",
}
INVENTARIO = set("a b d e f g i k l m n o p r s t u x ɲ ʎ".split()) | {"tʃ"}


def _sin_diacriticos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if unicodedata.category(c) != "Mn")


def normaliza_token(t: str) -> str | None:
    t = _sin_diacriticos(t.strip().lower())
    if not t:
        return None
    if "tʃ" in t or t in ("ts", "ts̪"):
        return "tʃ"
    base = t[0] if len(t) > 1 else t          # multi-char raro -> primer símbolo
    base = FOLD.get(base, base)
    if base in INVENTARIO:
        return base
    return "X"                                 # desconocido -> error explícito


def normaliza_sec(tokens) -> list[str]:
    out = []
    for t in tokens:
        n = normaliza_token(t)
        if n is not None:
            out.append(n)
    return out


# Referencia canónica ya plegada (misma transformación que la hipótesis)
REF_FOLD = {w: normaliza_sec(fon.split()) for w, (fon, _nota) in REF.items()}

# El nombre de carpeta 'niño' viene corrupto del disco (mojibake de Mac).
# Búsqueda tolerante: empareja por las letras ASCII de la palabra.
_ALIAS = {"nino": "niño"}


def buscar_ref(palabra: str) -> list[str]:
    if palabra in REF_FOLD:
        return REF_FOLD[palabra]
    clave = "".join(c for c in palabra if c.isascii() and c.isalpha())
    return REF_FOLD[_ALIAS.get(clave, clave)]


# ---------- Reconocedores ----------
class W2V:
    def __init__(self):
        from transformers import AutoFeatureExtractor, AutoModelForCTC
        from huggingface_hub import hf_hub_download
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.fe = AutoFeatureExtractor.from_pretrained(W2V_ID)
        self.model = AutoModelForCTC.from_pretrained(W2V_ID).to(self.dev).eval()
        vocab = json.load(open(hf_hub_download(W2V_ID, "vocab.json"), encoding="utf-8"))
        self.id2tok = {v: k for k, v in vocab.items()}
        self.especiales = {"<pad>", "<s>", "</s>", "<unk>", "|", " ", ""}

    def reconoce(self, wav):
        iv = self.fe(wav, sampling_rate=16000, return_tensors="pt").input_values.to(self.dev)
        with torch.no_grad():
            ids = self.model(iv).logits.argmax(-1)[0].tolist()
        toks, prev = [], None
        for i in ids:
            if i != prev:
                toks.append(i)
            prev = i
        return [self.id2tok[i] for i in toks if self.id2tok.get(i) not in self.especiales]


class Allo:
    def __init__(self):
        from allosaurus.app import read_recognizer
        self.m = read_recognizer()

    def reconoce_path(self, ruta):
        return self.m.recognize(ruta, lang_id="spa").split()


def evalua(nombre, reconoce_fn, df, usa_path):
    por_clip, por_origen = [], {}
    t0 = time.perf_counter()
    for _, r in df.iterrows():
        ref = buscar_ref(r["palabra"])
        if usa_path:
            hip = normaliza_sec(reconoce_fn(r["abs"]))
        else:
            wav, _ = librosa.load(r["abs"], sr=16000)
            hip = normaliza_sec(reconoce_fn(wav))
        res = alinear(ref, hip)
        por_clip.append(res)
        por_origen.setdefault(r["origen"], []).append(res)
    dur = time.perf_counter() - t0
    glob = agregar(por_clip)
    print(f"\n### {nombre} ###  ({dur:.1f}s, {dur/len(df)*1000:.0f} ms/clip)")
    print(f"  P={glob.precision:.3f}  R={glob.recall:.3f}  F1={glob.f1:.3f}  PER={glob.per:.3f}")
    print("  Por origen (F1 | PER):")
    for orig, lst in sorted(por_origen.items()):
        g = agregar(lst)
        print(f"    {orig:10s} n={len(lst):3d}  F1={g.f1:.3f}  PER={g.per:.3f}")
    return {"nombre": nombre, "dur": dur, "glob": glob, "por_origen": por_origen}


def main():
    df = pd.read_csv(META)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    df["abs"] = df["ruta_proc"].apply(lambda r: os.path.join(RAIZ, r))
    print(f"Clips: {len(df)} | fonemas de referencia (plegados): "
          f"{sum(len(buscar_ref(w)) for w in df['palabra'])}")

    resultados = []
    print("\nCargando wav2vec2...")
    w2v = W2V()
    resultados.append(evalua("wav2vec2-xlsr-espeak", w2v.reconoce, df, usa_path=False))

    print("\nCargando Allosaurus...")
    allo = Allo()
    resultados.append(evalua("Allosaurus", allo.reconoce_path, df, usa_path=True))

    # ---- Figura comparativa ----
    os.makedirs(DIR_RES, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4))
    nombres = [r["nombre"] for r in resultados]
    x = np.arange(len(nombres))
    ax.bar(x - 0.2, [r["glob"].precision for r in resultados], 0.2, label="Precision")
    ax.bar(x,       [r["glob"].recall for r in resultados],    0.2, label="Recall")
    ax.bar(x + 0.2, [r["glob"].f1 for r in resultados],        0.2, label="F1")
    ax.set_xticks(x); ax.set_xticklabels(nombres); ax.set_ylim(0, 1)
    ax.set_title("Reconocimiento de fonemas — comparación"); ax.legend()
    fig.tight_layout()
    out = os.path.join(DIR_RES, "fonemas_comparacion.png")
    fig.savefig(out, dpi=120)
    print(f"\nFigura: {os.path.relpath(out, RAIZ)}")


if __name__ == "__main__":
    main()
