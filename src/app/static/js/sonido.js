// Tono musical de refuerzo (Web Audio API, sin archivos): suena al avanzar o acertar.
// Silenciable; la preferencia se guarda en localStorage.

const K_MUTE = "habli.mute";
let ctx = null;

export function silenciado() {
  return localStorage.getItem(K_MUTE) === "1";
}

export function alternarSilencio() {
  const nuevo = !silenciado();
  localStorage.setItem(K_MUTE, nuevo ? "1" : "0");
  return nuevo;
}

// Acorde alegre ascendente (do–mi–sol), corto y suave.
export function tono() {
  if (silenciado()) return;
  try {
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === "suspended") ctx.resume();
    const t0 = ctx.currentTime;
    const notas = [[523.25, 0], [659.25, 0.10], [783.99, 0.20]]; // C5, E5, G5
    for (const [freq, retardo] of notas) {
      const osc = ctx.createOscillator();
      const gan = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.value = freq;
      const t = t0 + retardo;
      gan.gain.setValueAtTime(0.0001, t);
      gan.gain.exponentialRampToValueAtTime(0.22, t + 0.03);
      gan.gain.exponentialRampToValueAtTime(0.0001, t + 0.32);
      osc.connect(gan).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.34);
    }
  } catch { /* navegador sin Web Audio: silencio */ }
}
