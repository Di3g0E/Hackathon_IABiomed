// VAD/DSP ON-DEVICE: puerta de voz ligera en el cliente (energía + saturación), espejo
// del fallback de pipeline/vad.py (PICO_MIN, DUR_VOZ_MIN, CLIP_MAX). Corre en el móvil
// sobre las muestras ya capturadas, ANTES de subir nada: si no hay voz, evita un viaje al
// servidor y una inferencia inútil. La puerta clínica fina sigue en el servidor (silero).

const SR = 16000;
const PICO_MIN = 0.02;      // pico mínimo para considerar que hay sonido de voz
const DUR_VOZ_MIN = 0.12;   // s mínimos de voz
const CLIP_MAX = 0.02;      // fracción de muestras saturadas -> "saturado"
const FRAME = 320;          // 20 ms a 16 kHz

// Analiza muestras float32 (mono, 16 kHz). Devuelve {hayVoz, durVoz, clipping, motivo}.
export function analizarVoz(onda, sr = SR) {
  if (!onda || !onda.length) return { hayVoz: false, durVoz: 0, clipping: 0, motivo: "no se oyó la voz" };
  let pico = 0, saturadas = 0;
  for (let i = 0; i < onda.length; i++) {
    const a = Math.abs(onda[i]);
    if (a > pico) pico = a;
    if (a > 0.99) saturadas++;
  }
  const clipping = saturadas / onda.length;

  // duración de voz: fotogramas de 20 ms cuyo RMS supera un umbral relativo al pico
  const umbral = Math.max(PICO_MIN, pico * 0.15);
  let framesVoz = 0, frames = 0;
  for (let i = 0; i + FRAME <= onda.length; i += FRAME) {
    let s = 0;
    for (let j = i; j < i + FRAME; j++) s += onda[j] * onda[j];
    frames++;
    if (Math.sqrt(s / FRAME) >= umbral) framesVoz++;
  }
  const durVoz = (framesVoz * FRAME) / sr;
  const hayVoz = pico >= PICO_MIN && durVoz >= DUR_VOZ_MIN;

  let motivo = null;
  if (!hayVoz) motivo = "no se oyó la voz (¿micro lejos o no habló?)";
  else if (clipping > CLIP_MAX) motivo = "el sonido está saturado (baja el volumen o aleja el micro)";
  return { hayVoz, durVoz: Math.round(durVoz * 1000) / 1000, clipping, motivo };
}