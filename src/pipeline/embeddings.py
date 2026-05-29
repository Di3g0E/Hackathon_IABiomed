"""
Embeddings de audio preentrenados para clasificación de origen (T2).

Dos extractores (modelos CONGELADOS, solo inferencia):
  - EcapaEmbedding: ECAPA-TDNN de SpeechBrain (192-dim), diseñado para rasgos de
    hablante (incluye acento).
  - XLSREmbedding: wav2vec2-XLS-R-300m multilingüe, media de los estados ocultos
    (1024-dim); captura pistas fonéticas de acento.
"""
from __future__ import annotations

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
