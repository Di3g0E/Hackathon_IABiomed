"""
Reconocimiento de fonemas + plegado dialectal (compartido por T1 e infantil).

- W2V: wav2vec2-xlsr-53-espeak-cv-ft (IPA), decodificación CTC manual (sin
  depender de phonemizer/espeak en Windows).
- Allo: Allosaurus (reconocedor universal de fonemas).
- Plegado (fold) de equivalencias sistemáticas, aplicado igual a ref e hipótesis,
  para no penalizar acentos: seseo θ=s, yeísmo ʎ=ʝ, róticas ɾ=r, alófonos, glides.
- buscar_ref: referencia canónica plegada por palabra (tolerante al mojibake 'niño').
"""
from __future__ import annotations

import json
import unicodedata

import numpy as np
import torch

from pipeline.fonemas_canonicos import REF

W2V_ID = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"

FOLD = {
    "β": "b", "ð": "d", "ɣ": "g", "ɡ": "g", "ŋ": "n", "ɱ": "m",
    "ɹ": "r", "ʁ": "r", "ʀ": "r", "ɾ": "r", "r": "r",
    "θ": "s", "ʝ": "ʎ", "ɟ": "ʎ", "ʄ": "ʎ",
    "j": "i", "w": "u",
    "ɔ": "o", "ɛ": "e", "ɪ": "i", "ɨ": "i", "ʊ": "u",
    "æ": "a", "ə": "e", "ɐ": "a", "ʌ": "a", "y": "i", "ʏ": "i",
    "c": "k", "q": "k", "χ": "x", "ʃ": "tʃ", "ʧ": "tʃ",
}
INVENTARIO = set("a b d e f g i k l m n o p r s t u x ɲ ʎ".split()) | {"tʃ"}


def _sin_diacriticos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if unicodedata.category(c) != "Mn")


def normaliza_token(t: str):
    t = _sin_diacriticos(t.strip().lower())
    if not t:
        return None
    if "tʃ" in t or t in ("ts", "ts̪"):
        return "tʃ"
    base = t[0] if len(t) > 1 else t
    base = FOLD.get(base, base)
    return base if base in INVENTARIO else "X"


def normaliza_sec(tokens):
    return [n for n in (normaliza_token(t) for t in tokens) if n is not None]


REF_FOLD = {w: normaliza_sec(fon.split()) for w, (fon, _n) in REF.items()}
_ALIAS = {"nino": "niño"}


def buscar_ref(palabra: str):
    if palabra in REF_FOLD:
        return REF_FOLD[palabra]
    clave = "".join(c for c in palabra if c.isascii() and c.isalpha())
    return REF_FOLD[_ALIAS.get(clave, clave)]


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