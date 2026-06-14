// Selector de avatar reutilizable (registro y perfil). Muestra las imágenes cuadradas
// de /avatares de forma CIRCULAR; la opción elegida se guarda en factores.avatar (URL).
// Si no hay imágenes en la carpeta, no se muestra nada (se usa la inicial de color).

import * as api from "./api.js";

export async function montarSelectorAvatar(cont, { actual = null, onSelect = () => {} } = {}) {
  let avatares = [];
  try { ({ avatares } = await api.getAvatares()); } catch { avatares = []; }
  if (!avatares.length) {
    cont.innerHTML = "";
    return null;             // sin imágenes: el llamador usa la inicial de color
  }
  let elegido = actual && avatares.includes(actual) ? actual : null;

  cont.innerHTML = `
    <p class="texto-caption" style="margin:0 0 10px;text-align:center">Elige un dibujo de perfil</p>
    <div class="avatar-picker">
      ${avatares.map((u) => `
        <button type="button" class="avatar-opcion ${u === elegido ? "sel" : ""}"
                data-url="${u}" aria-label="Elegir avatar" aria-pressed="${u === elegido}">
          <img src="${u}" alt="">
        </button>`).join("")}
    </div>`;

  cont.querySelectorAll(".avatar-opcion").forEach((b) =>
    b.addEventListener("click", () => {
      elegido = b.dataset.url;
      cont.querySelectorAll(".avatar-opcion").forEach((x) => {
        const sel = x === b;
        x.classList.toggle("sel", sel);
        x.setAttribute("aria-pressed", String(sel));
      });
      onSelect(elegido);
    }));

  return { get: () => elegido };
}
