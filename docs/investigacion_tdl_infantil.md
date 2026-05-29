# Detección temprana de TDL en niños — investigación de datos y métodos (verificado 2025-2026)

> Objetivo clínico de Blue Route: cribado **temprano, rápido y fácil** de TDL/TEL (DLD/SLI)
> en niños (distinguible ~3 años, diagnosticable ~4-5). El dataset del hackatón son
> grabaciones de **adultos** (Forvo, 32 palabras de la lista de Laura Bosch).

## Conclusión principal
**No existe (a 2025-2026) ningún dataset público y descargable de audio de niños en español
etiquetado con TDL/TEL.** Los corpus españoles de CHILDES/PhonBank son casi todos de
desarrollo *típico* y muchos solo tienen transcripción (no audio). El único corpus abierto
de audio infantil con etiqueta de trastorno es **checo (LANNA SLI)**.

## 1. Datasets de habla infantil

### CHILDES / TalkBank — español  (https://talkbank.org/childes/access/Spanish/)
Licencia TalkBank (CC BY-NC-SA / "Ground Rules", gratis). **Casi todos típicos.** Con AUDIO/VÍDEO:

| Corpus | Edades | Variedad | Media |
|---|---|---|---|
| AguadoOrea/Pine | 1;10–2;07 | España | Audio |
| Aguirre | 1;7–2;10 | España | Audio |
| Remedi | 1;11–2;10 | Argentina | Audio |
| Shiro | 6;0–9;0 | Venezuela (narrativa) | Audio |
| Nieva | 1;8–2;3 | España | Vídeo |
| Ornat (López-Ornat) | 1;7–4;0 | España | Vídeo |
| LlinasOjea | 0;11–3;02 | ES-EN bilingüe | Vídeo |
| BecaCESNo, Diez-Itza, Aguado, Linaza, Marrero, Serra/Solé, Vila, ColMex, Montes, Koine... | varias | varias | **solo transcripción** |

- ⚠️ Verificar audio por corpus en la página viva antes de descargar.
- Ninguno es clínico/TDL: son adquisición típica.

### PhonBank (fonología, IPA)  (https://phonbank.talkbank.org/)
Transcrito en IPA con Phon + enlace a grabaciones, niños pequeños. Cobertura española escasa.
Con audio: **PhonBLA** (alemán-español) https://phon.talkbank.org/access/Biling/PhonBLA.html

### Bancos clínicos de TalkBank
**No hay banco pediátrico de TDL/SLI.** AphasiaBank/DementiaBank/etc. son de adultos. FluencyBank = tartamudez.

### Corpus clínicos españoles de TEL/DLD
Existen como estudios y **tests comerciales**, no como datos abiertos:
- Aguado (pseudopalabras, baremos): https://www.neurologia.com/articulo/2006395
- Mendoza — **CEG** (comprensión gramatical, comercial TEA/Hogrefe); CEG-Infantil 2-4 años
- Auza/Bedore/Peña/Gutiérrez-Clellen — **BESA** (bilingüe 4;0-6;11): datos no públicos
- Gabani, Bedore & Peña (2009) — ML de LI en ES/ES-EN, corpus no distribuido

### LANNA SLI (checo) — único audio infantil abierto con etiqueta de trastorno
PLOS ONE 2016: https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0150365
- Edades ~4-12; controles (70+) y SLI (46 + 67 graduados leve/moderado/severo)
- 13 tareas (vocales, palabras, frases, oraciones)
- Acceso abierto vía LINDAT/CLARIN: http://hdl.handle.net/11372/LRT-1597
- Base de la mayoría de papers de deep learning de SLI (ver §3)

### Kaggle / HF / Zenodo / OSF
- Kaggle "Specific Language Impairment" (dgokeeffe): **NO es audio ni español** — son 64
  características de transcripciones inglesas (CHILDES: Conti-Ramsden/ENNI/Gillam), ~1163
  niños 4-16, etiqueta TD/SLI. Útil para prototipar *método*.
  https://www.kaggle.com/datasets/dgokeeffe/specific-language-impairment
- No apareció ningún dataset de audio infantil-TDL en español. **Hueco confirmado.**

## 2. Marcadores clínicos y métodos de cribado (qué debe medir el modelo)
- **Repetición de oraciones (SRep)**: el marcador individual MÁS preciso (~90% sens / 85% esp).
  En **español, SRep > repetición de pseudopalabras (NWR)** (Aguado et al.):
  https://www.sciencedirect.com/science/article/abs/pii/S0214460318300421
- **NWR (pseudopalabras)**: fuerte (memoria fonológica de trabajo); discrimina TEL en español
  (Girbau 2016), catalán-español y portugués.
- Otros marcadores ES: morfología verbal (tiempo/concordancia), omisión de clíticos, MLU bajo,
  procesos fonológicos (simplificaciones).
- Herramientas estándar ES: **Bosch "Evaluación fonológica del habla infantil"** (3;0-7;11;
  32 palabras-imagen que cubren todos los fonemas consonánticos; mide procesos de
  simplificación — ¡es la fuente de tus 32 palabras!), **RFI Monfort** (3-6;6; 57 palabras),
  CEG, PLON-R, PPVT/Peabody, CUMANIN.
- Revisión sistemática 2025 (la más autorizada): Hu, Ngai & Chen, *JSLHR* — cribado automático
  de TDL existe solo en 5 idiomas (checo, italiano, mandarín, español, inglés).
  https://pubs.asha.org/doi/10.1044/2025_JSLHR-24-00488

### Papers ML/DL de detección de TDL
- LANNA (checo): SLINet, CNN-1D híbrido, texturas LBP de espectrogramas (90%+, muestra pequeña).
- Transcripción (inglés): Hassanali et al., pipelines NLP sobre narrativas CHILDES.
- Detección de errores fonológicos (método reutilizable): autoencoder Siamés
  https://arxiv.org/pdf/2008.03193

## 3. Modelos preentrenados para habla infantil
- **Brecha adulto→niño es real**: el habla infantil tiene F0/formantes altos y variables;
  Whisper puede dar ~50% de error de fonemas en niños. wav2vec2 transfiere mejor; conviene
  preentrenar en adultos y luego adaptar a niños. Comparativa: https://arxiv.org/abs/2311.04936
- **Detector de edad/niño**: `audeering/wav2vec2-large-robust-24-ft-age-gender` (clase "child";
  CC BY-NC-SA, no comercial) — útil para **comprobar que la entrada es un niño**.
  https://huggingface.co/audeering/wav2vec2-large-robust-24-ft-age-gender

## 4. Camino realista para el hackatón (recomendado)
1. **Replantear como cribado/triaje, NO diagnóstico** (el diagnóstico lo hace un logopeda).
2. Modelar **desarrollo típico** con corpus infantiles abiertos en español (AguadoOrea/Pine,
   Aguirre, Remedi, Shiro) + un wav2vec2 español.
3. Usar tus **audios adultos de las 32 palabras de Bosch como referencia canónica** y construir
   un **detector de procesos fonológicos** (reducción de grupos, omisión de sílabas,
   sustituciones) que compare la producción del niño con la referencia y con normas por edad.
4. **Simular errores fonológicos** sobre audio/transcripción limpia para crear datos etiquetados.
5. Implementar los marcadores de alto rendimiento automatizables: **NWR y SRep**, + MLU/morfología
   desde transcripción ASR.
6. **Validación real → colaborar con la clínica** (Clínica Pediátrica Amado, mencionada en la
   propuesta): es la única vía a audio español de TDL etiquetado.

**Avisos de incertidumbre:** la disponibilidad de audio por corpus de CHILDES cambia (verificar
en la página viva); revisar términos de LANNA al descargar; las precisiones de LANNA son de
muestra pequeña monolingüe → no asumir transferencia a español.
