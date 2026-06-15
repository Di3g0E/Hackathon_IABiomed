"""
Compara el reconocedor FULL (fp32, cloud) vs EDGE (int8 cuantizado, móvil) sobre los
mismos audios: calidad (PER, F1 por fonema), latencia por palabra y peso del modelo.

Es la "prueba de ambos sistemas" del fork móvil: mide cuánta calidad se pierde (si alguna)
al cuantizar y cuánto se gana en peso/velocidad.

Ejecutar:
  uv run python src/scripts/10_comparar_cuantizado.py            # 2 clips por palabra
  uv run python src/scripts/10_comparar_cuantizado.py --por-palabra 4
  uv run python src/scripts/10_comparar_cuantizado.py --todos    # todos los clips
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import librosa

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from pipeline.alineamiento import agregar, alinear
from pipeline.clinico import normaliza_clinico, ref_clinico
from pipeline.reconocedor import W2V
from pipeline import cuantizacion as cz

SR = 16_000
# los audios (data/processed) están gitignorados y viven en el repo principal; el fork
# (worktree) no los tiene, así que se comparten desde el repo hermano "IABiomed".
DIR_PROC = os.path.join(RAIZ, "data", "processed")
if not os.path.isdir(DIR_PROC):
    DIR_PROC = os.path.join(os.path.dirname(RAIZ), "IABiomed", "data", "processed")


def _clips(por_palabra):
    """Toma hasta `por_palabra` clips por carpeta-palabra de data/processed."""
    pares = []
    for palabra in sorted(os.listdir(DIR_PROC)):
        d = os.path.join(DIR_PROC, palabra)
        if not os.path.isdir(d):
            continue
        wavs = sorted(glob.glob(os.path.join(d, "*.wav")))
        if por_palabra:
            wavs = wavs[:por_palabra]
        for w in wavs:
            pares.append((palabra, w))
    return pares


def _evaluar(w2v, clips):
    """Devuelve (per_medio, f1_micro, latencia_media_ms) sobre los clips."""
    resultados, latencias = [], []
    for palabra, ruta in clips:
        onda, _ = librosa.load(ruta, sr=SR, mono=True)
        t0 = time.perf_counter()
        fon, _conf = w2v.reconoce_conf(onda)
        latencias.append((time.perf_counter() - t0) * 1000)
        hyp = normaliza_clinico(fon)
        resultados.append(alinear(ref_clinico(palabra), hyp))
    glob_res = agregar(resultados)
    per_medio = sum(r.per for r in resultados) / len(resultados)
    return per_medio, glob_res.f1, sum(latencias) / len(latencias)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--por-palabra", type=int, default=2, help="clips por palabra (0=todos)")
    ap.add_argument("--todos", action="store_true", help="usa todos los clips")
    args = ap.parse_args()
    por_palabra = 0 if args.todos else args.por_palabra

    clips = _clips(por_palabra)
    if not clips:
        print(f"Sin clips en {DIR_PROC}"); return
    print(f"Comparando sobre {len(clips)} clips de {DIR_PROC}\n")

    print("Cargando modelo FULL (fp32)…", flush=True)
    full = W2V()
    full.model = full.model.to("cpu").eval()      # CPU para una comparación justa con edge
    full.dev = "cpu"
    mb_full = cz.tamano_mb(full.model)

    print("Cuantizando a INT8 (edge) y exportando…", flush=True)
    edge = W2V.__new__(W2V)                        # reusa estructura sin recargar pesos
    edge.fe, edge.id2tok, edge.especiales, edge.dev = full.fe, full.id2tok, full.especiales, "cpu"
    edge.model = cz.cuantizar_modelo(full.model)
    ruta_export = os.path.join(RAIZ, "results", "w2v_int8_edge.pt")
    mb_edge = cz.exportar(edge.model, ruta_export)

    print("Evaluando FULL…", flush=True)
    per_f, f1_f, lat_f = _evaluar(full, clips)
    print("Evaluando EDGE (int8)…", flush=True)
    per_e, f1_e, lat_e = _evaluar(edge, clips)

    print("\n================ COMPARACIÓN FULL (cloud) vs EDGE (móvil) ================")
    cab = f"{'sistema':18s}{'peso MB':>10s}{'PER↓':>9s}{'F1↑':>9s}{'latencia/clip':>16s}"
    print(cab)
    print(f"{'FULL fp32':18s}{mb_full:>10.1f}{per_f:>9.3f}{f1_f:>9.3f}{lat_f:>13.0f} ms")
    print(f"{'EDGE int8':18s}{mb_edge:>10.1f}{per_e:>9.3f}{f1_e:>9.3f}{lat_e:>13.0f} ms")
    print("-" * 74)
    d_per = per_e - per_f
    d_f1 = f1_e - f1_f
    print(f"{'Δ (edge-full)':18s}{mb_edge - mb_full:>10.1f}{d_per:>+9.3f}{d_f1:>+9.3f}"
          f"{(lat_f / lat_e if lat_e else 0):>11.2f}×  ")
    print(f"\nPeso: {mb_full:.1f} → {mb_edge:.1f} MB ({100 * (1 - mb_edge / mb_full):.0f}% menos). "
          f"Velocidad: {lat_f / lat_e:.2f}× más rápido. "
          f"Calidad: PER {d_per:+.3f}, F1 {d_f1:+.3f} (≈0 = se mantiene).")
    print(f"Modelo edge exportado en: {os.path.relpath(ruta_export, RAIZ)}")


if __name__ == "__main__":
    main()