// Router de la SPA Habli (hash routing, sin build step).

import * as estado from "./estado.js";
import * as lali from "./lali.js";
import * as perfiles from "./vistas/perfiles.js";
import * as registro from "./vistas/registro.js";
import * as home from "./vistas/home.js";
import * as prueba from "./vistas/prueba.js";
import * as historico from "./vistas/historico.js";
import * as ejercicios from "./vistas/ejercicios.js";
import * as perfil from "./vistas/perfil.js";

const RUTAS = {
  "#/perfiles": { vista: perfiles, requierePerfil: false },
  "#/registro": { vista: registro, requierePerfil: false },
  "#/home": { vista: home, requierePerfil: true },
  "#/prueba": { vista: prueba, requierePerfil: true },
  "#/historico": { vista: historico, requierePerfil: true },
  "#/ejercicios": { vista: ejercicios, requierePerfil: true },
  "#/perfil": { vista: perfil, requierePerfil: true },
};

let vistaActual = null;

async function navegar() {
  const hash = location.hash || "#/perfiles";
  const ruta = RUTAS[hash] || RUTAS["#/perfiles"];
  if (ruta.requierePerfil && !estado.getNinoId()) {
    location.hash = "#/perfiles";
    return;
  }
  // limpieza de la vista anterior (micro, temporizadores…)
  if (vistaActual?.desmontar) {
    try { vistaActual.desmontar(); } catch { /* nada */ }
  }
  vistaActual = ruta.vista;
  document.body.classList.remove("modo-nino", "fase-verde", "fase-celebracion");
  const cont = document.getElementById("vista");
  cont.innerHTML = "";
  // el botón de Lali vive en todas las pantallas con perfil, menos durante la prueba
  lali.colocarFab(hash !== "#/prueba" && Boolean(estado.getNinoId()));
  lali.cerrarPanel();
  try {
    await ruta.vista.render(cont);
  } catch (e) {
    cont.innerHTML = `
      <div class="hero-lali">
        <img class="mascota" src="/static/brand/lali-mascota.png" alt="Lali el loro">
        <div class="bocadillo">¡Uy! Algo no ha ido bien: ${e.message}.<br>
        ¿Está encendido el servidor de Habli?</div>
        <button class="h-btn" onclick="location.reload()">Reintentar</button>
      </div>`;
  }
}

window.addEventListener("hashchange", navegar);
lali.iniciar();
navegar();
