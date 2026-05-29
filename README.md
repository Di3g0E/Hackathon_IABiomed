# Hackatón AIBiomed — Análisis de audio para cribado de TDL

Proyecto para el hackatón de Blue Route. Objetivo clínico final: **cribado temprano
de TDL (Trastorno del Desarrollo del Lenguaje) en niños**. A partir de audios de 32
palabras (lista de Laura Bosch, repositorio Forvo) se abordan tres tareas:

- **T1 — Fonemas:** identificar los fonemas que componen cada palabra (independiente del hablante).
- **T2 — Origen:** clasificar al hablante en España / Latinoamérica / No nativo.
- **T3 — Sexo:** clasificar al hablante en hombre / mujer.

Se evalúa precisión/recall/F-score **y** tiempo de entrenamiento/inferencia, recursos
y facilidad de integración en una app → se priorizan soluciones **ligeras y desplegables**.

## Estructura
```
data/
  raw/Base_datos_palabras/   audios originales (mp3) por palabra (no versionado)
  processed/                 audio preprocesado 16 kHz mono + metadata.csv
  fonemas_canonicos.csv      referencia fonémica IPA de las 32 palabras
docs/                        propuesta del hackatón + investigación (TDL infantil)
src/
  pipeline/                  librería reutilizable
    preprocessing.py         Pipeline sklearn: cargar→recortar silencio→normalizar
    features.py              PitchFeatures (F0) como transformador sklearn
    splits.py                validación por hablante (Stratified)GroupKFold
    alineamiento.py          alineamiento de fonemas (Levenshtein) + métricas P/R/F1/PER
    fonemas_canonicos.py     referencia canónica de las 32 palabras (genera el CSV)
  scripts/                   entrypoints ejecutables
    build_metadata.py        genera metadata.csv desde los nombres de archivo
    run_preprocess.py        aplica el preprocesado + EDA
    clasif_sexo.py           T3 — clasificación de sexo
    reconocer_fonemas.py     T1 — reconocimiento de fonemas (Allosaurus vs wav2vec2)
results/                     métricas y figuras
metadata.csv                 etiquetas (ruta, palabra, hablante, sexo, país, origen, revisar)
```

## Estrategia de datos
- **Test:** audios locales de Forvo (`data/raw/Base_datos_palabras/`) — conjunto mínimo del reto.
- **Entrenamiento (escalado):** OpenSLR Latinoamérica (gratis, etiquetas sexo/país).
- **Validación por hablante** (GroupKFold) para evitar fuga de hablante.
- **Dialecto:** se aceptan variantes (seseo θ=s, yeísmo ʎ=ʝ) por plegado, sin clasificar el
  origen, para no penalizar acentos (verificado: F1 fonémico sin sesgo entre orígenes).

## Entorno
Gestionado con [`uv`](https://docs.astral.sh/uv/). Python 3.11, PyTorch CUDA 12.4.
```
uv sync                                   # crea .venv e instala dependencias
uv run python src/scripts/build_metadata.py
uv run python src/scripts/run_preprocess.py
uv run python src/scripts/clasif_sexo.py        # T3 sexo
uv run python src/scripts/reconocer_fonemas.py  # T1 fonemas
uv run python src/pipeline/fonemas_canonicos.py # regenera la referencia IPA
```
> Nota VSCode: selecciona el intérprete de `.venv` (Ctrl+Shift+P → "Python: Select
> Interpreter") para evitar falsos errores de import de Pylance.

## Resultados actuales
| Tarea | Modelo | F1 | Notas |
|---|---|---|---|
| T3 Sexo | F0 + LogReg | 0.742 (macro) | ultraligero (train 26 ms, infer 0.01 ms/clip) |
| T1 Fonemas | wav2vec2-xlsr-espeak | 0.862 | sin sesgo dialectal; PER 0.17 |
| T1 Fonemas | Allosaurus | 0.655 | baseline ligero, menos preciso |

## Hardware de referencia
Ryzen 7 5800H · 16 GB RAM · RTX 3050 Laptop (4 GB VRAM) → modelos preentrenados
congelados + clasificadores ligeros (sin fine-tuning pesado).
