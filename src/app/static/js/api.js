// Cliente de la API (mismo origen). El audio del niño va al servidor, NUNCA al LLM.

async function pedir(ruta, opciones = {}) {
  const r = await fetch(ruta, opciones);
  if (!r.ok) {
    let detalle = r.statusText;
    try { detalle = (await r.json()).detail || detalle; } catch { /* sin cuerpo JSON */ }
    throw new Error(detalle);
  }
  return r.json();
}

export const getSalud = () => pedir("/salud");
export const getNinos = () => pedir("/ninos");
export const getNino = (id) => pedir(`/nino/${encodeURIComponent(id)}`);
export const putNino = (id, datos) =>
  pedir(`/nino/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  });
export const eliminarNino = (id) =>
  pedir(`/nino/${encodeURIComponent(id)}`, { method: "DELETE" });

export const getHistorial = (id) => pedir(`/familia/chat/${encodeURIComponent(id)}/historial`);
export const chat = (id, mensaje = "", datos = null) =>
  pedir("/familia/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, mensaje, ...(datos ? { datos } : {}) }),
  });

export const getAvatares = () => pedir("/avatares");
export const getPalabrasPrueba = (id) => pedir(`/prueba/${encodeURIComponent(id)}/palabras`);
export const iniciarPrueba = (id) =>
  pedir(`/prueba/${encodeURIComponent(id)}/iniciar`, { method: "POST" });
export const estimarEdad = (id) =>
  pedir(`/prueba/${encodeURIComponent(id)}/estimar-edad`, { method: "POST" });
export const getPropuesta = (id) => pedir(`/nino/${encodeURIComponent(id)}/propuesta`);
export const abandonarPrueba = (id, ronda = "principal") =>
  pedir(`/prueba/${encodeURIComponent(id)}/abandonar?ronda=${ronda}`, { method: "POST" });
// versión para cierres de página/navegación (no espera respuesta)
export const abandonarPruebaBeacon = (id, ronda = "principal") => {
  const url = `/prueba/${encodeURIComponent(id)}/abandonar?ronda=${ronda}`;
  if (!navigator.sendBeacon?.(url)) {
    fetch(url, { method: "POST", keepalive: true }).catch(() => {});
  }
};
export const urlAudioPalabra = (palabra) => `/palabra/${encodeURIComponent(palabra)}/audio`;
export const urlImagenPalabra = (palabra) => `/static/palabras/${encodeURIComponent(palabra)}.png`;
export const IMAGEN_PLACEHOLDER = "/static/palabras/placeholder.svg";

export async function subirAudio(palabra, blobWav, ninoId, { reintentada = false, ronda = "principal" } = {}) {
  const fd = new FormData();
  fd.append("archivo", blobWav, `${palabra}.wav`);
  fd.append("nino_id", ninoId);
  fd.append("reintentada", String(reintentada));
  fd.append("ronda", ronda);
  return pedir(`/familia/audio/${encodeURIComponent(palabra)}`, { method: "POST", body: fd });
}

export const getHistorico = (id) => pedir(`/nino/${encodeURIComponent(id)}/historico`);
export const getEjercicios = (edad) =>
  pedir(`/ejercicios${edad ? `?edad=${edad}` : ""}`);
export const marcarEjercicio = (id, titulo) =>
  pedir(`/nino/${encodeURIComponent(id)}/ejercicio`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo }),
  });
export const desmarcarEjercicio = (id, titulo) =>
  pedir(`/nino/${encodeURIComponent(id)}/ejercicio`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo }),
  });

export const getScreeningItems = () => pedir("/familia/screening/items");
export const enviarScreening = (respuestas, edad, ninoId) =>
  pedir("/familia/screening", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ respuestas, edad, nino_id: ninoId }),
  });

export const getEnvio = (id, email) =>
  pedir(`/informe/${encodeURIComponent(id)}/envio${email ? `?email=${encodeURIComponent(email)}` : ""}`);
export const urlInforme = (id) => `/informe/${encodeURIComponent(id)}/html`;
export const urlPdf = (id) => `/informe/${encodeURIComponent(id)}/pdf`;
export const urlInformePalabras = (id, nPrueba) =>
  `/sesion/${encodeURIComponent(`${id}_p${nPrueba}`)}/palabras.html`;
