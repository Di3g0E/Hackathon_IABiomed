"""
Embeddings de audio preentrenados para clasificación de origen (T2).

Dos extractores (modelos CONGELADOS, solo inferencia):
  - EcapaEmbedding: ECAPA-TDNN de SpeechBrain (192-dim), diseñado para rasgos de
    hablante (incluye acento).
  - XLSREmbedding: wav2vec2-XLS-R-300m multilingüe, media de los estados ocultos
    (1024-dim); captura pistas fonéticas de acento.
"""
from __future__ import annotations

import os

import numpy as np
import torch


class EcapaEmbedding:
    NOMBRE = "ECAPA-TDNN"

    def __init__(self):
        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except Exception:
            from speechbrain.pretrained import EncoderClassifier  # versiones antiguas
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            run_opts={"device": self.dev},
        )

    def embed_many(self, ondas):
        out = []
        for o in ondas:
            sig = torch.tensor(o, dtype=torch.float32).unsqueeze(0).to(self.dev)
            with torch.no_grad():
                emb = self.model.encode_batch(sig)
            out.append(emb.squeeze().detach().cpu().numpy())
        return np.array(out, dtype=np.float64)


class XLSREmbedding:
    NOMBRE = "XLS-R-300m"

    def __init__(self, mid: str = "facebook/wav2vec2-xls-r-300m"):
        from transformers import AutoFeatureExtractor, AutoModel
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.fe = AutoFeatureExtractor.from_pretrained(mid)
        self.model = AutoModel.from_pretrained(mid).to(self.dev).eval()

    def embed_many(self, ondas):
        out = []
        for o in ondas:
            iv = self.fe(o, sampling_rate=16000, return_tensors="pt").input_values.to(self.dev)
            with torch.no_grad():
                h = self.model(iv).last_hidden_state  # (1, T, 1024)
            out.append(h.mean(dim=1).squeeze().detach().cpu().numpy())
        return np.array(out, dtype=np.float64)


def cargar_embeddings_ecapa(df, raiz, sr=16000):
    """Embeddings ECAPA-TDNN (192-dim) de los clips de `df` (columna ruta_proc), con
    caché en disco. Backbone ligero (~20 MB) frente a XLS-R (~1.2 GB)."""
    import librosa
    cache_npy = os.path.join(raiz, "data", "processed", "emb_ecapa.npy")
    cache_rut = os.path.join(raiz, "data", "processed", "emb_ecapa_rutas.txt")
    rutas = list(df["ruta_proc"])
    if os.path.exists(cache_npy) and os.path.exists(cache_rut):
        with open(cache_rut, encoding="utf-8") as f:
            if f.read().splitlines() == rutas:
                print("Embeddings ECAPA cargados de caché.")
                return np.load(cache_npy)
    print("Calculando embeddings ECAPA (se cachean)...")
    ondas = [librosa.load(os.path.join(raiz, r), sr=sr, mono=True)[0].astype(np.float32)
             for r in rutas]
    X = EcapaEmbedding().embed_many(ondas)
    np.save(cache_npy, X)
    with open(cache_rut, "w", encoding="utf-8") as f:
        f.write("\n".join(rutas))
    return X


def cargar_embeddings_xlsr(df, raiz, sr=16000):
    """Embeddings XLS-R de los clips de `df` (columna ruta_proc), con caché en disco."""
    import librosa
    cache_npy = os.path.join(raiz, "data", "processed", "emb_xlsr.npy")
    cache_rut = os.path.join(raiz, "data", "processed", "emb_xlsr_rutas.txt")
    rutas = list(df["ruta_proc"])
    if os.path.exists(cache_npy) and os.path.exists(cache_rut):
        with open(cache_rut, encoding="utf-8") as f:
            if f.read().splitlines() == rutas:
                print("Embeddings XLS-R cargados de caché.")
                return np.load(cache_npy)
    print("Calculando embeddings XLS-R (se cachean)...")
    ondas = [librosa.load(os.path.join(raiz, r), sr=sr, mono=True)[0].astype(np.float32)
             for r in rutas]
    X = XLSREmbedding().embed_many(ondas)
    np.save(cache_npy, X)
    with open(cache_rut, "w", encoding="utf-8") as f:
        f.write("\n".join(rutas))
    return X
