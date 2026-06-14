# Informe — Análisis de audio para el cribado temprano de TDL
### Hackatón AIBiomed · Blue Route

---

## 1. Resumen ejecutivo

Partiendo de audios de **32 palabras** (lista fonológica de Laura Bosch, repositorio Forvo),
se han resuelto las **tres tareas del reto** y se ha construido, además, el **núcleo clínico**
que conecta con el objetivo real de Blue Route: el **cribado temprano del Trastorno del
Desarrollo del Lenguaje (TDL) en niños**.

| Tarea | Mejor solución | Resultado | Coste |
|---|---|---|---|
| **T1 — Fonemas** | wav2vec2-xlsr-espeak | **F1 0.86** · PER 0.17 · sin sesgo dialectal | 45–81 ms/clip (GPU) |
| **T2 — Origen** | XLS-R + LogReg (+voto) | **F1 0.62** (Esp/Latam) | train 0.3 s · infer 3 ms |
| **T3 — Sexo** | XLS-R + LogReg | **F1 0.82** | train 26 ms · infer 0.01 ms/clip |

Sobre T1 se añadió un **detector de procesos fonológicos** (reducción de grupos,
oclusivización, etc.) con la métrica clínica **PCC**, y una **salida de cribado en JSON**
lista para la app. T2 y T3 incorporan **umbral de confianza + corrección manual**
(*human-in-the-loop*). Todo el sistema es **ligero, reproducible y sin sesgo de acento**.

---

## 2. Contexto y problema

- El **TDL** afecta a ~7% de los niños; es distinguible hacia los 3 años y diagnosticable con
  precisión entre los 4–5. La detección temprana es determinante, pero el diagnóstico requiere
  profesional y hay poca disponibilidad (especialmente rural).
- Blue Route propone una **app telemática** (registro → screening → pruebas de audio →
  diagnóstico → terapia). El **cuello de botella** es que diagnóstico y terapia dependen de un
  profesional. El reto: **un modelo de análisis de audio** que automatice parte de la evaluación.
- El test de Bosch evalúa el habla infantil mediante **nombrado de dibujos** de un conjunto de
  palabras que cubren todo el sistema fonológico → es la tarea **más temprana y fácil** aplicable
  a un niño pequeño, y es justo la que sostiene este sistema.

---

## 3. Datos

- **227 audios** de 32 palabras, **142 hablantes** distintos, de Forvo.
- **Metadatos extraídos del nombre de archivo** (`palabra_usuario_sexo_pais.mp3`) →
  [data/metadata.csv](data/metadata.csv). Sin necesidad de anotación manual.
- **Desbalances reales (parte del desafío):** sexo **178 H / 49 M**; origen
  **Latam 115 / España 97 / No nativo 15**. La clase *No nativo* es minúscula y además tiene un
  *confound*: 8 de sus 15 clips son la palabra `piedra`.
- **Preprocesado** (pipeline reutilizable de scikit-learn): mono 16 kHz → recorte de silencio →
  normalización. Duración media **0,82 s**; se recortó **1,73 s** de silencio por clip.
  EDA en [results/eda_distribuciones.png](results/eda_distribuciones.png).

**Estrategia de evaluación:** los audios de Forvo se usan como **conjunto de test** (el mínimo del
reto); el entrenamiento puede escalarse con **OpenSLR Latinoamérica**. **Validación cruzada POR
HABLANTE** (`StratifiedGroupKFold`) en todo el proyecto, para evitar la **fuga de hablante**
(las 32 palabras se repiten entre hablantes; un split aleatorio inflaría las métricas).

---

## 4. Metodología

- **Pipeline sklearn reutilizable**: el mismo objeto trata igual los datos de Forvo, los futuros
  de OpenSLR y cualquier entrada nueva.
- **Modelos preentrenados congelados + clasificadores ligeros** (no hay fine-tuning): encaja con el
  hardware (RTX 3050, 4 GB VRAM) y con el criterio del reto de **mínimos recursos**.
- **Métricas**: precision / recall / **F1 macro** (por el desbalance), PER (fonemas), PCC (clínica),
  además de **tiempo de entrenamiento/inferencia y recursos**.

---

## 5. T3 — Clasificación de sexo

| Modelo | F1 macro | mujer F1 | Coste |
|---|---|---|---|
| F0 (pitch) + LogReg | 0.742 | 0.614 | train 26 ms · infer 0.01 ms/clip |
| **XLS-R + LogReg** | **0.815** | 0.708 | reutiliza embeddings cacheados |

Con **umbral de confianza** ([results/sexo_confianza.png](results/sexo_confianza.png)): a 0,90 el
sistema **autocompleta el 74% al 95,8% de acierto** y deriva el resto al usuario. Confusión en
[results/sexo_confusion.png](results/sexo_confusion.png).

---

## 6. T2 — Clasificación de origen

| Características | España vs Latam (F1) | 3 clases (F1) |
|---|---|---|
| MFCC + pitch | 0.542 | 0.388 |
| ECAPA-TDNN | 0.575 | 0.408 |
| **XLS-R-300m** | **0.608** (voto/hablante **0.62**) | 0.515 |

El acento desde **una palabra suelta corta** es intrínsecamente difícil; con datos tan pequeños el
resultado es modesto pero **claramente sobre azar**. **Decisión de diseño clave (validada
empíricamente):** no se usa un clasificador de dialecto para "corregir" los fonemas; en su lugar se
**aceptan las variantes dialectales** (seseo θ=s, yeísmo ʎ=ʝ) por plegado → el F1 fonémico es
**igual entre orígenes** (ver §7), sin sesgo.

**Human-in-the-loop + reframe de producto:** el origen es, en realidad, un **dato de registro** que
la familia indica. El clasificador funciona como **autosugerencia con confianza**
([results/origen_confianza.png](results/origen_confianza.png)): a nivel hablante (umbral 0,70)
autocompleta 115 y **consulta al usuario** 27. La corrección manual **se propaga a todas las
palabras** de ese niño y, conociendo el dialecto, permite pasar de la evaluación *permisiva* a una
**referencia fonémica específica del dialecto** (mayor precisión clínica).

---

## 7. T1 — Reconocimiento de fonemas (núcleo clínico)

**Referencia canónica** de las 32 palabras (IPA, 168 fonemas, 23 únicos) en
[data/fonemas_canonicos.csv](data/fonemas_canonicos.csv) — *pendiente de validación por logopeda*.

**Comparación de reconocedores** ([results/fonemas_comparacion.png](results/fonemas_comparacion.png)):

| Modelo | Precision | Recall | F1 | PER |
|---|---|---|---|---|
| **wav2vec2-xlsr-espeak** | 0.870 | 0.855 | **0.862** | 0.174 |
| Allosaurus | 0.688 | 0.626 | 0.655 | 0.433 |

**Auditoría de equidad (wav2vec2):** F1 España 0.852 · Latam 0.865 · No nativo 0.907 → **sin sesgo
dialectal**. Esto valida la estrategia de variantes aceptadas.

**Detector de procesos fonológicos** (el output clínico): a partir del alineamiento niño↔referencia,
clasifica cada desviación en un proceso con nombre clínico (reducción de grupos consonánticos,
oclusivización, frontalización, lateralización, omisiones…) y calcula el **PCC** (Percentage of
Consonants Correct). Línea base en adultos: **PCC 81,8%, igual entre orígenes**
([results/procesos_frecuencia.png](results/procesos_frecuencia.png)). Salida de cribado de ejemplo
para la app en [results/ejemplo_screening.json](results/ejemplo_screening.json).

> **Lectura honesta:** ese PCC ~82% en habla adulta correcta es el **suelo de ruido del
> reconocedor** (~18% de error de fonemas sin fine-tuning). Para niños, los umbrales de riesgo deben
> calibrarse **por encima de ese suelo** y contra **normas por edad**.

---

## 8. Validación con voz infantil (domain gap)

Como **no existe audio infantil en español con las 32 palabras ni con etiqueta TDL** (CHILDES está
tras login; ver [docs/investigacion_tdl_infantil.md](docs/investigacion_tdl_infantil.md)), se usó
una muestra pública de habla infantil espontánea (Nexdata, 44 clips) como prueba de *domain gap*.

| | PER |
|---|---|
| Adultos (palabra aislada) | 0.17 |
| Niños (habla espontánea) | **0.29** (~1.7×) |

**Caveats honestos:** comparación no estricta (palabra aislada vs habla continua + G2P aproximado);
y el detector de edad estimó ~30 años / P(niño) 0,06 → las muestras "infantiles" gratuitas pueden no
ser de niños pequeños (lección de calidad de datos). **Conclusión:** (1) el reconocedor **necesita
adaptación a voz infantil**; (2) la **tarea de palabra aislada de Bosch es el diseño correcto** porque
elimina el confound de habla conectada; (3) la validación clínica real exige **grabaciones infantiles
de las 32 palabras** (vía Clínica Pediátrica Amado). Detalle en
[results/validacion_infantil.csv](results/validacion_infantil.csv).

---

## 9. Integración en la app

- **Ligero y desplegable:** T3/T2 son embeddings congelados + LogReg (inferencia en milisegundos);
  T1 corre en ~50 ms/clip en una GPU de 4 GB. Apto para servidor; T3/T2 incluso on-device.
- **Human-in-the-loop:** sexo y origen se **autocompletan cuando hay confianza** y **se preguntan al
  usuario** cuando no; siempre **corregibles**. Encaja con el paso de **Registro** de la app.
- **Salida estructurada (JSON)** por palabra/niño: fonemas esperados vs detectados, procesos
  fonológicos, PCC y nivel de riesgo → consumible directamente por el front-end de screening.
- **Motor clínico** ([src/pipeline/clinico.py](src/pipeline/clinico.py) + [app_demo](src/scripts/app_demo.py)):
  registro (edad 3-6) → 32 palabras → 8 procesos fonológicos → **riesgo por edad** (Bajo 0-2 /
  Medio 3-5 / Alto >5 errores *impropios para la edad*, o baja inteligibilidad vía confianza de
  transcripción). Normas por edad **configurables** en `data/normas_edad.csv`. Modo clínico que
  conserva ɾ/r (rr) y vocales (diptongos). El demo muestra la **sensibilidad por edad**: la misma
  sesión sale BAJO a los 3-4 años y se marca a los 5-6 (donde el ruido del reconocedor ~18% se
  cuenta como 'alerta') → cuantifica por qué hay que adaptar el reconocedor a voz infantil y
  calibrar umbrales (datos de la Clínica Amado).

### 9.0 Mejora del reconocimiento (decodificación restringida)
El cuello de botella era el suelo de ruido del ASR en decodificación libre (~18% PER adultos). Se
añadió una **decodificación RESTRINGIDA + GOP** (`pipeline/decodificacion.py`): como se sabe qué
palabra se pide, se puntúan la realización canónica y las que generan los 8 procesos contra los
logits CTC (colapsados a clases clínicas, robusto a seseo/yeísmo) y gana la más probable. **PER
0.36 → 0.11 en adultos** (≈3×; `8_comparar_reconocedor.py`). Es la estrategia por defecto, conmutable
con la libre. Complementos: **Silero-VAD + puerta de calidad** (recorte y motivo real de repetición),
**calibración por palabra** (suelo de error del ASR, informativa, no descuenta → sensibilidad intacta),
**modo infantil** por pitch-shift en test-time (A/B; LoRA como scaffold) y **consentimiento** para
guardar audio+edad anonimizados de entrenamiento.

### 9.1 Aplicación conversacional (dos grafos agénticos)
Sobre el motor anterior se ha construido la **app de la propuesta** (`src/app/`), con **LangGraph +
Groq** y **FastAPI**, inspirada en la arquitectura del repo de referencia (orquestador + subagentes + tools):
- **Grafo Familia/Niño** ("Lumi") **conducido por el LLM**: un orquestador (tool-calling) guía
  Registro → Prueba de audio → Resultado (vista familiar SIMPLE: solo nivel + recomendación) →
  Ejercicios de estimulación → Envío, **anuncia cada paso** y emite **señales de acción** para la UI
  (`pedir_registro · iniciar_grabacion · mostrar_resultado · mostrar_ejercicios · ofrecer_envio`).
  Dos subagentes: **operativo** (palabras + ejercicios) y **análisis** (evalúa/clasifica/guarda +
  nota clínica con **PCC multinivel**: por palabra, por grupo de error y global, con severidad
  Shriberg — vista del profesional). Las cifras las calcula el motor (no el LLM); los confounds de
  equidad del registro (bilingüismo, audición, L2) generan avisos sin alterar el riesgo.
- **Re-test** = núcleo fijo + palabras falladas previas; **histórico** completo por niño (audios
  versionados `sesiones/<nino>/p<N>/` + pruebas en SQLite) con **persistencia** por proceso
  (persistente/nuevo/resuelto) y válvulas (2 "alto" seguidos → especialista). **Ronda extra
  opcional** (neutra, con palabras alternativas de la misma estructura) que puede corregir el
  resultado si los errores nuevos no se confirman. **Ejercicios de estimulación (NO terapia)** en
  3 niveles con gating por edad/normas; plan de seguimiento global del especialista por
  **riesgo × edad** (180/42/21 días, `data/plan_seguimiento.csv`, editable por API).
- **Grafo Logopeda**: asistente con **tool-calling** (análisis con severidad PCC, editor de revisión,
  re-puntuación human-in-the-loop, plan, evolución, export). **Entrega:** editor HTML interactivo de
  timeline + **PDF** con la evolución (prueba 1 vs 2) + enlace **`mailto:`** al especialista.
- **Privacidad (RGPD):** el audio infantil se procesa en local y **nunca** se envía al LLM. Estado de
  chat e histórico en SQLite. Sin `GROQ_API_KEY` el flujo degrada a una orquestación determinista.

---

## 10. Enfoque clínico y camino realista

1. **Cribado/triaje, no diagnóstico** (el diagnóstico lo firma un logopeda).
2. **Núcleo:** comparar la producción del niño con la **referencia canónica de Bosch** y detectar
   **procesos fonológicos** + PCC, frente a **normas por edad y dialecto**.
3. **Datos infantiles reales** vía la **Clínica Pediátrica Amado** (en la propuesta) — única vía a
   audio español de TDL etiquetado; además permite **fine-tuning** del reconocedor a voz infantil.
4. **Marcadores complementarios** de alto rendimiento (repetición de oraciones/pseudopalabras) como
   ampliación futura.

---

## 11. Limitaciones

- Dataset pequeño y sesgado (parte del desafío); *No nativo* poco fiable (confound de palabra).
- T2 (origen) modesto: el acento en palabra aislada da poca señal → se mitiga con human-in-the-loop.
- Referencia fonémica hecha por IA: **requiere validación de logopeda**.
- Reconocedor sin adaptar a voz infantil (domain gap confirmado); normas por edad por validar clínicamente.
- **Taxonomía limitada a los 8 procesos del documento clínico.** Cualquier otra discrepancia
  (frontalización velar `k→t`/`g→d`, deafricación `tʃ→s`, omisión de consonante **inicial/medial**,
  confusión tap/vibrante `ɾ↔r`, cambios vocálicos) se clasifica como **"otra discrepancia
  (no objetivo)"** y **NO cuenta como error**. Es deliberado (evita contar ruido del reconocedor
  ~18% PER y variación dialectal), pero implica que **procesos clínicos reales fuera de los 8 no se
  detectan** (posible falso negativo). Decisión pendiente con la logopeda: ¿ampliar la taxonomía?
  - **Mitigación (guardián de validez):** una producción **no válida** —muchas inserciones
    (`> max(2, 0.5×n_ref)`, p.ej. decir una palabra mucho más larga) o cobertura `< ⅓` de los
    fonemas esperados (palabra distinta, balbuceo o silencio)— **nunca se marca "correcta" ni
    puntúa errores**: va a "a repetir" (re-elicitación) y cuenta para la puerta de inteligibilidad.
    Umbrales calibrados con las 32 palabras adultas (máx. observado: 1 inserción, cobertura ≥0.40).
  - **Alineamiento canonicalizado:** ante alineamientos óptimos equivalentes (fonemas repetidos),
    se prefiere conservar los fonemas iniciales y omitir los finales (patrón real de truncamiento:
    "ro" por "rojo" = omite la sílaba final "xo", no un segmento interior "ox").
  - **Validez híbrida en la decodificación restringida:** la restringida clasifica entre hipótesis
    cerradas (necesita clase de rechazo), así que la validez combina el GOP (los fonemas esperados
    deben encajar) con el guardián de inserciones/cobertura sobre la transcripción LIBRE del mismo
    audio ("gorrocóptero" contiene "gorro" y ganaría la canónica; el guardián lo detecta). La
    transcripción libre se guarda en el informe (`transcripcion_libre`) para el profesional.
    **Límite conocido:** un añadido de una sola sílaba en palabra corta ("sillón" por "silla",
    1 inserción) queda por debajo del umbral de ruido del ASR (≤1 inserción en habla correcta) y
    no es detectable sin léxico; se mitiga parcialmente vía GOP/confianza baja → reintento.
  - **Espacio de hipótesis (restringida):** cubre los 8 procesos + variantes; reducción de grupos
    genera tanto "omite obstruyente" como "omite líquida" (forma infantil más común: "tes","banco").
    Procesos fuera de los 8 (lateralización ʎ→l, omisión de consonante inicial/media) se generan como
    hipótesis "otro" (se muestran al profesional, NO cuentan). La selección del ganador tiene **sesgo
    FP>FN**: entre hipótesis cercanas (banda 0.5) se prefiere un proceso objetivo (cuenta) sobre uno
    "otro" sobre la canónica, para no enterrar procesos clínicos.
  - **Límites del modelo acústico (validados con grabaciones reales de la compañera):** (a) en grupos
    consonánticos el ASR puede ALUCINAR la líquida ("banco"→`b l a n k o`); (b) NO distingue de forma
    fiable vibrante múltiple /r/ de tap /ɾ/ intervocálicos ("goro"≈"gorro"). Mitigaciones: la
    canonicalización + las nuevas hipótesis recuperan muchos casos; para /r/ vs /ɾ/ se añade una
    **heurística de duración** (segmento rótico < ~50 ms → flag `duda_rr` informativo, no cuenta).
    Solución de fondo = fine-tune con voz infantil real (scaffold `9_finetune_lora.py` + Clínica Amado).
- **PCC ≠ "correcta":** el PCC (% consonantes correctas) y el indicador clínico (¿alguno de los 8
  procesos?) son métricas distintas; una palabra con PCC bajo puede figurar sin error clínico.
- **Plegado dialectal por diseño:** seseo `θ=s` y yeísmo `ʎ=ʝ` nunca cuentan como error.

---

## 12. Conclusiones

Las tres tareas del reto están resueltas con métricas honestas y validación rigurosa (por hablante,
sin sesgo dialectal, con coste medido). Más allá del reto, se entrega un **prototipo de cribado
fonológico** alineado con el objetivo de Blue Route: detección **temprana, rápida y fácil** mediante
nombrado de dibujos, con un diseño *human-in-the-loop* responsable para uso médico.

---

## 13. Reproducibilidad

Entorno con [`uv`](https://docs.astral.sh/uv/) (Python 3.11, PyTorch CUDA 12.4):
```
uv sync
uv run python src/scripts/1_preparar_datos.py       # metadata + preprocesado + EDA
uv run python src/scripts/2_sexo.py                 # T3 sexo (F0 vs XLS-R + confianza)
uv run python src/scripts/3_origen.py               # T2 origen (MFCC/ECAPA/XLS-R + confianza)
uv run python src/scripts/4_fonemas.py              # T1 fonemas (wav2vec2 vs Allosaurus)
uv run python src/scripts/5_procesos.py             # T1 procesos fonológicos + PCC
uv run python src/scripts/6_validacion_infantil.py  # validación voz infantil
uv run python src/pipeline/fonemas_canonicos.py     # (re)genera la referencia IPA
```
Estructura y detalles en [README.md](README.md). Investigación clínica en
[docs/investigacion_tdl_infantil.md](docs/investigacion_tdl_infantil.md).
