// Lali, el loro 🦜 — chat de la familia (historial persistido en servidor) +
// botón flotante global + dispatcher de las ACCIONES que emite el grafo.
// Regla de marca: Lali anima y celebra; el riesgo lo muestra la UI en su tarjeta,
// solo el nivel GENERAL, nunca por palabra.

import * as api from "./api.js";
import * as estado from "./estado.js";

const MASCOTA = "/static/brand/lali-mascota.png";
const CHIPS = ["¿Qué hacemos hoy?", "Quiero jugar", "¿Qué juegos hay para casa?"];

function esc(t) {
  const d = document.createElement("div");
  d.textContent = String(t ?? "");
  return d.innerHTML;
}

export function chipRiesgo(nivel, grande = false) {
  const textos = { bajo: "Riesgo bajo", medio: "Riesgo medio", alto: "Riesgo alto" };
  if (!textos[nivel]) return "";
  return `<span class="h-chip h-chip--riesgo-${esc(nivel)}${grande ? " h-chip--grande" : ""}">${textos[nivel]}</span>`;
}

// ---------------------------------------------------------------- tarjetas de acción
export function tarjetaResultado(datos) {
  const el = document.createElement("div");
  el.className = "burbuja burbuja--tarjeta tarjeta-resultado anima-aparece";
  el.innerHTML = `
    <h3>Resultado de la prueba</h3>
    <p>${chipRiesgo(datos.nivel_riesgo, true)}</p>
    ${datos.recomendacion ? `<p class="recomendacion">${esc(datos.recomendacion)}</p>` : ""}
    <p class="texto-caption">${esc(datos.encuadre || "Cribado orientativo, no es un diagnóstico.")}</p>
    <div class="acciones">
      ${datos.ronda_extra ? `<button class="h-btn h-btn--secundario" data-acc="ronda">🎲 Una ronda más</button>` : ""}
      <button class="h-btn h-btn--secundario" data-acc="ejercicios">🧩 Juegos para practicar</button>
      <button class="h-btn h-btn--secundario" data-acc="historico">⭐ Mis resultados</button>
    </div>`;
  return el;
}

function tarjetaJugar(datos) {
  const el = document.createElement("div");
  el.className = "burbuja burbuja--tarjeta anima-aparece";
  const n = (datos.palabras || []).length;
  el.innerHTML = `
    <h3 style="margin-bottom:8px">¡Hay un juego de palabras preparado!</h3>
    <p class="texto-secundario">${n} palabras · prueba ${esc(datos.n_prueba ?? "")}</p>
    <button class="h-btn h-btn--juego" data-acc="jugar">🎮 ¡A jugar!</button>`;
  return el;
}

function tarjetaEjercicios(datos) {
  const el = document.createElement("div");
  el.className = "burbuja burbuja--tarjeta anima-aparece";
  const lista = (datos.ejercicios || [])
    .map((e) => `<li><strong>${esc(e.titulo)}</strong> — ${esc(e.actividad || e.actividad_familia || "")}</li>`)
    .join("");
  el.innerHTML = `
    <h3 style="margin-bottom:8px">Juegos para practicar en casa</h3>
    ${datos.mensaje ? `<p>${esc(datos.mensaje)}</p>` : ""}
    <ul style="padding-left:20px">${lista}</ul>
    ${datos.plazo ? `<p class="texto-secundario">Próximo juego de palabras en ${esc(datos.plazo)} ⭐</p>` : ""}
    <button class="h-btn h-btn--secundario" data-acc="ejercicios">Ver todos los juegos</button>`;
  return el;
}

function tarjetaEnvio(datos) {
  const el = document.createElement("div");
  el.className = "burbuja burbuja--tarjeta anima-aparece";
  const urlInforme = datos.informe_url || datos.pdf_url;
  el.innerHTML = `
    <h3 style="margin-bottom:8px">Informe para el especialista</h3>
    <p class="texto-secundario">El informe completo es para el profesional; ábrelo o envíalo cuando quieras.</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <a class="h-btn" href="${urlInforme}" target="_blank" rel="noopener">📄 Ver informe</a>
      ${datos.mailto_url ? `<a class="h-btn h-btn--secundario" href="${datos.mailto_url}">✉️ Enviar al especialista</a>` : ""}
    </div>`;
  return el;
}

// ---------------------------------------------------------------- componente de chat
export function montarChat(cont, { alFinalizarAccion = null } = {}) {
  const ninoId = estado.getNinoId();
  cont.innerHTML = `
    <div class="chat">
      <div class="chat__cabecera">
        <img src="${MASCOTA}" alt="">
        <div>
          <div class="nombre">Lali</div>
          <div class="texto-caption">tu loro parlanchín 🦜</div>
        </div>
      </div>
      <div class="chat__mensajes" role="log" aria-live="polite"></div>
      <div class="chat__chips"></div>
      <form class="chat__entrada">
        <input class="h-input" type="text" placeholder="Escribe a Lali…" aria-label="Mensaje para Lali">
        <button class="h-btn h-btn--verde" type="submit" aria-label="Enviar">➤</button>
      </form>
    </div>`;

  const mensajes = cont.querySelector(".chat__mensajes");
  const chips = cont.querySelector(".chat__chips");
  const form = cont.querySelector(".chat__entrada");
  const input = form.querySelector("input");

  function burbuja(rol, texto) {
    const el = document.createElement("div");
    if (rol === "assistant") {
      el.className = "burbuja burbuja--lali";
      el.innerHTML = `<img src="${MASCOTA}" alt=""><div>${esc(texto)}</div>`;
    } else {
      el.className = "burbuja burbuja--usuario";
      el.textContent = texto;
    }
    mensajes.appendChild(el);
    mensajes.scrollTop = mensajes.scrollHeight;
    return el;
  }

  function tarjeta(el) {
    if (!el) return;
    mensajes.appendChild(el);
    el.addEventListener("click", (ev) => {
      const acc = ev.target?.dataset?.acc;
      if (!acc) return;
      if (acc === "jugar") location.hash = "#/prueba";
      else if (acc === "ejercicios") location.hash = "#/ejercicios";
      else if (acc === "historico") location.hash = "#/historico";
      else if (acc === "ronda") enviar("¡Sí, jugamos una ronda más!");
      if (alFinalizarAccion) alFinalizarAccion(acc);
    });
    mensajes.scrollTop = mensajes.scrollHeight;
  }

  // las ACCIONES del grafo se traducen en tarjetas dentro del chat (la familia decide)
  function despachar(accion, datos) {
    if (!accion) return;
    if (accion === "pedir_registro") {
      const el = document.createElement("div");
      el.className = "burbuja burbuja--tarjeta";
      el.innerHTML = `<button class="h-btn" onclick="location.hash='#/registro'">📝 Completar los datos</button>`;
      tarjeta(el);
    } else if (accion === "iniciar_grabacion") {
      estado.setPruebaPendiente(datos);
      tarjeta(tarjetaJugar(datos));
    } else if (accion === "mostrar_resultado") {
      tarjeta(tarjetaResultado(datos));
    } else if (accion === "mostrar_ejercicios") {
      tarjeta(tarjetaEjercicios(datos));
    } else if (accion === "ofrecer_envio") {
      tarjeta(tarjetaEnvio(datos));
    }
  }

  let ocupado = false;
  async function enviar(texto, datos = null) {
    if (ocupado) return;
    ocupado = true;
    if (texto) burbuja("user", texto);
    // puntos grandes y animados: se ve que Lali piensa, no que la app está congelada
    const espera = burbuja("assistant", "");
    espera.querySelector("div").innerHTML =
      `<span class="pensando" aria-label="Lali está pensando"><span></span><span></span><span></span></span>`;
    try {
      const r = await api.chat(ninoId, texto, datos);
      espera.querySelector("div").textContent = r.mensaje || "…";
      despachar(r.accion, r.datos || {});
    } catch (e) {
      espera.querySelector("div").textContent = `¡Uy! No he podido responder (${e.message}).`;
    } finally {
      ocupado = false;
    }
  }

  for (const c of CHIPS) {
    const b = document.createElement("button");
    b.className = "h-chip";
    b.type = "button";
    b.textContent = c;
    b.addEventListener("click", () => enviar(c));
    chips.appendChild(b);
  }

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const t = input.value.trim();
    if (!t) return;
    input.value = "";
    enviar(t);
  });

  // historial persistido: se recupera del servidor; si está vacío, Lali saluda
  (async () => {
    try {
      const h = await api.getHistorial(ninoId);
      const turnos = h.historial || [];
      for (const m of turnos) burbuja(m.role === "user" ? "user" : "assistant", m.content);
      if (!turnos.length) await enviar("");
      mensajes.scrollTop = mensajes.scrollHeight;
    } catch {
      burbuja("assistant", "¡Hola! Soy Lali 🦜 ¿Jugamos?");
    }
  })();

  return { enviar };
}

// ---------------------------------------------------------------- botón flotante
let panelAbierto = false;

export function iniciar() {
  const fab = document.getElementById("lali-fab");
  fab.addEventListener("click", () => (panelAbierto ? cerrarPanel() : abrirPanel()));
}

export function colocarFab(visible) {
  document.getElementById("lali-fab").classList.toggle("oculto", !visible);
  if (!visible) cerrarPanel();
}

export function abrirPanel() {
  const panel = document.getElementById("lali-panel");
  panel.classList.remove("oculto");
  panelAbierto = true;
  montarChat(panel);
}

export function cerrarPanel() {
  const panel = document.getElementById("lali-panel");
  panel.classList.add("oculto");
  panel.innerHTML = "";
  panelAbierto = false;
}
