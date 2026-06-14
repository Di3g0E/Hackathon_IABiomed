// Home: sidebar a la izquierda, avatar arriba a la derecha y, en el centro,
// el chat con Lali (pregunta dudas, pide recomendaciones, lanza el juego).

import * as lali from "../lali.js";
import { montarShell } from "./_shell.js";

export async function render(cont) {
  const { slot } = await montarShell(cont, "#/home");
  slot.innerHTML = `<div class="chat-home"></div>`;
  lali.montarChat(slot.querySelector(".chat-home"));
}
