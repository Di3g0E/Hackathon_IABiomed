// Registro mínimo, en una sola pantalla SIN scroll: nombre, dibujo de perfil (si hay
// avatares) y los dos consentimientos, en bocadillos grandes y centrados.
// La EDAD no se pide (se estima por la voz en el primer juego). La LENGUA MATERNA y el
// resto de datos se configuran después desde el perfil.

import * as api from "../api.js";
import * as estado from "../estado.js";
import { montarSelectorAvatar } from "../avatares.js";

function slug(s) {
  // quita diacríticos (NFD separa la letra de su tilde: rango U+0300-U+036F)
  const sinAcentos = String(s).normalize("NFD").split("")
    .filter((c) => c.charCodeAt(0) < 0x300 || c.charCodeAt(0) > 0x36f).join("");
  return sinAcentos.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "peque";
}

export async function render(cont) {
  cont.innerHTML = `
    <div class="hero-lali" style="background:var(--habli-azul-50);min-height:100vh;justify-content:center;gap:18px;padding:16px">
      <div style="display:flex;align-items:center;gap:14px;justify-content:center">
        <img src="/static/brand/lali-mascota.png" alt="" style="width:84px">
        <div class="bocadillo bocadillo--lado" style="max-width:320px;padding:14px 20px;font-size:18px">
          ¡Hola, soy Lali! 🦜 ¿Cómo te llamas?
        </div>
      </div>

      <form id="form-registro" class="anima-aparece"
            style="max-width:540px;width:100%;display:flex;flex-direction:column;gap:14px;align-items:center">
        <input class="h-input h-input--bocadillo" id="r-nombre" required maxlength="30"
               style="font-size:19px;text-align:center"
               placeholder="Nombre o apodo" aria-label="Nombre o apodo">

        <div id="r-avatar" style="width:100%"></div>

        <label class="h-check" style="width:100%;font-size:16px;align-items:center">
          <input type="checkbox" id="r-consentimiento" required>
          <span>Acepto los permisos de la app (cribado, no diagnóstico).</span>
        </label>

        <label class="h-check" style="width:100%;font-size:16px;align-items:center">
          <input type="checkbox" id="r-consentimiento-datos">
          <span>Permito usar el audio, de forma anónima, para mejorar.</span>
        </label>

        <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;justify-content:center">
          <button class="h-btn h-btn--juego" type="submit">🦜 ¡Listo, Lali!</button>
          <button class="h-btn h-btn--fantasma" type="button" id="r-volver">Volver</button>
        </div>
        <p class="texto-caption" style="margin:0;text-align:center">La edad se estima con la voz en el primer juego.</p>
      </form>
    </div>`;

  // selector de avatar (si hay imágenes en static/avatares/)
  let avatarSel = null;
  let avatarElegido = null;
  const ctrl = await montarSelectorAvatar(cont.querySelector("#r-avatar"),
    { onSelect: (u) => { avatarElegido = u; } });
  avatarSel = ctrl;

  cont.querySelector("#r-volver").addEventListener("click", () => {
    location.hash = "#/perfiles";
  });

  cont.querySelector("#form-registro").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const nombre = cont.querySelector("#r-nombre").value.trim();
    if (!nombre) return;

    // id estable estilo "ana"; si colisiona, sufijo numérico
    const { ninos } = await api.getNinos();
    const existentes = new Set(ninos.map((n) => n.id));
    let id = slug(nombre);
    let k = 2;
    while (existentes.has(id)) id = `${slug(nombre)}_${k++}`;

    const boton = ev.submitter;
    boton.disabled = true;
    try {
      await api.putNino(id, {
        alias: nombre,
        factores: {
          avatar: (avatarSel && avatarSel.get()) || avatarElegido || null,
          consentimiento: cont.querySelector("#r-consentimiento").checked,
          consentimiento_datos: cont.querySelector("#r-consentimiento-datos").checked,
        },
      });
      estado.setNinoId(id);
      location.hash = "#/home";
    } catch (e) {
      alert(`No se pudo guardar el perfil: ${e.message}`);
      boton.disabled = false;
    }
  });
}
