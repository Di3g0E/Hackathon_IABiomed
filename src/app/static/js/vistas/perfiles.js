// Pantalla de entrada: Lali saluda. Sin perfiles -> registro directo;
// con perfiles -> selector estilo Netflix + crear perfil nuevo.

import * as api from "../api.js";
import * as estado from "../estado.js";

export async function render(cont) {
  const { ninos } = await api.getNinos();

  if (!ninos.length) {
    cont.innerHTML = `
      <div class="hero-lali">
        <img class="mascota" src="/static/brand/lali-mascota.png" alt="Lali el loro saludando">
        <div class="bocadillo">
          ¡Hola! Soy <strong>Lali</strong> 🦜<br>
          Jugamos, hablamos y aprendemos. ¿Empezamos?<br>
          Primero cuéntame quién eres.
        </div>
        <button class="h-btn h-btn--juego" id="empezar">✨ ¡Empezar!</button>
        <p class="texto-caption">© ${new Date().getFullYear()} Habli · Proyecto Blue Route. Cribado, no diagnóstico.</p>
      </div>`;
    cont.querySelector("#empezar").addEventListener("click", () => {
      location.hash = "#/registro";
    });
    return;
  }

  cont.innerHTML = `
    <div class="perfiles">
      <img class="perfiles__logo" src="/static/brand/habli-logo.png" alt="Habli">
      <h1>¿Quién va a jugar hoy?</h1>
      <div class="perfiles__grid"></div>
      <p class="texto-caption">© ${new Date().getFullYear()} Habli · Proyecto Blue Route. Cribado, no diagnóstico.</p>
    </div>`;

  const grid = cont.querySelector(".perfiles__grid");
  for (const n of ninos) {
    const card = document.createElement("div");
    card.className = "perfil-card anima-aparece";
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.innerHTML = `
      <button class="perfil-del" aria-label="Eliminar perfil de ${n.alias}" title="Eliminar perfil">×</button>
      ${estado.avatarHTML(n)}
      <span class="perfil-card__nombre">${n.alias}</span>
      <span class="texto-secundario">⭐ ${n.n_pruebas || 0} ${n.n_pruebas === 1 ? "juego" : "juegos"}</span>`;
    const entrar = () => { estado.setNinoId(n.id); location.hash = "#/home"; };
    card.addEventListener("click", entrar);
    card.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); entrar(); } });
    card.querySelector(".perfil-del").addEventListener("click", async (ev) => {
      ev.stopPropagation();
      if (!confirm(`¿Eliminar el perfil de ${n.alias}?\n\nSe borrarán sus datos, audios e `
          + `informes. Esta acción no se puede deshacer.`)) return;
      try {
        await api.eliminarNino(n.id);
        if (estado.getNinoId() === n.id) estado.setNinoId(null);
        render(cont);                 // recarga el selector (o el saludo si no quedan)
      } catch (e) {
        alert(`No se pudo eliminar: ${e.message}`);
      }
    });
    grid.appendChild(card);
  }

  const nuevo = document.createElement("button");
  nuevo.className = "perfil-card perfil-card--nuevo";
  nuevo.innerHTML = `
    <span class="avatar">+</span>
    <span class="perfil-card__nombre">Crear perfil</span>
    <span class="texto-secundario">¡Un amigo nuevo!</span>`;
  nuevo.addEventListener("click", () => { location.hash = "#/registro"; });
  grid.appendChild(nuevo);
}
