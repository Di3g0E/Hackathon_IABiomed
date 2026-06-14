// Estado de cliente: perfil activo y preferencias (la verdad clínica vive en el servidor).

const K_NINO = "habli.nino_id";
const K_NIVEL = "habli.nivel";

export function getNinoId() {
  return localStorage.getItem(K_NINO) || null;
}

export function setNinoId(id) {
  if (id) localStorage.setItem(K_NINO, id);
  else localStorage.removeItem(K_NINO);
}

export function getNivel() {
  return Number(sessionStorage.getItem(K_NIVEL) || "1");
}

export function setNivel(n) {
  sessionStorage.setItem(K_NIVEL, String(n));
}

// Datos de la prueba pendiente (palabras/ronda) que el chat u otra vista deja preparados.
let _pruebaPendiente = null;
export function setPruebaPendiente(datos) { _pruebaPendiente = datos; }
export function tomarPruebaPendiente() {
  const d = _pruebaPendiente;
  _pruebaPendiente = null;
  return d;
}

// Color de avatar estable por id (paleta de marca; nunca amarillo de fondo).
const COLORES = ["azul", "verde", "naranja"];
export function colorAvatar(id) {
  let h = 0;
  for (const c of String(id)) h = (h * 31 + c.charCodeAt(0)) % 997;
  return COLORES[h % COLORES.length];
}

export function inicial(alias) {
  return (String(alias || "?").trim()[0] || "?").toUpperCase();
}

// Markup del avatar: imagen circular si el perfil tiene factores.avatar; si no, inicial.
export function avatarHTML(nino, { boton = false, extra = "" } = {}) {
  const id = nino?.id || "";
  const av = nino?.factores?.avatar;
  const cls = `avatar avatar--${colorAvatar(id)}${av ? " avatar--img" : ""}`
    + `${boton ? " avatar--boton" : ""}${extra ? " " + extra : ""}`;
  if (av) return `<span class="${cls}" style="background-image:url('${av}')" aria-hidden="true"></span>`;
  return `<span class="${cls}">${inicial(nino?.alias || id)}</span>`;
}
