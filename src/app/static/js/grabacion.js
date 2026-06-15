// Captura de micrófono -> WAV PCM16 mono 16 kHz codificado EN CLIENTE.
// (MediaRecorder produce webm/opus, que el servidor puede no decodificar sin ffmpeg;
// un WAV lo lee soundfile/librosa siempre.) Echo/noise suppression desactivados:
// distorsionan el análisis fonético.

import * as vad from "./vad.js";

const SR_DESTINO = 16000;

let stream = null;
let ctx = null;
let nodo = null;
let fuente = null;
let trozos = [];
let capturando = false;

const CODIGO_WORKLET = `
class CapturaHabli extends AudioWorkletProcessor {
  process(inputs) {
    const canal = inputs[0] && inputs[0][0];
    if (canal) this.port.postMessage(canal.slice(0));
    return true;
  }
}
registerProcessor("captura-habli", CapturaHabli);
`;

export async function iniciar() {
  if (stream) return;
  stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: true,
    },
  });
  ctx = new (window.AudioContext || window.webkitAudioContext)();
  fuente = ctx.createMediaStreamSource(stream);
  if (ctx.audioWorklet) {
    const url = URL.createObjectURL(new Blob([CODIGO_WORKLET], { type: "application/javascript" }));
    await ctx.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);
    nodo = new AudioWorkletNode(ctx, "captura-habli");
    nodo.port.onmessage = (ev) => { if (capturando) trozos.push(ev.data); };
    fuente.connect(nodo);
    // el worklet necesita estar conectado al grafo; lo silenciamos con ganancia 0
    const mudo = ctx.createGain();
    mudo.gain.value = 0;
    nodo.connect(mudo).connect(ctx.destination);
  } else {
    // navegadores antiguos: ScriptProcessorNode
    nodo = ctx.createScriptProcessor(4096, 1, 1);
    nodo.onaudioprocess = (ev) => {
      if (capturando) trozos.push(new Float32Array(ev.inputBuffer.getChannelData(0)));
    };
    fuente.connect(nodo);
    nodo.connect(ctx.destination);
  }
}

export function listo() {
  return Boolean(stream);
}

export function empezar() {
  trozos = [];
  capturando = true;
  if (ctx?.state === "suspended") ctx.resume();
}

export function parar() {
  capturando = false;
  const total = trozos.reduce((s, t) => s + t.length, 0);
  const onda = new Float32Array(total);
  let i = 0;
  for (const t of trozos) { onda.set(t, i); i += t.length; }
  trozos = [];
  const onda16 = remuestrear(onda, ctx ? ctx.sampleRate : SR_DESTINO, SR_DESTINO);
  // VAD on-device: gate de voz ANTES de subir (evita viaje al servidor si no hay voz)
  const voz = vad.analizarVoz(onda16, SR_DESTINO);
  return { blob: codificarWav(onda16), voz };
}

export function liberar() {
  capturando = false;
  trozos = [];
  try { fuente?.disconnect(); nodo?.disconnect(); } catch { /* ya desconectado */ }
  try { stream?.getTracks().forEach((t) => t.stop()); } catch { /* ya parado */ }
  try { ctx?.close(); } catch { /* ya cerrado */ }
  stream = ctx = nodo = fuente = null;
}

// Interpolación lineal: suficiente aquí (el servidor vuelve a remuestrear con librosa).
function remuestrear(onda, srOrigen, srDestino) {
  if (srOrigen === srDestino || !onda.length) return onda;
  const factor = srOrigen / srDestino;
  const n = Math.floor(onda.length / factor);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const pos = i * factor;
    const j = Math.floor(pos);
    const f = pos - j;
    out[i] = onda[j] * (1 - f) + (onda[Math.min(j + 1, onda.length - 1)] || 0) * f;
  }
  return out;
}

function codificarWav(onda, sr = SR_DESTINO) {
  const n = onda.length;
  const buf = new ArrayBuffer(44 + n * 2);
  const v = new DataView(buf);
  const escribe = (pos, s) => { for (let i = 0; i < s.length; i++) v.setUint8(pos + i, s.charCodeAt(i)); };
  escribe(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); escribe(8, "WAVE");
  escribe(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
  v.setUint16(22, 1, true); v.setUint32(24, sr, true); v.setUint32(28, sr * 2, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  escribe(36, "data"); v.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) {
    const x = Math.max(-1, Math.min(1, onda[i]));
    v.setInt16(44 + i * 2, x < 0 ? x * 0x8000 : x * 0x7FFF, true);
  }
  return new Blob([buf], { type: "audio/wav" });
}
