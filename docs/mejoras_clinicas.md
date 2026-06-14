# Análisis clínico especializado — mejoras y ampliaciones

Revisión del sistema de cribado fonológico desde la perspectiva de logopedia / patología del
habla y lenguaje pediátrica. No implica implementar (se decidió mantener los 8 procesos del
documento); son propuestas priorizadas para la evolución clínica del producto.

> Encuadre clave que atraviesa todo: el sistema mide **habla** (fonología/articulación), que
> **correlaciona pero NO es** TDL (trastorno del **lenguaje**: comprensión, gramática, vocabulario).
> Un positivo fonológico **deriva a valoración**, no diagnostica.

## 1. Métricas clínicas estándar (salida más interpretable) — *quick wins*
- **Severidad por PCC (Shriberg & Kwiatkowski, 1982):** ya calculamos PCC; basta clasificar en
  leve (>85 %), leve-moderado (65-85 %), moderado-grave (50-65 %), grave (<50 %). Métrica que los
  logopedas reconocen de inmediato.
- **Procesos como % de oportunidades**, no conteo bruto: "reducción de grupos en 4/7 palabras con
  grupo (57 %)" es más interpretable y normalizable que "4".
- **Inventario fonético por edad (McLeod & Crowe, 2018):** reportar fonemas adquiridos / emergentes /
  ausentes frente a lo esperado en español para esa edad (norma específica del idioma), más granular
  que el conteo de procesos.
- **Marco SODA** (Sustitución / Omisión / Distorsión / Adición): hoy no se capturan **distorsiones**
  (p. ej. /r/ o /s/ distorsionada pero reconocible) porque el reconocedor mapea al fonema más cercano;
  son clínicamente relevantes.

## 2. Variabilidad / consistencia (subtipo diagnóstico) — *alto valor*
- **Inconsistencia (Dodd):** repetir un subconjunto de palabras 2-3 veces y medir variabilidad
  token-a-token. >40 % de inconsistencia (en ~25 palabras) sugiere **Trastorno Fonológico
  Inconsistente**, subtipo que requiere terapia distinta (Core Vocabulary). El sistema actual (una
  producción por palabra) no lo capta; encaja con el mecanismo de reintento ya implementado.

## 3. Procesos atípicos vs evolutivos (modelo de riesgo más fino)
- No todos pesan igual: los **atípicos** (omisión de consonante **inicial**, posteriorización/backing,
  sustitución por **glotal**, omisión de sílaba tónica) son señales de alarma mucho mayores que los
  evolutivos (reducción de grupos, frontalización), aun siendo menos frecuentes. El conteo actual los
  trata por igual → **ponderar** los atípicos mejoraría la especificidad (Dodd; Bowen).

## 4. Factores diferenciales a registrar (SEGURIDAD y EQUIDAD) — *crítico*
Antes de emitir un riesgo, el registro debería capturar y el informe condicionar:
- **Audición / otitis media recurrente:** confound #1 de la fonología; un niño con hipoacusia
  transitoria falla fonemas por no oírlos, no por TDL.
- **Lengua(s) del hogar / bilingüismo / exposición L2:** los "errores" de un niño bilingüe pueden ser
  **transferencia interlingüística**, no trastorno → los bilingües se **sobre-derivan**. Imprescindible
  para evitar falsos positivos (equidad).
- **Estructura orofacial** (frenillo lingual, fisura) y **congestión/resfriado** el día de la prueba.

## 5. Inteligibilidad medida con instrumento validado — *quick win*
- La confianza del ASR es un proxy débil. Añadir la **ICS (Intelligibility in Context Scale,
  McLeod et al.)**: 10 ítems a los padres, validada en español, rápida; complementa el análisis
  acústico con una medida funcional ("¿le entienden los desconocidos?").

## 6. Diseño de la elicitación (validez de la prueba)
- **Conocimiento léxico:** si el niño no conoce la palabra, no la nombra → falsa omisión. Bosch usa
  imagen + **imitación diferida** de respaldo. Mejora: si falla el nombrado, la app reproduce un
  **modelo** y el niño repite (ya tenemos audios de referencia adultos).
- **Posición del fonema:** medir y reportar cada fonema en inicial / media / final (Bosch lo hace).
- **Habla conectada / repetición de frases:** los procesos en habla espontánea difieren de la palabra
  aislada; la **repetición de oraciones** es marcador fuerte de TDL en español (Aguado) y ampliaría de
  "habla" hacia "lenguaje".

## 7. Acercarse al objetivo "lenguaje" (no solo habla)
- Extensión: cribado breve de **lenguaje** (vocabulario receptivo tipo TVIP/Peabody, comprensión de
  órdenes) para tocar el dominio que define el TDL. Mínimo imprescindible: que el informe deje
  explícito que un positivo fonológico **no afirma TDL** y deriva a valoración de lenguaje.

## 8. Seguimiento longitudinal — *probablemente el mayor valor clínico*
- El criterio decisivo no es una foto puntual, es la **PERSISTENCIA**: un proceso que sigue presente a
  los 6-12 meses es la alarma real. Guardar sesiones por niño y mostrar la **trayectoria** convierte el
  cribado en monitorización.

## 9. Validación y regulación — *imprescindible para uso clínico*
- **Estudio de validación** contra evaluación logopédica gold-standard (Clínica Pediátrica Amado):
  **sensibilidad/especificidad** (en cribado prima **alta sensibilidad**), VPP/VPN según prevalencia
  7-8 %, y concordancia con el logopeda. Auditoría de **sesgo** en niños (dialecto, sexo, NSE, bilingüismo).
- **Producto sanitario:** encaje regulatorio (MDR / marcado CE; probable software de cribado clase
  I-IIa). La propuesta ya incluye perfil de regulación de *medical devices* (Elsa Vilabella).

## 10. Ética y comunicación
- Mensajería a familias **no alarmista** ("conviene una valoración", nunca diagnóstico).
- **Voz pediátrica = dato de salud sensible** (RGPD): consentimiento informado, minimización y
  almacenamiento seguro.

---
### Prioridad sugerida
| Prioridad | Acción |
|---|---|
| 🟢 Rápida, alto impacto | Severidad PCC · % por oportunidades · registrar audición/bilingüismo · ICS · encuadre habla≠lenguaje en el informe |
| 🟡 Media | Inventario por edad (McLeod&Crowe) · ponderar procesos atípicos · imitación de respaldo · precisión por posición |
| 🔴 Mayor (proyecto) | Consistencia (Dodd) · seguimiento longitudinal · repetición de frases/lenguaje · estudio de validación + regulación |