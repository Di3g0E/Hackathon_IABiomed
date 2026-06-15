# Informe comparativo de modelos — sistema CLOUD (full) vs MÓVIL (edge)

Fork `movil-edge`. Medido en CPU sobre `data/processed` (225 clips de adultos, Forvo).
Reproducible con `src/scripts/10_comparar_cuantizado.py`, `11_detectores.py`, `12_comparar_modelos.py`.

## Resumen ejecutivo
- **Reconocedor de fonemas (núcleo clínico): la cuantización INT8 es claramente ganadora** —
  −72 % de peso y 3× más rápido **sin perder calidad** (PER/F1 se mantienen o mejoran). Es
  el resultado más importante: el cribado puede correr en móvil conservando la calidad.
- **Modelo de edad**: misma reducción (−72 %, 3,8×) pero con más desviación al cuantizar
  (~1,8 años en voz adulta). Aceptable porque la edad es un tramo 3-6 que la familia revisa.
- **Detectores origen/sexo**: muy ligeros. **Sexo** funciona bien (ECAPA 0,89). **Origen**
  rinde flojo incluso con ECAPA (~0,53): el acento es difícil con estos datos (pocas muestras,
  "No nativo" n=15) → usarlo como sugerencia de baja confianza apoyada en el perfil.

---

## 1. Reconocedor de fonemas (wav2vec2-xlsr-espeak) — full fp32 vs int8

| Sistema | Peso | PER ↓ | F1 ↑ | Latencia/clip |
|---|---|---|---|---|
| FULL fp32 (cloud) | 1205 MB | 0.205 | 0.834 | 304 ms |
| **EDGE int8 (móvil)** | **338 MB** | **0.187** | **0.845** | **101 ms** |
| Δ | −72 % | −0.017 | +0.011 | **3.0× más rápido** |

Calidad **mantenida** (la leve mejora está dentro del ruido). Modelo exportado: `results/w2v_int8_edge.pt`.

## 2. Modelo de edad (audeering wav2vec2-large) — full fp32 vs int8

| Sistema | Peso | Latencia/clip |
|---|---|---|
| FULL fp32 | 1211 MB | 381 ms |
| INT8 | 340 MB | 99 ms |
| Δ | −72 % | 3.8× más rápido |

Acuerdo full↔int8: **diferencia media 1.8 años** (máx 10.2) sobre voz adulta. Más desviación
que el reconocedor, pero tolerable: la edad solo discrimina el tramo 3-6 y es **editable por
la familia** (flujo estimar→confirmar). No hay versión int8 oficial en HF → se cuantiza local.

## 3. Detectores de ORIGEN y SEXO — MFCC vs ECAPA

| Tarea | Features | Accuracy | F1 macro | dim | Latencia features | Peso cabeza |
|---|---|---|---|---|---|---|
| Origen (3 clases) | MFCC | 0.502 | 0.424 | 80 | 14 ms | 3.4 KB |
| Origen (3 clases) | ECAPA | 0.533 | 0.434 | 192 | 56 ms | 5.6 KB |
| Sexo | MFCC | 0.827 | 0.777 | 80 | 3.5 ms | 3.0 KB |
| **Sexo** | **ECAPA** | **0.893** | **0.854** | 192 | 41 ms | 4.8 KB |

> El "peso cabeza" es solo el clasificador (KB). **MFCC** no añade modelo (extractor de peso 0).
> **ECAPA** añade el encoder (~20 MB fp32 / ~6 MB int8) y ~4-10× más latencia de features.

**Lectura:**
- **Sexo**: ECAPA merece la pena (+0.066 accuracy) si se asume +6 MB y +40 ms; MFCC si se
  prioriza peso mínimo. OJO: entrenado con voz **adulta** → en niños 3-6 poco fiable → sugerencia
  editable en el perfil (como la edad).
- **Origen**: ni MFCC (0.50) ni ECAPA (0.53) dan buen resultado. Causas: "No nativo" con solo
  15 muestras, desbalance (España 97 / Latam 113 / No nativo 15) y dificultad intrínseca del
  acento. Recomendación: más datos (sobre todo no nativos e infantiles) y/o fusionar con la
  **lengua materna declarada** en el perfil; mientras tanto, baja confianza + dato del perfil (HITL).

## 3b. Detector origen/sexo — comparación de cabezas (mismos embeddings ECAPA, mismos folds)

Los dos candidatos son **ambos ECAPA-TDNN**; solo cambia la cabeza. Comparados sobre los
MISMOS embeddings y MISMOS folds (5-fold estratificado):

| Tarea | Cabeza | Accuracy | F1 macro |
|---|---|---|---|
| Origen | sklearn (StandardScaler+LogReg balanced, main) | 0.542 | 0.430 |
| Origen | numpy (LogReg propio, fork) | 0.533 | 0.434 |
| Sexo | sklearn (main) | 0.893 | 0.841 |
| Sexo | numpy (fork) | 0.893 | 0.854 |

**Equivalentes** (Δ ≤ 0.013, ruido de partición); mismo peso/latencia. **Decisión: se conserva
la cabeza sklearn de `main`** por ingeniería (backbone ECAPA compartido entre tareas, pipeline
estándar y mantenible, E/S robusta, ya integrada). El "0.62" del XLS-R que citó el patrocinador
era un modelo ~1.2 GB; con ECAPA ligero (~6 MB int8) se obtiene calidad similar en lo que importa.

## Arquitectura consolidada en main
- Reconocedor de fonemas: **int8 en vivo** (juego) + **full en el informe** (`HABLI_BACKEND=hibrido`).
- Edad: int8 en edge/híbrido. · Origen/Sexo: **ECAPA + LogReg**, HITL. · **VAD on-device** + Silero opcional.

---

## Recomendación de despliegue móvil
- **Fonemas**: int8 edge para el juego en vivo (sin pérdida de calidad) + **híbrido** (informe
  del especialista re-evaluado con el modelo full). Ya implementado (`HABLI_BACKEND=hibrido`).
- **Edad**: int8 vale (editable por la familia).
- **Sexo**: ECAPA-int8 si se quiere precisión; si no, MFCC. Siempre como sugerencia editable.
- **Origen**: no fiable aún; recoger más datos antes de exponerlo como dato firme.

## Limitaciones de validez
- Las cifras son sobre **voz adulta** (Forvo); para 3-6 años hay *domain gap* documentado
  (PER infantil 0.29 vs 0.17 adultos). Lo prioritario sería validar con voz infantil real.
- La cuantización INT8 dinámica afecta a capas Linear (transformer); las convoluciones quedan
  fp32. Para un runtime móvil real el siguiente paso es exportar a **ONNX / ExecuTorch / CoreML**.