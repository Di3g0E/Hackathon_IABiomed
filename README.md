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
  normas_edad.csv            normas de desarrollo por edad (editable por la logopeda)
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
    procesos_fonologicos.py    detección de procesos + PCC (análisis T1)
    g2p_es.py                  grafema→fonema español (para validación infantil)
    reconocedor.py             wav2vec2 / Allosaurus + plegado + confianza + reconoce_restringido
    decodificacion.py          decodificación RESTRINGIDA + GOP (hipótesis clínicas, CTC forward)
    vad.py                     Silero-VAD + puerta de calidad de captura (SNR/clipping/voces)
    calibracion.py             suelo de error del ASR por palabra (informativo, no descuenta)
    preproc_infantil.py        modo infantil: pitch-shift en test-time (conmutable)
    normas.py                  normas de desarrollo por edad (tabla §8, configurable)
    clinico.py                 MOTOR CLÍNICO: 8 errores + riesgo por edad
    ejercicios.py              ejercicios en 3 NIVELES + plan de seguimiento riesgo×edad (CSVs)
    screening.py               anamnesis/triaje a padres + factores de equidad
  app/                       APP: persistencia, servicio, grafos agénticos y API
    config.py                  rutas, modelos Groq y carga de .env
    almacen.py                 SQLite longitudinal (niños, eventos, evolución)
    herramientas.py            capa de servicio (envuelve el motor; sin audio al LLM)
    informe_pdf.py             export PDF (prueba 1/2 + evolución + ejercicios + PCC multinivel)
    revision_html.py           genera el editor interactivo de timeline de fonemas
    static/editor.{js,css}     editor (onda + letras arrastrables + añadir/quitar)
    grafo_familia.py           grafo Familia/Niño (orquestador + subagentes, Lumi)
    grafo_logopeda.py          grafo Logopeda (tool-calling + fallback determinista)
    api.py                     backend FastAPI (chat, audio, reanalizar, pdf, evolución)
  scripts/                   entrypoints (un paso por archivo, en orden)
    1_preparar_datos.py        metadata + preprocesado + EDA
    2_sexo.py                  T3 — sexo (F0 vs XLS-R + confianza)
    3_origen.py                T2 — origen (MFCC/ECAPA/XLS-R + confianza + voto)
    4_fonemas.py               T1 — reconocimiento (wav2vec2 vs Allosaurus + equidad)
    5_procesos.py              T1 — procesos fonológicos + PCC + screening JSON
    6_validacion_infantil.py   validación con voz infantil (domain gap)
    7_calibrar.py              suelo de error del ASR por palabra (data/calibracion_palabras.csv)
    8_comparar_reconocedor.py  A/B libre vs restringida × adulto vs infantil
    9_finetune_lora.py         SCAFFOLD fine-tune LoRA infantil (no se ejecuta por defecto)
    app_demo.py                DEMO app (sin micro): sobre audios existentes
    app.py                     APP interactiva: graba tu voz y obtén el cribado
    revisar_sesion.py          informe HTML (audio + onda con fonemas en el tiempo) — uso médico
    reanalizar.py              re-puntúa tras editar 'detectado' en el informe (corrección manual)
    app_familia_cli.py         CLI del grafo Familia (recorre el flujo completo, Lumi)
    app_logopeda_cli.py        CLI del grafo Logopeda (análisis + plan + editor + PDF)
    demo_longitudinal.py       demo prueba 1 → ejercicios → prueba 2 + evolución + PDF
    generate_pdf.py            export del análisis clínico (mejoras_clinicas) a PDF
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
uv run python src/pipeline/normas.py                # (re)genera normas_edad.csv
uv run python src/scripts/app_demo.py               # DEMO app: cribado end-to-end + riesgo
```

## Motor clínico de cribado (app)
Registro (edad 3-6; sexo/origen autosugeridos por T3/T2) → 32 palabras → reconocimiento de
fonemas + confianza → clasificación en **8 procesos fonológicos** (reducción de grupos,
sustitución r→l, errores en rr, omisión de sílabas, oclusivización, simplificación de
diptongos, omisión de consonantes finales, asimilaciones) → **riesgo por edad**:
- **Bajo** 0-2 · **Medio** 3-5 · **Alto** >5 errores *impropios para la edad* (o baja
  inteligibilidad = baja confianza de transcripción).
- Las normas por edad (`data/normas_edad.csv`) son **editables** por la logopeda.
- El modo clínico conserva ɾ/r (rr) y vocales (diptongos), a diferencia del fold de T1.
- **Control de fiabilidad:** palabras con baja confianza se marcan "a repetir" y NO se puntúan
  como errores (evita falsos positivos por fallos de captura). Las palabras correctas se
  reportan como tales; las discrepancias no objetivo (ruido/dialecto) van aparte, no como error.

### Reconocimiento: decodificación restringida + GOP, VAD, calibración, modo infantil
El reconocedor es **conmutable** (`app/config.py`), sin perder la versión anterior:
- **Decodificación RESTRINGIDA + GOP** (por defecto, `ESTRATEGIA_RECONOCEDOR=restringida`): en vez
  de transcribir libre, puntúa la palabra esperada y sus realizaciones clínicas (los 8 procesos)
  contra los logits CTC y elige la más probable → el proceso sale de qué hipótesis gana. **Reduce el
  PER de 0.36 a 0.11** en adultos (≈3× menos ruido; ver `8_comparar_reconocedor.py`). El plegado a
  clases clínicas hace que seseo/yeísmo no penalicen. La decodificación **libre** original queda
  disponible (`ESTRATEGIA_RECONOCEDOR=libre`).
- **Silero-VAD + puerta de calidad** (`pipeline/vad.py`): recorte preciso del habla y motivo real para
  repetir (no se oyó / ruido / saturado / varias voces). Cae al detector de energía si Silero no está.
- **Calibración por palabra** (`7_calibrar.py` → `data/calibracion_palabras.csv`): mide el suelo de
  error del ASR con los 227 audios adultos. Es **solo informativa** (marca "interpretar con cautela" y
  sugiere repetir); **nunca descuenta errores** (se prioriza la sensibilidad: mejor FP que FN).
- **Modo infantil** (`MODO_INFANTIL=1`): pitch-shift en test-time hacia rango adulto. Comparable en
  paralelo con `8_comparar_reconocedor.py`. El fine-tune LoRA+VTLP queda como scaffold (`9_finetune_lora.py`).
- **Consentimiento de datos**: si la familia lo marca en el registro, el audio+edad se guardan
  anonimizados en `data/entrenamiento/` (etiquetas.csv) para mejorar el modelo; si no, solo para el
  especialista. RGPD: id seudónimo (hash), carpeta gitignored.

### Uso interactivo y revisión médica
```
uv run python src/scripts/app.py --rapida        # grabas tu voz (8 palabras) → cribado
uv run python src/scripts/revisar_sesion.py diego_6   # HTML: audio + onda con fonemas + tiempos
uv run python src/scripts/reanalizar.py results/informe_diego_6.json  # re-puntuar tras editar
```
- `app.py` graba con **pre-roll/post-roll** (empieza antes del aviso y corta después) para no
  perder el inicio/final de la palabra. Las grabaciones se guardan en `data/raw/sesiones/<id>/`.
- `revisar_sesion.py` genera `results/revision_<id>.html`: por palabra, reproductor de audio,
  gráfica de la onda con cada fonema situado en el tiempo, y la tabla de tiempos.
> Nota VSCode: selecciona el intérprete de `.venv` (Ctrl+Shift+P → "Python: Select
> Interpreter") para evitar falsos errores de import de Pylance.

## Aplicación conversacional (propuesta Blue Route)
Implementa el flujo de la propuesta (**Registro → Prueba de audio → Resultado → Ejercicios de
estimulación → Seguimiento/Envío**) con
**dos grafos agénticos** (LangGraph + Groq) que orquestan subagentes y llaman a la capa de
servicio (`app/herramientas.py`), que a su vez envuelve el motor clínico. Arquitectura inspirada
en el repo de referencia `PFINAL_AP-IA` (FastAPI + LangGraph + orquestador-router + tools).

- **Grafo Familia/Niño (`grafo_familia.py`, "Lumi") — CONDUCIDO POR EL LLM:** un orquestador
  (LLM con tool-calling) conduce todo el proceso, anuncia cada paso y emite una **señal de acción**
  para la UI. Dos subagentes: **operativo** (decide las palabras de la prueba y propone los ejercicios)
  y **análisis** (evalúa, clasifica, guarda el histórico y redacta la nota clínica). El LLM **nunca**
  inventa cifras (se calculan en el motor) ni toca el audio.
  - **Vista familiar simplificada SIEMPRE:** la familia ve solo el **nivel** del resultado y la
    recomendación (sin cifras ni detalle por palabra); el detalle completo vive en el informe
    profesional descargable.
  - Respuesta del chat: `{mensaje, accion, datos, fin}`. Acciones: `pedir_registro · iniciar_grabacion ·
    mostrar_resultado · mostrar_ejercicios · ofrecer_envio · ninguna` (la oferta de ronda extra viaja
    en `mostrar_resultado.datos.ronda_extra`).
- **Registro (sign-in):** nombre* y edad* obligatorios; sexo, lengua materna, bilingüismo y
  antecedentes auditivos opcionales → generan **avisos de equidad** en la nota clínica y el PDF
  (no modifican el riesgo).
- **Ejercicios de estimulación del habla (NO terapia) en 3 niveles** (`data/ejercicios.csv`):
  N1 general (3-6), N2 conciencia fonológica (4-6; sonido inicial 5-6), N3 personalizado por error
  (solo procesos no-normales para la edad según `data/normas_edad.csv`). Mapeo: bajo=1×N1 ·
  medio=N1+N2 · alto=N1+N2+N3. Biblioteca completa en `GET /ejercicios?edad=&riesgo=`.
- **Plan de seguimiento global del especialista** (`data/plan_seguimiento.csv`, editable vía
  `GET/PUT /logopeda/config/plan`): bajo = seguimiento OPCIONAL a 6 meses · medio = repetir en
  6 semanas · alto = repetir en 3 semanas y, si persiste, especialista. Plazos legibles
  (días→semanas→meses).
- **Re-test enfocado + histórico:** la 1ª prueba pide las 32 palabras; el re-test pide **núcleo fijo
  + palabras falladas**. Audios versionados en `data/raw/sesiones/<nino>/p<N>/`; todas las pruebas
  en SQLite. **Persistencia** por proceso (persistente/nuevo/resuelto) visible para el médico;
  **2 resultados "alto" seguidos → recomendar especialista**.
- **Ronda extra (opcional):** desde el 2º test, si aparecen errores nuevos se ofrece de forma
  **neutra** ("¿jugamos una ronda más?") repetir con **palabras distintas** de la misma estructura;
  si salen bien, el resultado **se corrige** (anotado); si no, queda anotado sin cambiar el riesgo.
- **Entrega:** **PDF descargable** (con PCC por palabra/grupo/global + severidad Shriberg, vista
  médico) + enlace **`mailto:`** prerrellenado con el correo del especialista.
- **Grafo Logopeda (`grafo_logopeda.py`):** asistente profesional con **tool-calling real** (cargar
  informe, análisis clínico multinivel, generar editor, re-puntuar, ejercicios, evolución, PDF).
- **Privacidad (RGPD):** el audio infantil se procesa en local y **nunca** se envía al LLM (solo
  fonemas/métricas). Estado de chat e histórico en SQLite; IDs saneados; sin clave de Groq el flujo
  degrada a una orquestación determinista por estado (mismas acciones).

```
cp .env.example .env          # añade tu GROQ_API_KEY (sin ella funciona en modo respaldo determinista)
uv run python src/scripts/app_familia_cli.py --alias Ana --edad 5 --sesion diego_6   # chat guiado por Lumi
uv run python src/scripts/app_logopeda_cli.py --sesion diego_6_p1                      # asistente logopeda
uv run python src/scripts/demo_longitudinal.py                                        # prueba 1→2 + evolución
uv run uvicorn app.api:app --app-dir src --reload    # API (docs en http://127.0.0.1:8000/docs)
```
Endpoints clave (contrato para la UI): `POST /familia/chat {id, mensaje, datos?}` → `{mensaje, accion,
datos, fin, llm}`; `POST /familia/audio/{palabra}` (form `nino_id`, `ronda=principal|repeticion`;
acumula y versiona el audio); `POST /sesion/finalizar`; `GET /ejercicios?edad=&riesgo=` (biblioteca);
`POST /nino/{id}/ejercicio` (marcar hecho); `GET/PUT /logopeda/config/plan`;
`GET /sesion/{id}/revision.html` (editor interactivo); `POST /logopeda/reanalizar/{id}`;
`GET /nino/{id}/evolucion`; `GET /informe/{id}/pdf`; `GET /informe/{id}/envio?email=` → `{pdf_url,
mailto_url}`; `POST /logopeda/chat {id, mensaje}`.

### Editor interactivo y entrega al especialista
- **Editor de timeline** (`/sesion/{id}/revision.html`, id = prueba p.ej. `ana_5_p1`): por palabra,
  reproductor + onda + la línea de tiempo de fonemas **editable** (arrastrar dónde está cada letra,
  añadir/eliminar/renombrar). "Re-puntuar" envía las correcciones a la API y actualiza el riesgo en vivo.
- **PDF + envío** (`/informe/{nino}/pdf`, `/informe/{nino}/envio`): resumen de las pruebas, **evolución**
  entre la 1ª y la 2ª (deltas + tiempos), ejercicios y encuadre clínico; descargable y enviable por mailto.

## Resultados
| Tarea | Mejor modelo | F1 | Notas |
|---|---|---|---|
| T1 Fonemas | wav2vec2-xlsr-espeak | 0.86 | sin sesgo dialectal; PER 0.17 (Allosaurus 0.66) |
| T2 Origen | XLS-R + LogReg (voto) | 0.62 (Esp/Latam) | confianza + override manual |
| T3 Sexo | XLS-R + LogReg | 0.82 | F0 baseline 0.74; confianza + override |

## Hardware de referencia
Ryzen 7 5800H · 16 GB RAM · RTX 3050 Laptop (4 GB VRAM) → modelos preentrenados
congelados + clasificadores ligeros (sin fine-tuning pesado).