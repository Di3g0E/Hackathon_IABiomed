# Hackatón AIBiomed — Análisis de audio para cribado de TDL

Proyecto para el hackatón de Blue Route. A partir de audios de 32 palabras (Forvo),
se abordan tres tareas:

- **T1 — Fonemas:** identificar los fonemas que componen cada palabra (independiente del hablante).
- **T2 — Origen:** clasificar al hablante en España / Latinoamérica / No nativo.
- **T3 — Sexo:** clasificar al hablante en hombre / mujer.

Se evalúa precisión/recall/F-score **y** tiempo de entrenamiento/inferencia, recursos
y facilidad de integración en una app → se priorizan soluciones **ligeras y desplegables**.

## Estructura
```
data/raw/         audios y corpus descargados (no versionado)
data/processed/   audio preprocesado (16 kHz mono)
src/              scripts reutilizables
notebooks/        exploración
results/          métricas y figuras
metadata.csv      etiquetas (palabra, hablante, sexo, país, origen)
build_metadata.py genera metadata.csv desde los nombres de archivo
```

## Estrategia de datos
- **Entrenamiento:** OpenSLR Latinoamérica (gratis, etiquetas sexo/país).
- **Test:** los audios locales de Forvo (`Base_datos_palabras/`).
- **Validación por hablante** (GroupKFold) para evitar fuga de hablante.

## Entorno
Gestionado con [`uv`](https://docs.astral.sh/uv/). Python 3.11, PyTorch CUDA 12.4.
```
uv sync          # crea .venv e instala dependencias
uv run python build_metadata.py
```

## Hardware de referencia
Ryzen 7 5800H · 16 GB RAM · RTX 3050 Laptop (4 GB VRAM) → modelos preentrenados
congelados + clasificadores ligeros (sin fine-tuning pesado).
```
