// Layout interior compartido: sidebar izquierda PLEGABLE (botón de tres líneas) que
// comparte el fondo de la página (sin diferencia de color), y topbar con el avatar
// del perfil, que despliega un menú: Configurar / Cerrar sesión.

import * as api from "../api.js";
import * as estado from "../estado.js";

const ITEMS = [
  { hash: "#/prueba", icono: "🎮", texto: "Iniciar prueba" },
  { hash: "#/historico", icono: "⭐", texto: "Mis resultados" },
  { hash: "#/ejercicios", icono: "🧩", texto: "Juegos para practicar" },
];

export async function montarShell(cont, hashActivo, titulo = "") {
  const ninoId = estado.getNinoId();
  let nino = null;
  try { nino = await api.getNino(ninoId); } catch { /* perfil aún sin guardar */ }
  const alias = nino?.alias || ninoId;
  const avatarUrl = nino?.factores?.avatar || null;

  cont.innerHTML = `
    <div class="app-shell">
      <nav class="sidebar" aria-label="Menú principal">
        <a href="#/home"><img class="sidebar__logo" src="/static/brand/habli-logo.png" alt="Habli"></a>
        ${ITEMS.map((i) => `
          <button class="sidebar__item ${i.hash === hashActivo ? "activo" : ""}" data-hash="${i.hash}">
            <span class="icono">${i.icono}</span> ${i.texto}
          </button>`).join("")}
      </nav>
      <div class="contenido">
        <header class="topbar">
          <button class="hamburguesa" aria-label="Mostrar u ocultar el menú" aria-expanded="true">☰</button>
          <div style="display:flex;align-items:center;gap:12px">
            <div class="menu-perfil-zona">
              <button class="avatar avatar--${estado.colorAvatar(ninoId)} avatar--boton${avatarUrl ? " avatar--img" : ""}"
                      ${avatarUrl ? `style="background-image:url('${avatarUrl}')"` : ""}
                      title="Mi perfil" aria-label="Menú del perfil de ${alias}" aria-haspopup="true">
                ${avatarUrl ? "" : estado.inicial(alias)}
              </button>
              <div class="menu-perfil oculto" role="menu">
                <button role="menuitem" data-opcion="configurar">⚙️ Configurar</button>
                <button role="menuitem" data-opcion="salir">👋 Cerrar sesión</button>
              </div>
            </div>
          </div>
        </header>
        <div class="contenido__cuerpo">
          ${titulo ? `<h1>${titulo}</h1>` : ""}
          <div data-slot></div>
        </div>
      </div>
    </div>`;

  const shell = cont.querySelector(".app-shell");
  const sidebar = cont.querySelector(".sidebar");
  cont.querySelectorAll(".sidebar__item").forEach((b) =>
    b.addEventListener("click", () => { location.hash = b.dataset.hash; }));

  // pliega/despliega: en escritorio colapsa la columna, en móvil desliza el panel
  const hamburguesa = cont.querySelector(".hamburguesa");
  hamburguesa.addEventListener("click", () => {
    shell.classList.toggle("plegada");
    sidebar.classList.toggle("abierta");
    hamburguesa.setAttribute("aria-expanded", String(!shell.classList.contains("plegada")));
  });

  // menú del avatar
  const menu = cont.querySelector(".menu-perfil");
  const avatar = cont.querySelector(".avatar--boton");
  avatar.addEventListener("click", (ev) => {
    ev.stopPropagation();
    const estabaOculto = menu.classList.contains("oculto");
    menu.classList.toggle("oculto");
    if (estabaOculto) {
      document.addEventListener("click", () => menu.classList.add("oculto"), { once: true });
    }
  });
  menu.addEventListener("click", (ev) => {
    const opcion = ev.target?.dataset?.opcion;
    if (opcion === "configurar") location.hash = "#/perfil";
    else if (opcion === "salir") {
      estado.setNinoId(null);
      location.hash = "#/perfiles";
    }
  });

  return { slot: cont.querySelector("[data-slot]"), nino };
}
