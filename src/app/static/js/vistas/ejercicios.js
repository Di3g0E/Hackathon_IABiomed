// Juegos para practicar: recomendados (si el especialista/el sistema asignó) +
// biblioteca completa por niveles. Marcar como hecho suma una estrella.

import * as api from "../api.js";
import * as estado from "../estado.js";
import { montarShell } from "./_shell.js";

const NIVEL_NOMBRE = { 1: "Para todos", 2: "Con sonidos", 3: "A medida" };

function textoBoton(hecho) {
  return hecho ? "✔ ¡Hecho!" : "¡Hecho! ⭐";
}

function claseBoton(hecho) {
  return hecho ? "h-btn h-btn--secundario" : "h-btn h-btn--verde";
}

function tarjeta(e, hecho = false) {
  const nivel = e.nivel || 1;
  return `
    <div class="h-card ejercicio-card anima-aparece">
      <div class="fila">
        <div style="flex:1;min-width:220px">
          <span class="h-chip nivel-chip--${nivel}">Nivel ${nivel} · ${NIVEL_NOMBRE[nivel] || ""}</span>
          <h3 style="margin:8px 0 4px">${e.titulo}</h3>
          <p style="margin:0">${e.actividad || e.actividad_familia || ""}</p>
          ${e.objetivo ? `<p class="texto-caption" style="margin-top:6px">${e.objetivo}</p>` : ""}
        </div>
        <button class="${claseBoton(hecho)}" data-titulo="${e.titulo}" data-hecho="${hecho ? "1" : "0"}"
                title="${hecho ? "Pulsa para desmarcar" : "Marcar como hecho"}">
          ${textoBoton(hecho)}
        </button>
      </div>
    </div>`;
}

export async function render(cont) {
  const ninoId = estado.getNinoId();
  const { slot, nino } = await montarShell(cont, "#/ejercicios", "Juegos para practicar");
  const [historico, biblioteca] = await Promise.all([
    api.getHistorico(ninoId),
    api.getEjercicios(nino?.edad),
  ]);
  const hechos = new Set(historico.ejercicios_hechos.map((e) => e.titulo));
  const recomendados = historico.ejercicios_propuestos || [];

  const niveles = (biblioteca.niveles || []).map((n) => `
    <h2 style="margin-top:24px">${n.titulo || `Nivel ${n.nivel}`}</h2>
    ${(n.ejercicios || []).map((e) => tarjeta({ ...e, nivel: e.nivel ?? n.nivel }, hechos.has(e.titulo))).join("")}
  `).join("");

  slot.innerHTML = `
    ${recomendados.length ? `
      <h2>Recomendados para ti 🦜</h2>
      ${recomendados.map((e) => tarjeta(e, hechos.has(e.titulo))).join("")}` : `
      <div class="h-card" style="margin-bottom:16px;display:flex;gap:16px;align-items:center">
        <img src="/static/brand/lali-mascota.png" alt="" style="width:72px">
        <p style="margin:0">Cuando terminéis un juego de palabras, Lali os recomendará
        los mejores juegos para casa. Mientras tanto, ¡aquí está la colección entera!</p>
      </div>`}
    ${niveles || `<p class="texto-secundario">No hay juegos disponibles para esta edad.</p>`}`;

  // marcar / desmarcar (toggle): se puede quitar la marca de un ejercicio completado
  slot.querySelectorAll("button[data-titulo]").forEach((b) =>
    b.addEventListener("click", async () => {
      const hecho = b.dataset.hecho === "1";
      b.disabled = true;
      try {
        if (hecho) await api.desmarcarEjercicio(ninoId, b.dataset.titulo);
        else await api.marcarEjercicio(ninoId, b.dataset.titulo);
        b.dataset.hecho = hecho ? "0" : "1";
        b.textContent = textoBoton(!hecho);
        b.className = claseBoton(!hecho);
        b.title = !hecho ? "Pulsa para desmarcar" : "Marcar como hecho";
      } catch (e) {
        alert(`No se pudo guardar: ${e.message}`);
      } finally {
        b.disabled = false;
      }
    }));
}
