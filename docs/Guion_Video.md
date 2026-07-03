# Guión del vídeo de evidencia — Habli (Hackatón IABiomed · Blue Route)

**Duración objetivo: 5:00 min (límite).** Reparto: **A** = Andrea López Guirado (Biomédica) · **D** = Diego Esclarín Fernández (Ingeniero de IA).
Convención: **[PANTALLA]** = lo que se ve · _en cursiva_ = lo que se dice.

> Consejo de grabación: graba la demo real **antes** y locuta encima. Si vas justo de tiempo, los bloques marcados con ✂️ son los recortables.

---

## 0 · Gancho + título (0:00 – 0:20)

**[PANTALLA]** Portada de la memoria / logo Habli sobre el degradado de marca.

- **A:** _"El 7% de los niños tiene Trastorno del Desarrollo del Lenguaje. Detectarlo pronto lo cambia todo, pero hoy depende de un profesional y de listas de espera."_
- **D:** _"Somos Andrea y Diego. Esto es **Habli**: un sistema de análisis de audio que convierte un juego de nombrar dibujos en un cribado clínico temprano. Cribado, nunca diagnóstico."_

---

## 1 · El problema y la decisión de partida (0:20 – 0:55)

**[PANTALLA]** Diapositiva del flujo de Blue Route: Registro → Screening → Audio → Terapia, con el "cuello de botella" resaltado.

- **A:** _"La propuesta de Blue Route es una app que conecta familias y clínicas. El cuello de botella está en la evaluación del habla: necesita un logopeda y tiempo."_
- **D:** _"Nuestra pieza es ese modelo de audio. Y una decisión de diseño nos guió desde el minuto uno: con una GPU de 4 GB, nada de entrenar modelos enormes. Usamos **modelos preentrenados congelados + clasificadores ligeros**. Encaja con el criterio del reto: mínimos recursos."_

---

## 2 · El análisis biomédico de Andrea (0:55 – 1:35)

**[PANTALLA]** Lista de 32 palabras de Bosch + tabla de los 8 procesos fonológicos + nota "habla ≠ lenguaje".

- **A:** _"Mi parte fue el marco clínico. Partimos del test de Laura Bosch: 32 palabras que cubren todo el sistema fonológico del español. Es la prueba más temprana y sencilla que se le puede pedir a un niño de 3 años: nombrar dibujos."_
- **A:** _"Definí los **8 procesos fonológicos** que cuentan como señal de alarma —reducción de grupos, omisiones, oclusivización…— y validé la referencia fonética. Y un principio que atraviesa todo: medimos **habla**, que correlaciona pero no es el TDL. Por eso un positivo **deriva a valoración**, no diagnostica."_
- **A:** _"También fijé los criterios de **equidad y seguridad**: bilingüismo o problemas de audición se registran como avisos, para no sobre-derivar a un niño sano."_

---

## 3 · Las tres tareas del reto, resueltas (1:35 – 2:25)

**[PANTALLA]** Tabla de resultados (T1/T2/T3) de la memoria.

- **D:** _"El reto pedía tres cosas sobre esos audios. Las tres están resueltas, con validación **por hablante** para no inflar las métricas."_
  - _"**Fonemas**: wav2vec2 con F1 de 0,86 y, lo importante, **sin sesgo dialectal** —el F1 es igual en España, Latinoamérica y no nativos."_
  - _"**Sexo**: F1 de 0,82."_
  - _"**Origen**: F1 de 0,62."_
- **D:** _"Y aquí seamos honestos: el origen rinde modesto. Clasificar el acento desde una sola palabra corta es dificilísimo con datos tan pequeños."_
- **A:** _"Pero eso **no afecta al cribado**, y es a propósito: el origen **no es una puerta de decisión**. Es un dato de registro que la familia confirma; el modelo solo **autosugiere** y, si no está seguro, **pregunta**. Humano en el bucle. El cribado se apoya en los fonemas, que no tienen sesgo."_

---

## 4 · DEMO en vivo — la familia juega (2:25 – 3:25)

**[PANTALLA]** App real. Chat de **Lali**. Se hace el registro (nombre + edad), empieza el "juego" y se graba el niño nombrando varias palabras.

- **D:** _"Vamos a verlo funcionando. La familia entra y Lali, nuestra mascota, conduce el juego —nunca dice 'test' ni 'examen'."_
- **[ACCIÓN]** Registrar edad → pulsar grabar → decir 2-3 palabras (una bien, una con un error claro, p. ej. "tes" por "tres").
- **D:** _"El audio se procesa **en local**: nunca sale del dispositivo ni se envía al modelo de lenguaje. El reconocedor corre **cuantizado a int8**, que pesa un 72% menos y va 3 veces más rápido **sin perder calidad**."_
- **[PANTALLA]** Resultado de la familia: solo nivel + recomendación (sin cifras).
- **A:** _"Fijaos: a la familia solo le mostramos un nivel y una recomendación cálida. **Ningún número, ningún diagnóstico.** Eso es del logopeda."_

---

## 5 · DEMO — la vista del logopeda (3:25 – 4:15)

**[PANTALLA]** Informe del logopeda: timeline de fonemas editable + PCC y severidad + procesos detectados. Edita un fonema y se re-puntúa.

- **D:** _"Esta es la otra cara: el profesional. Aquí sí aparecen los datos —el alineamiento del niño contra la referencia, el **PCC** con severidad de Shriberg y los procesos detectados."_
- **D:** _"Como sabemos qué palabra se pide, usamos **decodificación restringida**: el error de fonemas baja de 0,36 a 0,11. Y hay un **guardián de validez**: si el niño dice otra palabra o balbucea, se marca 'a repetir', nunca se cuenta como correcta."_
- **[ACCIÓN]** Arrastrar/editar un fonema en el timeline → el riesgo se recalcula.
- **A:** _"El logopeda tiene la última palabra: corrige aquí mismo y el sistema vuelve a puntuar. Y guardamos el **histórico** del niño: lo que de verdad importa clínicamente es la **persistencia** de un error en el tiempo."_
- **[PANTALLA]** Botón de informe → se abre el **PDF** de evolución (prueba 1 vs prueba 2).

---

## 6 · Recursos, privacidad y honestidad (4:15 – 4:45)

**[PANTALLA]** Tabla de la memoria: int8 −72% / 3× · detectores ECAPA ~6 MB · arquitectura híbrida edge↔cloud.

- **D:** _"Sobre viabilidad: todo está medido y optimizado para móvil. Modelo int8 en el dispositivo para el juego, modelo completo en servidor solo para el informe. Y las cifras las calcula el motor, no el modelo de lenguaje: el coste de IA queda acotado."_
- **A:** _"Y somos transparentes con la gran limitación: **no existe** audio infantil etiquetado en español. Lo dejamos como **línea futura** —recoger datos reales con la Clínica Pediátrica Amado para adaptar el reconocedor a la voz infantil. Tenemos el consentimiento y el andamiaje listos."_

---

## 7 · Cierre (4:45 – 5:00)

**[PANTALLA]** Logo Habli + eslogan "Jugamos, hablamos y aprendemos" + URL del repositorio.

- **A:** _"Habli: detección temprana, ligera y responsable."_
- **D:** _"Tres tareas resueltas y una app completa, con privacidad por diseño y el profesional siempre en el centro. Gracias."_
- **[PANTALLA]** `github.com/Di3g0E/Hackathon_IABiomed` · _Cribado, no diagnóstico._

---

### Checklist de cosas que el vídeo DEBE dejar ver (rúbrica del jurado)
- [ ] **Funcionamiento real** (no solo slides): grabación de voz → resultado → informe → PDF.
- [ ] Las **3 tareas** con sus métricas (F1 0,86 / 0,82 / 0,62) y la **validación por hablante**.
- [ ] **Decisiones de diseño**: modelos congelados, sin sesgo dialectal, human-in-the-loop.
- [ ] **Análisis biomédico de Andrea**: Bosch, 8 procesos, habla ≠ lenguaje, equidad.
- [ ] Los **3 apuntes del patrocinador**: origen 0,62 salvado por HITL · recursos optimizados (int8/híbrido) · datos infantiles como limitación + línea futura.
- [ ] **Privacidad RGPD**: el audio del niño nunca sale del dispositivo / nunca va al LLM.
- [ ] **Cribado, no diagnóstico** dicho explícitamente.
- [ ] La **URL del repositorio** en pantalla.

### Notas de producción
- Si te pasas de 5:00, recorta primero en el bloque 6 (resúmelo en una frase) y acorta el registro de la demo.
- Graba la pantalla a 1080p; pon el móvil/navegador en un tamaño de fuente grande.
- Ten preparado un audio de respaldo por si el micro falla en directo (la app puntúa un `.wav` ya grabado).
