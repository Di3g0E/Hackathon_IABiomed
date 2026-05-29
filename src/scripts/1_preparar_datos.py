"""
Paso 1 — Preparar datos: etiquetas (metadata) + preprocesado de audio + EDA.

Ejecutar:  uv run python src/scripts/1_preparar_datos.py
Genera: data/metadata.csv, data/processed/*.wav, data/processed/metadata.csv,
        results/eda_distribuciones.png
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from pipeline.datos import construir_metadata, preprocesar


def main():
    print("### 1/2 Etiquetas (metadata) ###")
    construir_metadata(RAIZ)
    print("\n### 2/2 Preprocesado + EDA ###")
    preprocesar(RAIZ)


if __name__ == "__main__":
    main()