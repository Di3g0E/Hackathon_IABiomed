// Mis resultados: estrellas por participación, pruebas con su riesgo GENERAL
// (nunca detalle por palabra) y acceso manual al informe del especialista.

import * as api from "../api.js";
import * as estado from "../estado.js";
import { chipRiesgo } from "../lali.js";
import { montarShell } from "./_shell.js";

function fecha(ts) {
  try {
    return new Date(ts).toLocaleDateString("es-ES", { day: "numeric", month: "long", year: "numeric" });
  } catch { return ts; }
}

export async function render(cont) {
  const ninoId = estado.getNinoId();
  const { slot, nino } = await montarShell(cont, "#/historico", "Mis resultados");
  const h = await api.getHistorico(ninoId);

  const pruebas = h.pruebas.map((p) => `
    <div class="h-card anima-aparece">
      <div class="estrellas-grande" style="font-size:28px">${"⭐".repeat(p.estrellas || 0)}</div>
      <div style="flex:1;min-width:200px">
        <h3 style="margin:0">Juego de palabras ${p.n_prueba}</h3>
        <span class="texto-secundario">${fecha(p.fecha)} · ${p.n_palabras_jugadas} palabras</span>
      </div>
      ${chipRiesgo(p.riesgo_general)}
      <a class="h-btn h-btn--secundario" style="white-space:nowrap"
         href="${api.urlInformePalabras(ninoId, p.n_prueba)}" target="_blank" rel="noopener">🔎 Detalle por palabra</a>
    </div>`).join("");

  const hechos = h.ejercicios_hechos.map((e) => `
    <div class="h-card anima-aparece" style="padding:16px 24px">
      <span style="color:var(--habli-verde-600);font-size:22px">✔</span>
      <div style="flex:1"><strong>${e.titulo || "Juego en casa"}</strong>
        <span class="texto-secundario"> · ${fecha(e.fecha)}</span></div>
      <span class="estrella">⭐</span>
    </div>`).join("");

  slot.innerHTML = `
    <div class="h-card centrado" style="margin-bottom:24px">
      <div class="estrellas-grande" style="justify-content:center">
        <span class="estrella">⭐</span> ${h.estrellas_total}
      </div>
      <p class="texto-secundario">estrellas conseguidas jugando y practicando</p>
    </div>

    ${h.pruebas.length ? `<h2>Juegos de palabras</h2><div class="timeline">${pruebas}</div>`
      : `<div class="h-card centrado">
           <img src="/static/brand/lali-mascota.png" alt="" style="width:110px">
           <p>Todavía no hay ningún juego terminado.<br>¡El primero es el más divertido!</p>
           <button class="h-btn h-btn--juego" onclick="location.hash='#/prueba'">🎮 ¡A jugar!</button>
         </div>`}

    ${hechos ? `<h2 style="margin-top:32px">Juegos practicados en casa</h2><div class="timeline">${hechos}</div>` : ""}

    ${h.pruebas.length ? `
    <h2 style="margin-top:32px">Informe para el especialista</h2>
    <div class="h-card">
      <p class="texto-secundario">El informe completo (con el detalle clínico) es para el
      profesional. Cribado, no diagnóstico.</p>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        <a class="h-btn" href="${api.urlInforme(ninoId)}" target="_blank" rel="noopener">📄 Ver informe</a>
        <button class="h-btn h-btn--secundario" id="btn-enviar">✉️ Enviar al especialista</button>
      </div>
      <p class="texto-caption" style="margin-top:10px">El informe se abre en una pestaña;
      desde ahí puedes guardarlo en PDF con «Imprimir» (Ctrl+P).</p>
    </div>` : ""}`;

  slot.querySelector("#btn-enviar")?.addEventListener("click", async () => {
    let email = nino?.factores?.email_especialista;
    if (!email) {
      email = prompt("Email del especialista (puedes guardarlo en el perfil):");
      if (!email) return;
    }
    try {
      const env = await api.getEnvio(ninoId, email);
      if (env.mailto_url) window.location.href = env.mailto_url;
    } catch (e) {
      alert(`No se pudo preparar el envío: ${e.message}`);
    }
  });
}
