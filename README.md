# Hackatón AIBiomed — Análisis de audio para el cribado de TDL

Proyecto para el hackatón de Blue Route. Objetivo clínico: **cribado temprano de TDL
(Trastorno del Desarrollo del Lenguaje) en niños**. Sobre audios de 32 palabras (lista de
Laura Bosch, repositorio Forvo) se resuelven tres tareas:

- **T1 — Fonemas:** identificar los fonemas de cada palabra (independiente del hablante).
- **T2 — Origen:** clasificar al hablante en España / Latinoamérica / No nativo.
- **T3 — Sexo:** clasificar al hablante en hombre / mujer.

Se evalúa P/R/F1 **y** tiempo, recursos y facilidad de integración → soluciones **ligeras**.
Informe completo en **[INFORME.md](INFORME.md)**.

## Estructura
```
data/
  raw/Base_datos_palabras/   audios originales (mp3), no versionado
  raw/nexdata_child/         muestras infantiles (validación), no versionado
  processed/                 audio 16 kHz mono + metadata.csv + caché embeddings
  metadata.csv               etiquetas (ruta, palabra, hablante, sexo, país, origen)
  fonemas_canonicos.csv      referencia fonémica IPA de las 32 palabras
docs/                        propuesta del hackatón + investigación TDL infantil
results/                     métricas y figuras
src/
  pipeline/                  librería reutilizable (importable, sin "ejecutar")
    preprocessing.py           Pipeline sklearn: cargar→recortar silencio→normalizar
    features.py                PitchFeatures (F0) y MFCCFeatures
    embeddings.py              ECAPA / XLS-R (+ caché XLS-R)
    splits.py                  validación por hablante (Stratified)GroupKFold
    clasificacion.py           cv_eval, proba_oof, modelos, voto, confianza
    fonemas_canonicos.py       referencia canónica de las 32 palabras (genera el CSV)
    alineamiento.py            alineamiento de fonemas (Levenshtein) + métricas
    procesos_fonologicos.py    detección de procesos + PCC
    g2p_es.py                  grafema→fonema español (para validación infantil)
    reconocedor.py             wav2vec2 / Allosaurus + plegado dialectal
  scripts/                   entrypoints (un paso por archivo, en orden)
    1_preparar_datos.py        metadata + preprocesado + EDA
    2_sexo.py                  T3 — sexo (F0 vs XLS-R + confianza)
    3_origen.py                T2 — origen (MFCC/ECAPA/XLS-R + confianza + voto)
    4_fonemas.py               T1 — reconocimiento (wav2vec2 vs Allosaurus + equidad)
    5_procesos.py              T1 — procesos fonológicos + PCC + screening JSON
    6_validacion_infantil.py   validación con voz infantil (domain gap)
```

## Estrategia de datos
- **Test:** audios locales de Forvo (`data/raw/Base_datos_palabras/`).
- **Entrenamiento (escalado):** OpenSLR Latinoamérica (etiquetas sexo/país).
- **Validación por hablante** (GroupKFold) en todo → sin fuga de hablante.
- **Dialecto:** variantes aceptadas por plegado (seseo θ=s, yeísmo ʎ=ʝ) → sin sesgo;
  el origen se usa como dato de registro/autosugerencia (human-in-the-loop), no como puerta.

## Entorno y ejecución
Gestionado con [`uv`](https://docs.astral.sh/uv/). Python 3.11, PyTorch CUDA 12.4.
```
uv sync                                        # crea .venv e instala dependencias
uv run python src/scripts/1_preparar_datos.py  # datos + preprocesado + EDA
uv run python src/scripts/2_sexo.py            # T3 sexo
uv run python src/scripts/3_origen.py          # T2 origen
uv run python src/scripts/4_fonemas.py         # T1 fonemas
uv run python src/scripts/5_procesos.py        # T1 procesos fonológicos + PCC
uv run python src/scripts/6_validacion_infantil.py  # validación voz infantil
uv run python src/pipeline/fonemas_canonicos.py     # (re)genera la referencia IPA
```
> Nota VSCode: selecciona el intérprete de `.venv` (Ctrl+Shift+P → "Python: Select
> Interpreter") para evitar falsos errores de import de Pylance.

## Resultados
| Tarea | Mejor modelo | F1 | Notas |
|---|---|---|---|
| T1 Fonemas | wav2vec2-xlsr-espeak | 0.86 | sin sesgo dialectal; PER 0.17 (Allosaurus 0.66) |
| T2 Origen | XLS-R + LogReg (voto) | 0.62 (Esp/Latam) | confianza + override manual |
| T3 Sexo | XLS-R + LogReg | 0.82 | F0 baseline 0.74; confianza + override |

## Hardware de referencia
Ryzen 7 5800H · 16 GB RAM · RTX 3050 Laptop (4 GB VRAM) → modelos preentrenados
congelados + clasificadores ligeros (sin fine-tuning pesado).