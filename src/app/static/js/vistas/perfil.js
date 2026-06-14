// Configuración del perfil: campos tipo "bocadillo" (blancos, redondeados) directamente
// sobre el fondo de la página, con la pista en gris dentro de cada campo. Incluye el
// email del especialista y el cuestionario inicial (screening). Cerrar sesión vive en
// el menú del avatar.

import * as api from "../api.js";
import * as estado from "../estado.js";
import { montarSelectorAvatar } from "../avatares.js";
import { montarShell } from "./_shell.js";

export async function render(cont) {
  const ninoId = estado.getNinoId();
  const { slot, nino } = await montarShell(cont, "#/perfil", "Mi perfil");
  const f = nino?.factores || {};

  slot.innerHTML = `
    <form id="form-perfil" style="max-width:620px;display:flex;flex-direction:column;gap:16px">
      <input class="h-input h-input--bocadillo" id="p-nombre" maxlength="30"
             placeholder="Nombre o apodo (sin apellidos)" aria-label="Nombre o apodo"
             value="${nino?.alias || ""}">

      <div id="p-avatar"></div>

      <div>
        <p class="texto-caption" style="margin:0 0 8px 12px">Edad${f.edad_estimada
          ? " · ✨ estimada por el modelo a partir de la voz — revísala"
          : (nino?.edad ? "" : " · se estimará con la voz en el primer juego")}</p>
        <div class="h-opciones" id="p-edad">
          ${[3, 4, 5, 6].map((e) => `<button type="button" class="h-opcion" data-v="${e}"
              aria-pressed="${nino?.edad === e}">${e} años</button>`).join("")}
        </div>
      </div>

      <select class="h-select h-select--bocadillo" id="p-sexo" aria-label="Sexo">
        <option value="" ${!nino?.sexo ? "selected" : ""}>Sexo: prefiero no decirlo</option>
        <option value="m" ${nino?.sexo === "m" ? "selected" : ""}>Niño</option>
        <option value="f" ${nino?.sexo === "f" ? "selected" : ""}>Niña</option>
      </select>

      <input class="h-input h-input--bocadillo" id="p-lengua" maxlength="30"
             placeholder="Lengua materna (por ejemplo: español)" aria-label="Lengua materna"
             value="${f.lengua_materna || ""}">

      <label class="h-check">
        <input type="checkbox" id="p-bilinguismo" ${f.bilinguismo ? "checked" : ""}>
        <span>En casa se habla más de un idioma (bilingüismo)</span>
      </label>
      <label class="h-check">
        <input type="checkbox" id="p-audicion" ${f.problemas_auditivos ? "checked" : ""}>
        <span>Ha tenido otitis de repetición o problemas de audición</span>
      </label>

      <input class="h-input h-input--bocadillo" id="p-email" type="email"
             placeholder="Email del especialista (logopeda)" aria-label="Email del especialista"
             value="${f.email_especialista || ""}">

      <label class="h-check">
        <input type="checkbox" id="p-consentimiento-datos" ${f.consentimiento_datos ? "checked" : ""}>
        <span>Permito guardar la voz y la edad de forma <strong>anónima</strong> para mejorar el sistema (opcional).</span>
      </label>

      <div>
        <button class="h-btn" type="submit">💾 Guardar cambios</button>
      </div>
    </form>

    <div id="card-screening" style="max-width:620px;margin-top:40px">
      <h2>Unas preguntas sobre el peque</h2>
      <p class="texto-secundario">Cuestionario breve y opcional para el especialista
      (ayuda a interpretar mejor los juegos de palabras). Cribado, no diagnóstico.</p>
      <button class="h-btn h-btn--secundario" id="btn-screening">📋 Responder ahora</button>
      <div id="zona-screening" style="margin-top:16px"></div>
    </div>`;

  // selector de avatar (si hay imágenes en static/avatares/)
  let avatarElegido = f.avatar || null;
  await montarSelectorAvatar(slot.querySelector("#p-avatar"),
    { actual: f.avatar, onSelect: (u) => { avatarElegido = u; } });

  // edad con chips
  let edad = nino?.edad || null;
  const botonesEdad = slot.querySelectorAll("#p-edad .h-opcion");
  botonesEdad.forEach((b) =>
    b.addEventListener("click", () => {
      botonesEdad.forEach((x) => x.setAttribute("aria-pressed", "false"));
      b.setAttribute("aria-pressed", "true");
      edad = Number(b.dataset.v);
    }));

  slot.querySelector("#form-perfil").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const boton = ev.submitter;
    boton.disabled = true;
    try {
      await api.putNino(ninoId, {
        alias: slot.querySelector("#p-nombre").value.trim() || null,
        edad,
        sexo: slot.querySelector("#p-sexo").value || null,
        factores: {
          ...f,
          avatar: avatarElegido,
          lengua_materna: slot.querySelector("#p-lengua").value.trim() || null,
          bilinguismo: slot.querySelector("#p-bilinguismo").checked,
          problemas_auditivos: slot.querySelector("#p-audicion").checked,
          email_especialista: slot.querySelector("#p-email").value.trim() || null,
          consentimiento_datos: slot.querySelector("#p-consentimiento-datos").checked,
          // al guardar, la familia ya ha revisado la edad: deja de ser "estimada"
          ...(edad ? { edad_estimada: false } : {}),
        },
      });
      boton.textContent = "✔ Guardado";
      setTimeout(() => { boton.textContent = "💾 Guardar cambios"; boton.disabled = false; }, 1500);
    } catch (e) {
      alert(`No se pudo guardar: ${e.message}`);
      boton.disabled = false;
    }
  });

  // ---- screening (tarjetas Sí/No grandes) ----
  slot.querySelector("#btn-screening").addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    const zona = slot.querySelector("#zona-screening");
    const items = await api.getScreeningItems();
    const respuestas = {};
    zona.innerHTML = items.map((it) => `
      <div class="h-campo">
        <label>${it.texto}</label>
        <div class="h-opciones" data-item="${it.id}">
          <button type="button" class="h-opcion" data-v="si" aria-pressed="false">Sí</button>
          <button type="button" class="h-opcion" data-v="no" aria-pressed="false">No</button>
        </div>
      </div>`).join("") + `<button class="h-btn" id="enviar-screening">Enviar respuestas</button>`;

    zona.querySelectorAll(".h-opciones").forEach((grupo) =>
      grupo.querySelectorAll(".h-opcion").forEach((b) =>
        b.addEventListener("click", () => {
          grupo.querySelectorAll(".h-opcion").forEach((x) => x.setAttribute("aria-pressed", "false"));
          b.setAttribute("aria-pressed", "true");
          respuestas[grupo.dataset.item] = b.dataset.v === "si";
        })));

    zona.querySelector("#enviar-screening").addEventListener("click", async (e2) => {
      e2.target.disabled = true;
      try {
        await api.enviarScreening(respuestas, edad || 5, ninoId);
        zona.innerHTML = `<p>¡Gracias! 🦜 Las respuestas quedan guardadas para el especialista.</p>`;
      } catch (err) {
        alert(`No se pudo enviar: ${err.message}`);
        e2.target.disabled = false;
      }
    });
  });
}
