#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Genera la Memoria Tecnica de Habli (hackaton IABiomed / Blue Route) como HTML
on-brand, la renderiza a PDF con Chrome/Edge headless y estampa pie + numeracion
de pagina con pypdf + fpdf2.

Marca: docs/habli-brand.skill (tokens y logo oficial). Modo clinico/profesional.
"""
import base64
import pathlib
import subprocess
import zipfile

from fpdf import FPDF
import pypdf

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = ROOT / "docs" / "habli-brand.skill"
OUT_HTML = ROOT / "docs" / "Memoria_Tecnica_Habli.html"
OUT_PDF = ROOT / "docs" / "Memoria_Tecnica_Habli.pdf"
TMP_PDF = ROOT / "docs" / "_memoria_sin_pie.pdf"
OVERLAY = ROOT / "docs" / "_pie.pdf"
CHROME = pathlib.Path(r"C:/Program Files/Google/Chrome/Application/chrome.exe")
DEJAVU = ROOT / "DejaVuSans.ttf"


def b64_logo(nombre: str) -> str:
    with zipfile.ZipFile(SKILL) as z:
        data = z.read(f"habli-brand/assets/logos/{nombre}")
    return base64.b64encode(data).decode("ascii")


LOGO_COLOR = b64_logo("habli-logo.png")     # Lali a color + wordmark
ICONO = b64_logo("habli-icono.png")

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&family=Nunito:wght@400;600;700&display=swap');
:root{
  --azul-700:#2C7186; --azul-600:#3F92AC; --azul-500:#52B2CB; --azul-400:#84CFE0;
  --azul-200:#C4E8F2; --azul-50:#EAF7FB;
  --verde-700:#3E7A2A; --verde-500:#66B43F; --verde-200:#CDE9A8; --verde-50:#EFF8E4;
  --amarillo-500:#F2C242; --naranja-500:#EF9A30;
  --tinta-900:#173A4D; --tinta-700:#2C5566; --gris-500:#5E7785; --gris-400:#93A7B2;
  --gris-200:#D9E3E8; --gris-100:#EFF4F6; --fondo:#F6FAFB; --blanco:#FFFFFF;
  --r-bajo:#66B43F; --r-medio:#EF9A30; --r-alto:#E5705A;
  --grad-hero:linear-gradient(150deg,#173A4D 0%,#2C7186 45%,#3F92AC 70%,#549636 100%);
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{font-family:"Nunito","Trebuchet MS",sans-serif; color:var(--tinta-700);
  font-size:10pt; line-height:1.42; background:#fff;
  -webkit-print-color-adjust:exact; print-color-adjust:exact;}
h1,h2,h3,h4{font-family:"Poppins","Nunito",sans-serif;}
@page{ size:A4; margin:15mm 16mm 17mm 16mm; }
@page cover{ size:A4; margin:0; }

/* portada */
.cover{page:cover; position:relative; height:297mm; width:210mm;
  background:var(--grad-hero); color:#fff; overflow:hidden; page-break-after:always;}
.cover .glow{position:absolute; right:-120px; top:-120px; width:520px; height:520px;
  background:radial-gradient(circle, rgba(132,207,224,.30) 0%, rgba(132,207,224,0) 70%);}
.cover .glow2{position:absolute; left:-160px; bottom:-160px; width:560px; height:560px;
  background:radial-gradient(circle, rgba(102,180,63,.25) 0%, rgba(102,180,63,0) 70%);}
.cover-inner{position:absolute; inset:0; padding:26mm 22mm; display:flex; flex-direction:column;}
.logo-card{background:#fff; border-radius:24px; padding:16px 26px; align-self:flex-start;
  box-shadow:0 16px 40px rgba(23,58,77,.18);}
.logo-card img{height:84px; width:auto; display:block;}
.cover .kicker{margin-top:auto; font-weight:700; letter-spacing:.20em; text-transform:uppercase;
  font-size:9.5pt; color:var(--azul-200);}
.cover h1{font-size:31pt; font-weight:800; line-height:1.08; margin:8px 0 6px;}
.cover .sub{font-size:13.5pt; font-weight:600; color:#eaf7fb; max-width:560px;}
.cover .descriptor{margin-top:14px; font-size:10.5pt; color:var(--azul-200); font-style:italic;}
.cover .meta{margin-top:30px; border-top:1px solid rgba(255,255,255,.22); padding-top:16px; font-size:10pt;}
.cover .meta .row{display:flex; gap:40px;}
.cover .meta b{font-family:"Poppins"; font-weight:600; font-size:8.5pt; letter-spacing:.12em;
  text-transform:uppercase; color:var(--azul-200); margin-bottom:5px; display:block;}
.cover .author{margin-bottom:9px;}
.cover .author .nm{font-family:"Poppins"; font-weight:600; color:#fff; font-size:10.5pt;}
.cover .author .rl{color:var(--azul-200); font-size:9pt;}
.cover a{color:#dff2f8; text-decoration:underline;}
.cover .repo{margin-top:8px; font-size:9.5pt;}
.cover .repo b{display:inline; text-transform:none; letter-spacing:0; font-size:9.5pt; color:var(--azul-200);}
.cover .legal{position:absolute; left:22mm; bottom:14mm; font-size:8.8pt; color:rgba(196,232,242,.85);}

/* secciones */
h2.sec{font-size:15.5pt; font-weight:700; color:var(--tinta-900); margin:26px 0 1px;
  padding-left:11px; border-left:5px solid var(--azul-500); page-break-after:avoid;}
.sec-num{font-family:"Poppins"; font-weight:700; color:var(--azul-500);}
.sec-lead{color:var(--gris-500); font-size:9.6pt; margin:1px 0 10px 11px; page-break-after:avoid;}
h3{font-size:11.5pt; color:var(--tinta-900); margin:13px 0 3px; font-weight:600; page-break-after:avoid;}
h4{font-size:10.2pt; color:var(--azul-700); margin:11px 0 1px; font-weight:600; page-break-after:avoid;}
p{margin:5px 0;}
ul{margin:5px 0; padding-left:17px;} li{margin:2px 0;}
b,strong{color:var(--tinta-900);}
a{color:var(--azul-700);}
.small{font-size:8.6pt; color:var(--gris-500);}
.pb{page-break-before:always;}
.avoid{page-break-inside:avoid;}

/* tablas */
table{width:100%; border-collapse:collapse; margin:8px 0; font-size:9.2pt;}
th{background:var(--tinta-900); color:#fff; font-family:"Poppins"; font-weight:600;
  text-align:left; padding:6px 8px; font-size:8.8pt;}
td{padding:5px 8px; border-bottom:1px solid var(--gris-200); vertical-align:top;}
tbody tr:nth-child(even){background:var(--gris-100);}
tr.chosen{background:var(--verde-50)!important;}
tr.chosen td{border-bottom:1px solid var(--verde-200);}
td.hi{font-family:"Poppins"; font-weight:700; color:var(--verde-700);}
caption{caption-side:bottom; text-align:left; font-size:8.2pt; color:var(--gris-400);
  padding-top:4px; font-style:italic;}
.flag{font-family:"Poppins";font-weight:700;color:var(--verde-700);font-size:8pt;}

/* tarjetas de cifra */
.cards{display:flex; gap:10px; margin:10px 0;}
.card{flex:1; background:var(--azul-50); border:1px solid var(--azul-200);
  border-radius:14px; padding:10px 12px;}
.card .role{font-family:"Poppins"; font-weight:600; font-size:8.6pt; color:var(--azul-700);
  margin-bottom:3px; line-height:1.2;}
.card .n{font-family:"Poppins"; font-weight:800; font-size:18pt; color:var(--tinta-900); line-height:1;}
.card .n small{font-size:9pt; color:var(--gris-500); font-weight:600;}
.card .l{font-size:8.2pt; color:var(--gris-500); margin-top:4px; line-height:1.25;}
.card.green{background:var(--verde-50); border-color:var(--verde-200);}
.card.green .n{color:var(--verde-700);} .card.green .role{color:var(--verde-700);}
.card.amber{background:#FFF8EC; border-color:#F6D266;}
.card.amber .role{color:var(--naranja-500);}

/* callouts */
.box{border-radius:12px; padding:10px 14px; margin:10px 0; font-size:9.4pt;}
.box .t{font-family:"Poppins"; font-weight:600; margin-bottom:2px; font-size:9.8pt;}
.box.sponsor{background:#FFF8EC; border:1px solid #F6D266;} .box.sponsor .t{color:var(--naranja-500);}
.box.info{background:var(--azul-50); border:1px solid var(--azul-200);} .box.info .t{color:var(--azul-700);}
.box.note{background:var(--gris-100); border-left:4px solid var(--gris-400);} .box.note .t{color:var(--tinta-900);}
.box.future{background:var(--verde-50); border:1.5px solid var(--verde-500);} .box.future .t{color:var(--verde-700);}

.chip{display:inline-block; border-radius:999px; padding:1px 9px; font-size:8pt;
  font-weight:700; font-family:"Poppins"; color:#fff;}
.chip.bajo{background:var(--r-bajo);} .chip.medio{background:var(--r-medio);} .chip.alto{background:var(--r-alto);}

/* indice */
.toc{font-size:11pt; margin-top:12px;}
.toc a{display:block; margin:10px 0; break-inside:avoid; color:var(--tinta-700); text-decoration:none;}
.toc a:hover{color:var(--azul-700);}
.toc .tn{font-family:"Poppins"; font-weight:700; color:var(--azul-500); margin-right:9px;}

/* arquitectura visual */
.arch{margin:10px auto; max-width:600px;}
.arch .pill{display:inline-block; background:var(--azul-700); color:#fff; border-radius:999px;
  padding:6px 16px; font-family:"Poppins"; font-weight:600; font-size:9.2pt;}
.arch .center{text-align:center; margin:4px 0;}
.arch .down{text-align:center; color:var(--azul-400); font-size:14pt; line-height:.8; margin:1px 0;}
.arch .lay{display:flex; align-items:center; gap:12px; border:1.5px solid var(--azul-200);
  border-radius:13px; padding:9px 13px; margin:6px 0; background:var(--azul-50);}
.arch .lay .n{font-family:"Poppins"; font-weight:700; color:#fff; font-size:8.4pt;
  background:var(--azul-500); border-radius:999px; padding:3px 10px; white-space:nowrap;}
.arch .lay .d{font-size:9pt; flex:1;}
.arch .lay .o{font-size:8.4pt; color:var(--verde-700); font-weight:700; font-family:"Poppins";
  white-space:nowrap; text-align:right;}
.arch .split{display:flex; gap:10px; justify-content:center; margin-top:4px;}
.arch .out{background:#fff; color:var(--azul-700); border:1.5px solid var(--azul-400);}
hr{border:none; border-top:1px solid var(--gris-200); margin:12px 0;}
"""


def card(role, n, sub, l, cls=""):
    nn = f'{n} <small>{sub}</small>' if sub else n
    return (f'<div class="card {cls}"><div class="role">{role}</div>'
            f'<div class="n">{nn}</div><div class="l">{l}</div></div>')


HTML = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Memoria Técnica · Habli</title><style>{CSS}</style></head><body>

<!-- PORTADA -->
<div class="cover">
  <div class="glow"></div><div class="glow2"></div>
  <div class="cover-inner">
    <div class="logo-card"><img src="data:image/png;base64,{LOGO_COLOR}" alt="Habli"></div>
    <div class="kicker">Memoria Técnica · Hackatón IABiomed</div>
    <h1>Análisis de audio para el<br>cribado temprano del TDL</h1>
    <div class="sub">Un sistema ligero, honesto y con el profesional en el centro para detectar
    señales del Trastorno del Desarrollo del Lenguaje en niños de 3 a 6 años.</div>
    <div class="descriptor">&ldquo;Aprendiendo palabra a palabra&rdquo;</div>
    <div class="meta">
      <div class="row">
        <div style="flex:2">
          <b>Equipo</b>
          <div class="author"><span class="nm">Andrea López Guirado</span> &mdash;
            <span class="rl">Biomédica</span><br>
            <a href="https://www.linkedin.com/in/andrealopezguirado/">linkedin.com/in/andrealopezguirado</a></div>
          <div class="author"><span class="nm">Diego Esclarín Fernández</span> &mdash;
            <span class="rl">Ingeniero de IA</span><br>
            <a href="https://www.linkedin.com/in/diegoesclarinfernandez/">linkedin.com/in/diegoesclarinfernandez</a></div>
        </div>
        <div style="flex:1">
          <b>Reto</b><div class="rl" style="color:#eaf7fb">Blue Route · Salud digital</div>
          <b style="margin-top:11px">Fecha</b><div class="rl" style="color:#eaf7fb">15 de junio de 2026</div>
        </div>
      </div>
      <div class="repo"><b>Repositorio:</b>
        <a href="https://github.com/Di3g0E/Hackathon_IABiomed">github.com/Di3g0E/Hackathon_IABiomed</a></div>
    </div>
  </div>
  <div class="legal">&copy; 2026 Habli · Proyecto Blue Route. Cribado, no diagnóstico.</div>
</div>

<!-- INDICE (pagina propia) -->
<section style="page-break-after:always">
<h2 class="sec"><span class="sec-num">0.</span> Índice</h2>
<div class="toc">
  <a href="#s1"><span class="tn">1</span>Resumen ejecutivo</a>
  <a href="#s2"><span class="tn">2</span>Contexto y problema</a>
  <a href="#s3"><span class="tn">3</span>El reto y los datos</a>
  <a href="#s4"><span class="tn">4</span>Arquitectura de la solución</a>
  <a href="#s5"><span class="tn">5</span>Metodología y métricas</a>
  <a href="#s6"><span class="tn">6</span>Resultados del reto (T1, T2, T3)</a>
  <a href="#s7"><span class="tn">7</span>La aplicación Habli</a>
  <a href="#s8"><span class="tn">8</span>Recursos y viabilidad móvil</a>
  <a href="#s9"><span class="tn">9</span>Limitaciones y líneas futuras</a>
  <a href="#s10"><span class="tn">10</span>Conclusiones, herramientas de IA y reproducibilidad</a>
</div>
</section>

<!-- 1. RESUMEN -->
<section id="s1">
<h2 class="sec"><span class="sec-num">1.</span> Resumen ejecutivo</h2>
<p class="sec-lead">Qué se pedía, qué hemos construido y por qué importa.</p>

<p>Partiendo de audios de <b>32 palabras</b> (lista de evaluación fonológica de Laura Bosch, repositorio
público Forvo), hemos resuelto las <b>tres tareas del reto</b> y, sobre ellas, hemos construido una
<b>aplicación de cribado</b> que materializa el objetivo de Blue Route: detectar de forma temprana el
<b>Trastorno del Desarrollo del Lenguaje (TDL)</b> mientras el niño juega a nombrar dibujos.</p>

<div class="cards">
  {card("Fonemas (T1)", "0,86", "F1", "Reconoce qué dice el niño (núcleo clínico). Cuantizado a int8: <b>&minus;72% de tamaño</b> y <b>3&times; más rápido</b> sin perder calidad.", "green")}
  {card("Edad", "3&ndash;6", "años", "<b>La priorizamos:</b> es la variable que más pesa en el riesgo. Estimada y editable por la familia.", "amber")}
  {card("Sexo (T3)", "0,85", "F1", "Perfil del niño. ECAPA ligero (~6 MB), mejor que el método clásico (0,74).")}
  {card("Origen (T2)", "0,62", "F1", "Solo sugerencia editable; no decide nada en el cribado.")}
</div>

<p><b>Qué hace la aplicación.</b> Permite realizar una prueba de habla para detectar señales de TDL;
según el <b>nivel de riesgo</b> (que depende en gran medida de la <b>edad del niño</b>), <b>deriva al
especialista</b> y <b>recomienda ejercicios de mejora</b> elegidos a partir de los <b>fallos cometidos
durante la prueba</b> y la <b>edad</b>. Guarda el histórico para seguir su evolución.</p>

<h4>Honestidad clínica (en pocas palabras)</h4>
<ul>
<li><b>Cribado, no diagnóstico.</b> Medimos el <b>habla</b>; si algo no cuadra, avisamos para que lo
valore un logopeda. Nunca damos un diagnóstico.</li>
<li><b>Cuando el modelo no está seguro, preguntamos.</b> Donde la señal es débil (el origen) o delicada
(el sexo en niños), el sistema sugiere y deja que la persona confirme o corrija. El profesional manda.</li>
<li><b>Lo ligero es lo importante.</b> Usamos modelos ya entrenados y muy livianos, pensados para que
todo funcione en un móvil y de forma económica.</li>
</ul>
</section>

<!-- 2. CONTEXTO -->
<section id="s2">
<h2 class="sec"><span class="sec-num">2.</span> Contexto y problema</h2>
<p class="sec-lead">Por qué el cribado temprano del TDL necesita una solución ligera.</p>
<p>El <b>TDL</b> afecta a cerca del <b>7% de los niños</b>. Se distingue hacia los 3 años y se diagnostica
con precisión entre los 4 y 5. Detectarlo pronto es decisivo, pero el diagnóstico exige un profesional y
hay poca disponibilidad, sobre todo en el <b>medio rural</b>. La app de <b>Blue Route</b> conecta familias
y clínicas a lo largo de cuatro pasos: <b>Registro &rarr; Screening &rarr; Pruebas de audio &rarr; Terapia</b>.
El <b>cuello de botella</b> es que la evaluación del habla depende de un logopeda; nuestra pieza es el
<b>modelo de audio</b> que automatiza parte de ese trabajo. El test de Bosch &mdash;nombrar dibujos de 32
palabras que cubren todo el sistema fonológico&mdash; es la prueba más temprana y sencilla para un niño pequeño.</p>
</section>

<!-- 3. DATOS -->
<section id="s3">
<h2 class="sec"><span class="sec-num">3.</span> El reto y los datos</h2>
<p class="sec-lead">Tres tareas sobre un conjunto pequeño y desbalanceado &mdash; el sesgo es parte del desafío.</p>
<p><b>Las tres tareas:</b> <b>T1</b> identificar los fonemas de cada palabra, <b>T2</b> clasificar el
origen (España / Latinoamérica / No nativo) y <b>T3</b> el sexo. El reto valora precisión/recall/F1, pero
también <b>tiempo, recursos y facilidad de integrar en una app</b> &rarr; premia lo ligero.</p>
<p><b>Los datos:</b> <b>227 audios</b> de 32 palabras, <b>142 hablantes</b>, duración media <b>0,82 s</b>.
Los metadatos salen del nombre del archivo (sin anotación manual). Hay <b>desbalances reales</b>: sexo
178 H / 49 M; origen Latam 115 / España 97 / No nativo 15 (clase minúscula y con un sesgo: 8 de sus 15
clips son la palabra <span class="small">piedra</span>). Validamos <b>por hablante</b>
(StratifiedGroupKFold): como las 32 palabras se repiten entre personas, un reparto al azar inflaría las
cifras. Forvo es nuestro <b>test</b>; el entrenamiento puede ampliarse con <b>OpenSLR Latinoamérica</b> (gratis).</p>
</section>

<!-- 4. ARQUITECTURA -->
<section class="pb" id="s4">
<h2 class="sec"><span class="sec-num">4.</span> Arquitectura de la solución</h2>
<p class="sec-lead">De un vistazo: del audio del niño a dos vistas, según quién mira.</p>

<div class="arch avoid">
  <div class="center"><span class="pill">🎤 Audio del niño · 32 palabras</span></div>
  <div class="down">&#9660;</div>
  <div class="lay"><span class="n">Capa 1</span><span class="d"><b>Análisis de audio.</b> Modelos
    preentrenados congelados + clasificadores ligeros.</span><span class="o">&rarr; fonemas · edad · sexo/origen</span></div>
  <div class="down">&#9660;</div>
  <div class="lay"><span class="n">Capa 2</span><span class="d"><b>Motor clínico.</b> Compara con la
    referencia de Bosch; detecta procesos y calcula el riesgo.</span><span class="o">&rarr; procesos · PCC · riesgo por edad</span></div>
  <div class="down">&#9660;</div>
  <div class="lay"><span class="n">Capa 3</span><span class="d"><b>Aplicación (2 agentes).</b>
    LangGraph + Groq sobre FastAPI; histórico en SQLite.</span><span class="o">&rarr; experiencia + informe</span></div>
  <div class="down">&#9660;</div>
  <div class="split">
    <span class="pill out">👨‍👩‍👧 Familia (Lali): nivel + ejercicios</span>
    <span class="pill out">🩺 Logopeda: informe + PDF</span>
  </div>
</div>

<p class="small">Detalle por capa. <b>Capa 1</b> — T1 con reconocimiento fonético (wav2vec2), T2/T3 con
embeddings de hablante (ECAPA) + regresión logística, y estimación de edad; todo cacheado y reutilizable.
<b>Capa 2</b> — alineamiento niño↔referencia, detección de procesos fonológicos, PCC y nivel de riesgo por
edad, con decodificación restringida (sabemos qué palabra se pide) y guardián de validez. <b>Capa 3</b> —
dos grafos conversacionales: la familia ve un mensaje simple; el logopeda, los datos. El audio se procesa
en local y <b>nunca</b> se envía al modelo de lenguaje.</p>
</section>

<!-- 5. METODOLOGIA -->
<section id="s5">
<h2 class="sec"><span class="sec-num">5.</span> Metodología y métricas</h2>
<p class="sec-lead">Por qué decidimos así, dado el hardware y los criterios del reto.</p>

<h4>Modelos congelados + clasificadores ligeros</h4>
<p>Con una GPU de <b>4 GB</b>, entrenar modelos grandes es inviable y va contra el criterio de
<b>mínimos recursos</b>. Usamos los modelos preentrenados como <b>extractores congelados</b> y entrenamos
encima clasificadores de kilobytes (entrenan en milisegundos). Así el sistema es desplegable en un móvil.</p>

<h4>Priorizamos la edad</h4>
<p>El reto pedía fonemas, origen y sexo. Pero para el caso clínico la variable <b>más relevante es la
edad</b>: es la que fija el umbral de riesgo (lo normal a los 3 años no lo es a los 5). Aunque también
predecimos origen y sexo, <b>hemos priorizado la edad</b> en el análisis y la dejamos siempre editable
por la familia.</p>

<h4>Por qué estas métricas</h4>
<p>Usamos <b>F1 macro</b> en vez de <i>accuracy</i> porque con clases desbalanceadas la <i>accuracy</i>
premia acertar la clase mayoritaria; el F1 macro mide bien las minoritarias. Para fonemas usamos el
<b>PER</b> (error fonema a fonema, estándar en reconocimiento del habla) y, para la lectura clínica, el
<b>PCC</b> (porcentaje de consonantes correctas), que los logopedas reconocen al instante.</p>

<h4>Aceptamos el acento en vez de &ldquo;corregirlo&rdquo;</h4>
<p>La misma palabra suena distinta en España y en Latinoamérica (p. ej. el seseo). En vez de montar un
detector de acento que reescriba los fonemas &mdash;y arriesgarnos a equivocarnos&mdash;, tratamos esas
variantes como <b>equivalentes</b>. Resultado: el reconocedor acierta <b>igual de bien en todos los
orígenes</b>, así que <b>no hay sesgo por acento</b> (lo comprobamos en la &sect;6).</p>
</section>

<!-- 6. RESULTADOS -->
<section class="pb" id="s6">
<h2 class="sec"><span class="sec-num">6.</span> Resultados del reto (T1, T2, T3)</h2>
<p class="sec-lead">Cada tarea, con su mejora frente al modelo anterior. <span class="flag">En negrita, el modelo que usamos.</span></p>

<h4>T1 &mdash; Reconocimiento de fonemas <span class="small">(núcleo del valor clínico)</span></h4>
<table class="avoid">
<thead><tr><th>Modelo</th><th>F1 &uarr; (mejor &uarr;)</th><th>PER &darr; (mejor &darr;)</th><th></th></tr></thead>
<tbody>
<tr class="chosen"><td><b>wav2vec2-xlsr-espeak</b></td><td class="hi">0,862</td><td class="hi">0,174</td><td class="flag">✓ usado · +0,21 F1</td></tr>
<tr><td>Allosaurus (anterior)</td><td>0,655</td><td>0,433</td><td class="small">más lento, CPU</td></tr>
</tbody>
<caption>Lo elegimos por mucha mejor calidad. Auditoría de equidad: F1 España 0,852 · Latam 0,865 · No nativo 0,907 → sin sesgo dialectal.</caption>
</table>

<h4>T3 &mdash; Clasificación de sexo</h4>
<table class="avoid">
<thead><tr><th>Modelo</th><th>F1 macro &uarr;</th><th>Coste / tamaño</th><th></th></tr></thead>
<tbody>
<tr><td>F0 (tono) + LogReg (anterior)</td><td>0,742</td><td>mínimo</td><td class="small">flojo en mujer</td></tr>
<tr><td>XLS-R + LogReg</td><td>0,815</td><td>~1,2 GB</td><td class="small">bueno pero pesado</td></tr>
<tr class="chosen"><td><b>ECAPA-TDNN + LogReg</b></td><td class="hi">0,85</td><td class="hi">~6 MB</td><td class="flag">✓ usado · +0,11 vs F0</td></tr>
</tbody>
<caption>Lo elegimos porque es el mejor F1 <b>y</b> el más ligero (60&times; menos que XLS-R).</caption>
</table>

<h4>T2 &mdash; Clasificación de origen</h4>
<table class="avoid">
<thead><tr><th>Características</th><th>España vs Latam · F1 &uarr;</th><th>3 clases · F1 &uarr;</th></tr></thead>
<tbody>
<tr><td>MFCC + tono (anterior)</td><td>0,542</td><td>0,388</td></tr>
<tr><td>ECAPA-TDNN <span class="small">(desplegado, ligero)</span></td><td>0,575</td><td>0,408</td></tr>
<tr class="chosen"><td><b>XLS-R-300m</b> <span class="small">(mejor cifra)</span></td><td class="hi">0,608 (voto 0,62)</td><td>0,515</td></tr>
</tbody>
<caption>El acento desde una palabra suelta es muy difícil; el resultado es modesto pero por encima del azar.</caption>
</table>
<p><b>Por eso el 0,62 no afecta al cribado:</b> el origen <u>no decide nada</u>. Es un dato de registro
que la familia confirma; el modelo solo <b>sugiere</b> y, si no está seguro, <b>pregunta</b>
(<i>human-in-the-loop</i>). El cribado se apoya en los fonemas (F1 0,86, sin sesgo), no en el origen.</p>
</section>

<!-- 7. APP -->
<section id="s7">
<h2 class="sec"><span class="sec-num">7.</span> La aplicación Habli</h2>
<p class="sec-lead">El flujo de Blue Route, hecho producto, con dos caras de la misma marca.</p>

<p>Sobre el motor clínico construimos la app con <b>LangGraph + Groq</b> y <b>FastAPI</b>. El
<b>núcleo clínico</b> compara la producción del niño con la <b>referencia de Bosch</b>, clasifica cada
desviación en un <b>proceso fonológico</b> (reducción de grupos, omisiones…), calcula el <b>PCC</b> con
severidad y emite un <b>nivel de riesgo por edad</b> (<span class="chip bajo">Bajo</span>
<span class="chip medio">Medio</span> <span class="chip alto">Alto</span>). Como sabemos qué palabra se
pide, la <b>decodificación restringida</b> baja el error de fonemas de <b>0,36 a 0,11</b>, y un
<b>guardián de validez</b> evita contar como correcta una palabra que el niño no dijo.</p>

<h4>Dos agentes, dos públicos</h4>
<ul>
<li><b>Familia (Lali):</b> conduce el juego (Registro &rarr; Prueba &rarr; Resultado &rarr; Ejercicios
&rarr; Envío) y muestra <u>solo un nivel y una recomendación</u>, nunca cifras ni diagnóstico.</li>
<li><b>Logopeda:</b> ve los datos (PCC, procesos, timeline de fonemas <b>editable</b>), <b>re-puntúa</b>
con su criterio y descarga un <b>informe PDF</b> con la evolución (prueba 1 vs 2).</li>
</ul>
<p><b>Derivación y ejercicios.</b> Según riesgo &times; edad, la app <b>deriva al especialista</b> y
propone <b>ejercicios de mejora</b> (no terapia) elegidos por los <b>fallos de la prueba</b> y la
<b>edad</b>, con plan de seguimiento (180 / 42 / 21 días) e <b>histórico</b> para ver la persistencia.</p>

<div class="box info"><div class="t">Privacidad por diseño (RGPD)</div>
La voz del niño es un dato de salud sensible: se procesa <b>en local</b> y <b>nunca</b> se envía al modelo
de lenguaje (que solo recibe fonemas y métricas). Las cifras las calcula el motor; el LLM solo redacta.
Sin clave de API, el flujo sigue funcionando de forma determinista.</div>
</section>

<!-- 8. RECURSOS -->
<section id="s8">
<h2 class="sec"><span class="sec-num">8.</span> Recursos y viabilidad móvil</h2>
<p class="sec-lead">Respuesta al patrocinador: un pipeline potente que sigue siendo viable y económico.</p>

<h4>Cuantización INT8 del modelo más pesado (reconocedor)</h4>
<table class="avoid">
<thead><tr><th>Versión</th><th>Tamaño &darr;</th><th>PER &darr;</th><th>F1 &uarr;</th><th>Latencia &darr;</th></tr></thead>
<tbody>
<tr><td>Completa fp32 (servidor)</td><td>1205 MB</td><td>0,205</td><td>0,834</td><td>304 ms</td></tr>
<tr class="chosen"><td><b>INT8 (móvil)</b></td><td class="hi">338 MB</td><td class="hi">0,187</td><td class="hi">0,845</td><td class="hi">101 ms</td></tr>
<tr><td>Mejora</td><td class="flag">&minus;72%</td><td>+</td><td>+</td><td class="flag">3,0&times;</td></tr>
</tbody>
<caption>La calidad se mantiene. El modelo de edad mejora igual (&minus;72%, 3,8&times;).</caption>
</table>
<p>Además: detectores de sexo/origen <b>ECAPA ligeros (~6 MB)</b>; arquitectura <b>híbrida</b> &mdash;int8
en el móvil para el juego, modelo completo en servidor solo para el informe&mdash;; y <b>coste de LLM
acotado</b> (las cifras las calcula el motor, no se pagan tokens por ellas).</p>

<h4>Stack tecnológico</h4>
<table class="avoid">
<thead><tr><th>Pieza</th><th>Caso óptimo (lo que desplegamos)</th><th>También probado</th></tr></thead>
<tbody>
<tr><td>Fonemas (T1)</td><td><b>wav2vec2-xlsr-espeak (int8)</b></td><td>Allosaurus</td></tr>
<tr><td>Sexo / Origen (T3/T2)</td><td><b>ECAPA-TDNN + LogReg</b></td><td>XLS-R-300m, MFCC, F0</td></tr>
<tr><td>Edad</td><td><b>audeering age (int8)</b></td><td>—</td></tr>
<tr><td>Voz / calidad</td><td><b>Silero-VAD (on-device)</b></td><td>VAD por energía</td></tr>
<tr><td>App / agentes</td><td><b>LangGraph + Groq · FastAPI · SQLite · FPDF2</b></td><td>fallback determinista</td></tr>
<tr><td>Adaptación infantil</td><td>—</td><td>LoRA (andamiaje), pitch-shift</td></tr>
<tr><td>Entorno</td><td><b>Python 3.11 · uv · PyTorch CUDA 12.4</b></td><td>—</td></tr>
</tbody></table>
</section>

<!-- 9. LIMITACIONES -->
<section id="s9">
<h2 class="sec"><span class="sec-num">9.</span> Limitaciones y líneas futuras</h2>
<p class="sec-lead">Honestidad sobre lo que falta &mdash; es justo lo que valora el jurado.</p>

<div class="box future avoid"><div class="t">⚠ Limitación principal &mdash; y su solución de futuro</div>
<b>No existe</b> audio infantil en español con estas 32 palabras ni con etiqueta de TDL, y los modelos
estándar (entrenados con adultos) fallan más con niños: lo medimos &mdash; el error de fonemas pasa de
<b>0,17 en adultos a 0,29 en niños</b>. <b>Lo reconocemos abiertamente.</b><br>
<b>Solución ya preparada:</b> con <b>permiso</b> de la familia, guardamos las grabaciones asociadas
<b>solo a la edad, el sexo y la región</b> &mdash;las etiquetas que sirven para <b>entrenar y mejorar
los modelos</b>&mdash; y <b>nunca</b> información que identifique directamente al niño. Con esos datos, y
junto a la <b>Clínica Pediátrica Amado</b>, podremos adaptar el reconocedor a la voz infantil real
(tenemos el andamiaje de <i>fine-tuning</i> listo).</div>

<p><b>Cómo lidiamos ya con muestras pequeñas y sesgadas</b> (parte del desafío): validación por hablante;
F1 macro y auditoría de equidad; reportamos el sesgo de <i>No nativo</i> como no fiable en vez de maquillar
la cifra; y <i>human-in-the-loop</i> donde la señal es débil. <b>Otras líneas futuras:</b> validación
clínica frente a logopeda (sensibilidad/especificidad), encaje regulatorio (producto sanitario, marcado CE)
y marcadores de lenguaje (repetición de frases). <b>Otras limitaciones:</b> taxonomía acotada a 8 procesos
y referencia fonémica generada con apoyo de IA (pendiente de validación final del logopeda).</p>
</section>

<!-- 10. CONCLUSIONES -->
<section id="s10">
<h2 class="sec"><span class="sec-num">10.</span> Conclusiones, herramientas de IA y reproducibilidad</h2>
<p class="sec-lead">Qué entregamos, con qué nos apoyamos y cómo se ejecuta.</p>

<p>Hemos resuelto las <b>tres tareas del reto</b> con métricas honestas (validación por hablante, sin sesgo
dialectal, coste medido) y, más allá del reto, entregamos una <b>aplicación completa</b> de cribado:
temprana, ligera, con privacidad por diseño y con el profesional en el centro.</p>

<h4>Herramientas de IA que hemos usado</h4>
<ul>
<li><b>En la solución:</b> wav2vec2-xlsr-espeak (fonemas), ECAPA-TDNN (sexo/origen), audeering (edad),
Silero-VAD, y un LLM vía Groq/LangGraph que solo redacta (nunca ve el audio).</li>
<li><b>De apoyo en el desarrollo:</b> <b>Claude Code</b> como asistente de programación (arquitectura,
implementación, auditorías y documentación) y <b>Nano Banana</b> para generar las imágenes de la app.
Todas las decisiones técnicas y clínicas las revisamos y validamos nosotros.</li>
</ul>

<h4>Reproducibilidad</h4>
<p>Código completo en <b><a href="https://github.com/Di3g0E/Hackathon_IABiomed">github.com/Di3g0E/Hackathon_IABiomed</a></b>
(entorno con <span class="small">uv</span>, Python 3.11, PyTorch CUDA 12.4; detalles en el README):</p>
<table class="avoid">
<thead><tr><th>Comando</th><th>Qué hace</th></tr></thead>
<tbody>
<tr><td class="small">uv run python src/scripts/1_preparar_datos.py</td><td>Metadatos + preprocesado + EDA</td></tr>
<tr><td class="small">uv run python src/scripts/4_fonemas.py</td><td>T1 fonemas (wav2vec2 vs Allosaurus)</td></tr>
<tr><td class="small">uv run python src/scripts/2_sexo.py · 3_origen.py</td><td>T3 sexo · T2 origen (+ confianza)</td></tr>
<tr><td class="small">uv run python src/scripts/5_procesos.py · 6_validacion_infantil.py</td><td>Procesos + PCC · domain gap infantil</td></tr>
</tbody></table>

<hr>
<div style="display:flex; align-items:center; gap:16px; margin-top:10px;">
  <img src="data:image/png;base64,{ICONO}" style="width:58px;height:58px;border-radius:15px;">
  <div><div style="font-family:'Poppins';font-weight:700;font-size:12pt;color:var(--tinta-900);">Habli · Jugamos, hablamos y aprendemos</div>
  <div class="small">Proyecto Blue Route · Hackatón IABiomed 2026 · Cribado, no diagnóstico.</div></div>
</div>
</section>

</body></html>
"""

OUT_HTML.write_text(HTML, encoding="utf-8")
print("HTML:", OUT_HTML, f"({len(HTML)} bytes)")

# --- render con Chrome headless ---
TMP_PDF.unlink(missing_ok=True)
subprocess.run([str(CHROME), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                "--no-sandbox", "--virtual-time-budget=15000",
                "--run-all-compositor-stages-before-draw",
                f"--print-to-pdf={TMP_PDF}", OUT_HTML.as_uri()],
               check=True, capture_output=True)

# --- estampar pie + numeracion (todas menos la portada) ---
n_pag = len(pypdf.PdfReader(str(TMP_PDF)).pages)
ov = FPDF(orientation="P", unit="mm", format="A4")
ov.set_auto_page_break(False)  # si no, dibujar a 285mm inserta paginas extra y desalinea
ov.add_font("DejaVu", "", str(DEJAVU))
for i in range(n_pag):
    ov.add_page()
    if i == 0:
        continue  # portada sin pie
    ov.set_draw_color(217, 227, 232)
    ov.line(16, 284, 194, 284)
    ov.set_font("DejaVu", "", 7)
    ov.set_text_color(147, 167, 178)
    ov.set_xy(16, 285)
    ov.cell(120, 5, "© 2026 Habli · Proyecto Blue Route · Cribado, no diagnóstico.")
    ov.set_xy(120, 285)
    ov.cell(74, 5, f"Página {i + 1} de {n_pag}", align="R")
ov.output(str(OVERLAY))

# clone_from preserva enlaces internos del indice y URIs; merge_page solo aniade el pie encima
w = pypdf.PdfWriter(clone_from=str(TMP_PDF))
pie = pypdf.PdfReader(str(OVERLAY))
for i, page in enumerate(w.pages):
    page.merge_page(pie.pages[i])
OUT_PDF.unlink(missing_ok=True)
with open(OUT_PDF, "wb") as f:
    w.write(f)
TMP_PDF.unlink(missing_ok=True)
OVERLAY.unlink(missing_ok=True)
print("PDF:", OUT_PDF, f"({n_pag} páginas)")
