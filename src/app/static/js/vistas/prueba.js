// La prueba (el "juego de palabras"). Modo niño: una acción por pantalla,
// fondo monocromo que se vuelve VERDE cuando toca hablar (sin cuenta atrás),
// refuerzo siempre positivo (nunca se marca el fallo al niño).
//
// Ciclo por palabra: MOSTRAR -> CUE_VERDE -> GRABANDO -> SUBIENDO -> OK | REPETIR(1).

import * as api from "../api.js";
import * as estado from "../estado.js";
import * as grabacion from "../grabacion.js";
import * as sonido from "../sonido.js";
import { tarjetaResultado } from "../lali.js";

const MASCOTA = "/static/brand/lali-mascota.png";
// flecha gorda y visual (para un niño pequeño)
const FLECHA_VOLVER = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
  stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>`;
const DUR_GRABACION_MS = 3500;
const PRE_ROLL_MS = 300;
const CELEBRA = ["¡Toma ya!", "¡Genial!", "¡Qué bien lo haces!", "¡Súper!", "¡Sigue así!", "¡Eres un campeón!"];
const REPITE = [
  "¡Uy, no te he oído bien! ¿Me lo dices otra vez más cerquita?",
  "¡Casi casi! Dímelo otra vez, un poquito más fuerte.",
];

let cancelado = false;
let temporizadores = [];
// sesión en curso: si se abandona a medias, los audios se DESCARTAN sin analizar
// (las copias anónimas de entrenamiento, si hubo consentimiento, ya están guardadas)
let sesion = null;
let botonSonido = null;   // botón de sonido SOLO durante la prueba (esquina sup. dcha.)

function montarBotonSonido() {
  if (botonSonido) return;
  botonSonido = document.createElement("button");
  botonSonido.className = "btn-mute btn-mute--prueba";
  botonSonido.setAttribute("aria-label", "Activar o silenciar el sonido");
  const pinta = () => { botonSonido.textContent = sonido.silenciado() ? "🔇" : "🔊"; };
  pinta();
  botonSonido.addEventListener("click", () => { sonido.alternarSilencio(); pinta(); });
  document.body.appendChild(botonSonido);
}

function quitarBotonSonido() {
  botonSonido?.remove();
  botonSonido = null;
}

function espera(ms) {
  return new Promise((res) => temporizadores.push(setTimeout(res, ms)));
}

function enCurso() {
  return Boolean(sesion && sesion.subidas > 0 && !sesion.terminada);
}

function abandonarSiProcede() {
  if (!enCurso()) return;
  api.abandonarPruebaBeacon(sesion.ninoId, sesion.ronda);
  sesion = null;
}

function alCerrarPagina() {
  abandonarSiProcede();
}

export function desmontar() {
  cancelado = true;
  temporizadores.forEach(clearTimeout);
  temporizadores = [];
  grabacion.liberar();
  abandonarSiProcede();
  quitarBotonSonido();
  window.removeEventListener("pagehide", alCerrarPagina);
  document.body.classList.remove("modo-nino", "fase-verde", "fase-celebracion");
}

export async function render(cont) {
  cancelado = false;
  document.body.classList.add("modo-nino");
  montarBotonSonido();              // control de sonido visible solo en la prueba
  const ninoId = estado.getNinoId();

  // palabras: las que dejó preparadas el chat (incluida la ronda extra) o, desde el
  // menú, POST /prueba/iniciar (fija el nº de prueba y vacía palabras acumuladas)
  let datos = estado.tomarPruebaPendiente();
  if (!datos?.palabras?.length) {
    datos = await api.iniciarPrueba(ninoId);
  }
  const ronda = datos.ronda === "repeticion" ? "repeticion" : "principal";
  sesion = { ninoId, ronda, subidas: 0, terminada: false };
  window.addEventListener("pagehide", alCerrarPagina);

  paso1Nivel(cont, ninoId, datos.palabras, ronda);
}

// ---------------------------------------------------------------- paso 1: nivel
function paso1Nivel(cont, ninoId, palabras, ronda) {
  cont.innerHTML = `
    <div class="prueba anima-aparece">
      <button class="btn-volver prueba__salir" id="salir" aria-label="Volver">${FLECHA_VOLVER}</button>
      <h1>¿Cómo quieres jugar?</h1>
      <div class="niveles">
        <button class="nivel-card" data-nivel="1">
          <span class="emoji">🖼️🔤🔊</span>
          <span class="titulo">Nivel 1</span>
          <span class="pista">Veo el dibujo, leo la palabra y la escucho</span>
        </button>
        <button class="nivel-card" data-nivel="2">
          <span class="emoji">🔤</span>
          <span class="titulo">Nivel 2</span>
          <span class="pista">¡A leer! Solo la palabra escrita, sin dibujo</span>
        </button>
      </div>
    </div>`;

  cont.querySelector("#salir").addEventListener("click", () => { location.hash = "#/home"; });
  cont.querySelectorAll(".nivel-card").forEach((b) =>
    b.addEventListener("click", () => {
      estado.setNivel(Number(b.dataset.nivel));
      paso2Micro(cont, ninoId, palabras, ronda);
    }));
}

// ---------------------------------------------------------------- paso 2: micrófono
async function paso2Micro(cont, ninoId, palabras, ronda) {
  cont.innerHTML = `
    <div class="prueba anima-aparece">
      <div class="h-card" style="max-width:480px">
        <h2>Un momento, familia 👋</h2>
        <p>Para jugar necesitamos el <strong>micrófono</strong>. La voz del peque se
        analiza en este equipo y <strong>no se envía al asistente</strong>.</p>
        <p class="texto-secundario">Mejor en un sitio tranquilo y con el micro cerca.</p>
        <button class="h-btn h-btn--juego" id="permitir">🎤 Activar el micro</button>
      </div>
      <div style="display:flex;align-items:center;gap:12px;max-width:480px;margin-top:16px">
        <img src="${MASCOTA}" alt="" style="width:64px;flex:none">
        <div class="bocadillo bocadillo--lado" style="font-size:16px;padding:12px 16px">
          🎧 ¡Consejo de Lali! Mejor con <strong>cascos o auriculares</strong> para oírme
          bien y que no se cuele el sonido en el micro.
        </div>
      </div>
    </div>`;

  cont.querySelector("#permitir").addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    try {
      await grabacion.iniciar();
      buclePalabras(cont, ninoId, palabras, ronda);
    } catch (e) {
      const esPermiso = e.name === "NotAllowedError" || e.name === "PermissionDeniedError";
      cont.querySelector(".h-card").innerHTML = `
        <h2>No encontramos el micro 🙈</h2>
        <p>${esPermiso
          ? "El navegador no tiene permiso. Pulsa el icono del candado (junto a la dirección), permite el micrófono y vuelve a intentarlo."
          : `No se pudo abrir el micrófono (${e.message}).`}</p>
        <button class="h-btn" onclick="location.reload()">Reintentar</button>
        <button class="h-btn h-btn--fantasma" onclick="location.hash='#/home'">Volver</button>`;
    }
  });
}

// ---------------------------------------------------------------- paso 3: bucle de palabras
async function buclePalabras(cont, ninoId, palabras, ronda) {
  const nivel = estado.getNivel();
  let estrellas = 0;

  for (let i = 0; i < palabras.length && !cancelado; i++) {
    const palabra = palabras[i];
    let registro = await ciclo(cont, ninoId, palabra, { nivel, i, total: palabras.length, estrellas, ronda, reintentada: false });
    if (cancelado) return;
    if (registro && necesitaRepetir(registro)) {
      await pantallaRepite(cont);
      if (cancelado) return;
      registro = await ciclo(cont, ninoId, palabra, { nivel, i, total: palabras.length, estrellas, ronda, reintentada: true });
      if (cancelado) return;
    }
    // tras el (re)intento se avanza SIEMPRE celebrando: el niño nunca percibe fallo
    estrellas++;
    await pantallaCelebra(cont, { i, total: palabras.length, estrellas });
    if (cancelado) return;
  }

  if (sesion) sesion.terminada = true;   // prueba completa: ya no se descarta
  grabacion.liberar();
  if (!cancelado) celebracionFinal(cont, ninoId, ronda);
}

function necesitaRepetir(registro) {
  if (registro.reintentada) return false;
  return registro.valida === false || Boolean(registro.calidad?.motivo);
}

function plantillaPrueba(cont, { i, total, estrellas }) {
  cont.innerHTML = `
    <div class="prueba">
      <button class="btn-volver prueba__salir" id="salir" aria-label="Salir del juego">${FLECHA_VOLVER}</button>
      <div class="prueba__progreso progreso-estrellas" aria-label="Progreso: ${estrellas} de ${total}">
        ${Array.from({ length: total }, (_, k) => `<span class="${k < estrellas ? "llena" : ""}">⭐</span>`).join("")}
      </div>
      <div data-zona style="display:flex;flex-direction:column;align-items:center;gap:24px;width:100%"></div>
    </div>`;
  cont.querySelector("#salir").addEventListener("click", () => {
    if (confirm("¿Seguro que queréis salir del juego? Las palabras grabadas se "
        + "descartarán y no se analizará nada. (pregunta para el adulto)")) {
      location.hash = "#/home";   // al salir, el router descarta la sesión a medias
    }
  });
  return cont.querySelector("[data-zona]");
}

async function ciclo(cont, ninoId, palabra, ctx) {
  const zona = plantillaPrueba(cont, ctx);

  // --- MOSTRAR: Nivel 1 = dibujo + palabra + voz · Nivel 2 = solo la palabra escrita ---
  document.body.classList.remove("fase-verde");
  zona.innerHTML = ctx.nivel === 1
    ? `<div class="palabra-card anima-aparece">
         <img class="dibujo" src="${api.urlImagenPalabra(palabra)}"
              onerror="this.onerror=null;this.src='${api.IMAGEN_PLACEHOLDER}'" alt="${palabra}">
         <div class="palabra-texto">${palabra}</div>
         <button class="btn-altavoz" id="oir" aria-label="Escuchar la palabra">🔊</button>
       </div>`
    : `<div class="palabra-card palabra-card--texto anima-aparece">
         <div class="palabra-texto palabra-texto--grande">${palabra}</div>
       </div>`;

  if (ctx.nivel === 1) {
    const reproducir = () => reproducirClip(palabra);
    zona.querySelector("#oir").addEventListener("click", reproducir);
    await reproducir();
    await espera(700);
  } else {
    await espera(1500);
  }
  if (cancelado) return null;

  // --- CUE VERDE: el fondo se vuelve verde = ¡habla ahora! (sin 3-2-1) ---
  document.body.classList.add("fase-verde");
  zona.innerHTML = `
    <div class="cue-hablar anima-aparece"><span class="mic">🎤</span> ¡Ahora tú!</div>
    <div class="anillo" id="anillo"><div class="interior">🎤</div></div>
    <button class="h-btn h-btn--fantasma" id="cortar" style="background:rgba(255,255,255,.6)">Ya está</button>`;
  await espera(PRE_ROLL_MS);
  if (cancelado) return null;

  // --- GRABANDO ---
  grabacion.empezar();
  const anillo = zona.querySelector("#anillo");
  await new Promise((fin) => {
    const t0 = performance.now();
    const intervalo = setInterval(() => {
      const p = Math.min(100, ((performance.now() - t0) / DUR_GRABACION_MS) * 100);
      anillo?.style.setProperty("--p", p);
      if (p >= 100 || cancelado) { clearInterval(intervalo); fin(); }
    }, 100);
    temporizadores.push(intervalo);
    zona.querySelector("#cortar").addEventListener("click", () => { clearInterval(intervalo); fin(); });
  });
  const blob = grabacion.parar();
  document.body.classList.remove("fase-verde");
  if (cancelado) return null;

  // --- SUBIENDO: sin pantalla nueva (cambiar tanto confunde): se mantiene el dibujo
  // de la palabra con los puntos animados debajo mientras se analiza ---
  zona.innerHTML = `
    <div class="palabra-card">
      <img class="dibujo" src="${api.urlImagenPalabra(palabra)}"
           onerror="this.onerror=null;this.src='${api.IMAGEN_PLACEHOLDER}'" alt="${palabra}">
      <span class="pensando" aria-label="Analizando"><span></span><span></span><span></span></span>
    </div>`;
  try {
    const registro = await api.subirAudio(palabra, blob, ninoId, { reintentada: ctx.reintentada, ronda: ctx.ronda });
    if (sesion) sesion.subidas++;
    return registro;
  } catch (e) {
    // si el servidor falla, no se bloquea el juego: se avanza sin repetir
    console.error("Error subiendo audio:", e);
    return { valida: true, calidad: {}, error: e.message };
  }
}

async function reproducirClip(palabra) {
  try {
    const audio = new Audio(api.urlAudioPalabra(palabra));
    await new Promise((fin) => {
      audio.addEventListener("ended", fin, { once: true });
      audio.addEventListener("error", fin, { once: true });
      temporizadores.push(setTimeout(fin, 4000)); // tope por si el clip no carga
      audio.play().catch(fin);
    });
  } catch { /* sin clip: el juego sigue */ }
}

async function pantallaRepite(cont) {
  const zona = cont.querySelector("[data-zona]");
  zona.innerHTML = `
    <div class="palabra-card anima-aparece">
      <p style="font-size:24px;font-weight:800;color:var(--habli-tinta-900);margin:0">
        ${REPITE[Math.floor(Math.random() * REPITE.length)]}</p>
    </div>`;
  await espera(1800);
}

// el ÚNICO momento en que aparece Lali durante la prueba: para felicitar
async function pantallaCelebra(cont, { total, estrellas }) {
  sonido.tono();                          // refuerzo musical al avanzar/acertar
  const zona = cont.querySelector("[data-zona]");
  const fila = cont.querySelector(".progreso-estrellas");
  if (fila) fila.children[estrellas - 1]?.classList.add("llena");
  zona.innerHTML = `
    <div class="anima-aparece" style="display:flex;flex-direction:column;align-items:center;gap:12px">
      <img class="lali-mini anima" src="${MASCOTA}" alt="Lali">
      <div style="font-family:var(--habli-fuente-titulo);font-size:44px;font-weight:800;color:var(--habli-tinta-900)">
        ⭐ ${CELEBRA[Math.floor(Math.random() * CELEBRA.length)]}
      </div>
    </div>`;
  await espera(1100);
}

// ---------------------------------------------------------------- final
async function celebracionFinal(cont, ninoId, ronda) {
  document.body.classList.add("fase-celebracion");
  let alias = "";
  try { alias = (await api.getNino(ninoId)).alias || ""; } catch { /* da igual */ }

  cont.innerHTML = `
    <div class="prueba celebracion anima-aparece">
      <img class="mascota" src="${MASCOTA}" alt="Lali celebrando">
      <h1>¡¡Lo has hecho genial${alias ? ", " + alias : ""}!! 🎉</h1>
      <div style="font-size:44px">⭐⭐⭐</div>
      <button class="h-btn h-btn--juego" id="seguir">Seguir ➜</button>
    </div>`;

  // lluvia de estrellas (acento amarillo puntual, nunca fondo)
  for (let k = 0; k < 14; k++) {
    const s = document.createElement("div");
    s.className = "estrella-cae";
    s.textContent = "⭐";
    s.style.left = `${Math.random() * 100}vw`;
    s.style.animationDelay = `${Math.random() * 1.4}s`;
    document.querySelector(".celebracion").appendChild(s);
  }

  cont.querySelector("#seguir").addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    ev.target.textContent = "Un momentito…";
    await cerrarPrueba(cont, ninoId, ronda);
  });
}

// Cierre: si la edad la estimó el modelo (no se indicó a mano), se PREGUNTA antes de
// generar el informe (con la predicción por defecto). En la ronda extra ya hay edad.
async function cerrarPrueba(cont, ninoId, ronda) {
  document.body.classList.remove("modo-nino", "fase-celebracion");
  if (ronda !== "repeticion") {
    let nino = null;
    try { nino = await api.getNino(ninoId); } catch { /* sin perfil */ }
    const edadManual = nino?.edad && !nino?.factores?.edad_estimada;
    if (!edadManual) {
      await pantallaEdad(cont, ninoId, nino, ronda);
      return;                                  // analiza al confirmar la edad
    }
  }
  await analizarYMostrar(cont, ninoId, ronda);
}

// Pregunta la edad ANTES del informe, con la predicción del modelo por defecto.
async function pantallaEdad(cont, ninoId, nino, ronda) {
  let pred = nino?.edad || 5;
  try {
    const est = await api.estimarEdad(ninoId);
    if (est.edad) pred = est.edad;
  } catch { /* usa el valor por defecto */ }

  cont.innerHTML = `
    <div class="hero-lali" style="background:var(--habli-azul-50);justify-content:center;gap:22px">
      <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;justify-content:center">
        <img src="${MASCOTA}" alt="" style="width:clamp(110px,15vw,150px)">
        <div class="bocadillo bocadillo--lado" style="max-width:min(480px,82vw);font-size:clamp(18px,2.3vw,22px)">
          Antes de ver el resultado… ¿cuántos años tiene ${esc(nino?.alias || "")}?<br>
          Lo hemos estimado en <strong>${pred} años</strong>.
        </div>
      </div>
      <div class="h-opciones" id="edad-chips" style="justify-content:center">
        ${[3, 4, 5, 6].map((e) => `<button type="button" class="h-opcion" data-v="${e}"
            aria-pressed="${e === pred}">${e} años</button>`).join("")}
      </div>
      <button class="h-btn h-btn--juego" id="edad-ok">Ver resultado ➜</button>
    </div>`;

  let edad = pred;
  const chips = cont.querySelectorAll("#edad-chips .h-opcion");
  chips.forEach((b) => b.addEventListener("click", () => {
    chips.forEach((x) => x.setAttribute("aria-pressed", "false"));
    b.setAttribute("aria-pressed", "true");
    edad = Number(b.dataset.v);
  }));

  cont.querySelector("#edad-ok").addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    ev.target.textContent = "Un momentito…";
    try {                                      // edad confirmada a mano: ya no es estimada
      await api.putNino(ninoId, { edad, factores: { ...(nino?.factores || {}), edad_estimada: false } });
    } catch { /* se analiza igualmente con lo que haya */ }
    await analizarYMostrar(cont, ninoId, ronda);
  });
}

// Analiza la prueba (el grafo calcula riesgo con la edad ya confirmada y guarda el
// informe) y muestra: resultado + ejercicios por riesgo (ligados a los errores) +
// recomendación de repetir la prueba tras el plazo del plan.
async function analizarYMostrar(cont, ninoId, ronda) {
  document.body.classList.remove("modo-nino", "fase-celebracion");
  cont.innerHTML = `
    <div class="hero-lali" style="background:var(--habli-azul-50)">
      <img src="${MASCOTA}" alt="" style="width:120px">
      <p style="font-size:20px;font-weight:700;display:flex;gap:12px;align-items:center">
        Preparando el resultado
        <span class="pensando"><span></span><span></span><span></span></span>
      </p>
    </div>`;

  const mensaje = ronda === "repeticion"
    ? "Hemos terminado la ronda extra de palabras."
    : "Hemos terminado de grabar todas las palabras.";
  let r;
  try {
    r = await api.chat(ninoId, mensaje);
  } catch (e) {
    cont.innerHTML = `
      <div class="hero-lali" style="background:var(--habli-azul-50)">
        <img src="${MASCOTA}" alt="" style="width:110px">
        <div class="bocadillo bocadillo--lado">No se pudo cerrar la prueba (${esc(e.message)}).
        Las palabras están guardadas: probad de nuevo desde el chat de Lali.</div>
        <button class="h-btn" onclick="location.hash='#/home'">Ir al inicio</button>
      </div>`;
    return;
  }

  cont.innerHTML = `
    <div class="hero-lali" style="justify-content:flex-start;padding-top:40px;background:var(--habli-azul-50)">
      <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;justify-content:center">
        <img src="${MASCOTA}" alt="" style="width:clamp(110px,15vw,160px)">
        <div class="bocadillo bocadillo--lado"
             style="max-width:min(560px,80vw);font-size:clamp(20px,2.6vw,26px)">${esc(r.mensaje || "¡Gracias por jugar!")}</div>
      </div>
      <div data-resultado style="max-width:640px;width:100%"></div>
      <div data-propuesta style="max-width:640px;width:100%"></div>
      <button class="h-btn h-btn--fantasma" onclick="location.hash='#/home'">🏠 Ir al inicio</button>
    </div>`;

  const zona = cont.querySelector("[data-resultado]");
  if (r.accion === "mostrar_resultado") {
    const tarjeta = tarjetaResultado(r.datos || {});
    zona.appendChild(tarjeta);
    tarjeta.addEventListener("click", async (ev) => {
      const acc = ev.target?.dataset?.acc;
      if (acc === "ronda") {
        const r2 = await api.chat(ninoId, "¡Sí, jugamos una ronda más!");
        if (r2.accion === "iniciar_grabacion") {
          estado.setPruebaPendiente(r2.datos);
          desmontar();
          render(cont);
        }
      } else if (acc === "ejercicios") location.hash = "#/ejercicios";
      else if (acc === "historico") location.hash = "#/historico";
    });
  } else {
    zona.innerHTML = `<p class="texto-secundario centrado">Podéis ver el resultado en
      «Mis resultados» o preguntando a Lali.</p>`;
  }

  await pintarPropuesta(cont, ninoId);
}

// Ejercicios propuestos por riesgo (ligados a los errores) + recomendación de repetir.
async function pintarPropuesta(cont, ninoId) {
  const zona = cont.querySelector("[data-propuesta]");
  if (!zona) return;
  let plan;
  try { plan = await api.getPropuesta(ninoId); } catch { return; }
  if (!plan || plan.error || !(plan.ejercicios || []).length) return;

  const lista = plan.ejercicios.map((e) => `
    <div class="h-card ejercicio-card" style="text-align:left;margin:0">
      <span class="h-chip nivel-chip--${e.nivel}">Nivel ${e.nivel}${
        e.nivel === 3 && e.proceso ? " · " + esc(e.proceso) : ""}</span>
      <h3 style="margin:8px 0 4px">${esc(e.titulo)}</h3>
      <p style="margin:0">${esc(e.actividad)}</p>
    </div>`).join("");

  const retest = plan.plazo
    ? `<div class="h-chip" style="margin-top:14px;font-size:15px">🔁 Repetir la prueba en
        ${esc(plan.plazo)}${plan.fecha_retest ? " (~" + fechaCorta(plan.fecha_retest) + ")" : ""}</div>`
    : "";

  zona.innerHTML = `
    <div class="h-card" style="text-align:left">
      <h2 style="margin-top:0">🧩 Juegos para practicar en casa</h2>
      ${plan.mensaje ? `<p>${esc(plan.mensaje)}</p>` : ""}
      <div style="display:flex;flex-direction:column;gap:12px">${lista}</div>
      ${retest}
    </div>`;
}

function fechaCorta(iso) {
  try {
    return new Date(iso).toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric" });
  } catch { return iso; }
}

function esc(t) {
  const d = document.createElement("div");
  d.textContent = String(t ?? "");
  return d.innerHTML;
}
