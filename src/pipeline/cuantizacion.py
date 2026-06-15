"""
Cuantización INT8 (dinámica) + exportación del reconocedor de fonemas, para el camino
EDGE (móvil) de la arquitectura híbrida.

Usa la cuantización dinámica nativa de PyTorch (torch.ao.quantization.quantize_dynamic):
convierte a int8 las capas Linear (que dominan los parámetros del transformer wav2vec2),
sin dependencias extra. Reduce el peso del modelo y acelera la inferencia en CPU/móvil,
con pérdida de calidad pequeña (se mide en scripts/10_comparar_cuantizado.py).

Para un runtime móvil real el siguiente paso sería exportar a ONNX/ExecuTorch/CoreML;
esta cuantización es el primer escalón medible y reproducible aquí.
"""
from __future__ import annotations

import io
import os

import torch
import torch.ao.quantization as tq

from pipeline.reconocedor import W2V


def cuantizar_modelo(model):
    """Devuelve una copia int8 (dinámica) del modelo, en CPU y en modo eval."""
    model = model.to("cpu").eval()
    return tq.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8).eval()


def cargar_w2v_cuantizado():
    """Carga el W2V y lo cuantiza in-place (camino EDGE). Fuerza CPU (int8 dinámico es CPU)."""
    w2v = W2V()
    w2v.model = cuantizar_modelo(w2v.model)
    w2v.dev = "cpu"
    return w2v


def tamano_mb(model):
    """Tamaño en MB del state_dict serializado (proxy del peso en disco/descarga)."""
    buf = io.BytesIO()
    torch.save(model.state_dict(), buf)
    return round(buf.getbuffer().nbytes / (1024 * 1024), 1)


def exportar(model, ruta):
    """Exporta (serializa) el state_dict del modelo a disco. Devuelve el tamaño en MB."""
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    torch.save(model.state_dict(), ruta)
    return round(os.path.getsize(ruta) / (1024 * 1024), 1)