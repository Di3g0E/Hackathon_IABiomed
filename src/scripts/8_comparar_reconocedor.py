"""
A/B del reconocedor: compara las 4 combinaciones (libre/restringida × adulto/infantil)
sobre una sesión de audios, SIN perder ninguna. Sirve para decidir con datos qué estrategia
y qué modo conviene (la app usa por defecto restringida+adulto, pero esto deja probar todo).

Para cada palabra muestra los fonemas detectados, los procesos clínicos y el PER vs la
referencia; al final, un resumen por combinación (correctas, procesos, PER medio).

Ejecutar:
  uv run python src/scripts/8_comparar_reconocedor.py --sesion diego_6
  uv run python src/scripts/8_comparar_reconocedor.py --dir data/raw/nexdata_child   # clips infantiles
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import librosa

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from app import herramientas
from app.config import DIR_SESIONES
from pipeline.alineamiento import alinear
from pipeline.clinico import ref_clinico
from pipeline.normas import ERRORES

SR = 16_000
COMBOS = [("libre", False), ("libre", True), ("restringida", False), ("restringida", True)]


def _per(palabra, detectado):
    res = alinear(ref_clinico(palabra), detectado.split())
    return res.per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sesion", default="diego_6", help="carpeta en data/raw/sesiones/")
    ap.add_argument("--dir", default=None, help="carpeta de wav arbitraria (override de --sesion)")
    args = ap.parse_args()

    carpeta = args.dir or os.path.join(DIR_SESIONES, args.sesion)
    wavs = sorted(glob.glob(os.path.join(carpeta, "*.wav")))
    if not wavs:
        print(f"Sin wav en {carpeta}"); return
    print(f"Comparando {len(wavs)} palabras de {carpeta} (cargando modelo)...\n")
    herramientas.get_w2v()

    resumen = {c: {"correctas": 0, "procesos": 0, "per": []} for c in COMBOS}
    cab = f"{'palabra':10s}" + "".join(f"| {e+('/inf' if i else '/ad'):18s}"
                                       for e, i in COMBOS)
    print(cab)
    for w in wavs:
        pal = os.path.splitext(os.path.basename(w))[0]
        onda, _ = librosa.load(w, sr=SR, mono=True)
        celdas = []
        for est, inf in COMBOS:
            rec = herramientas.puntuar_palabra(pal, onda, estrategia=est, modo_infantil=inf)
            clin = [e["tipo"] for e in rec["eventos"] if e["tipo"] in ERRORES]
            per = _per(pal, rec["detectado"])
            r = resumen[(est, inf)]
            r["per"].append(per)
            if not clin and rec.get("valida", True):
                r["correctas"] += 1
            r["procesos"] += len(clin)
            celdas.append(f"| {rec['detectado'][:11]:11s}{'·'+clin[0][:4] if clin else '   ✓':6s}")
        print(f"{pal:10s}" + "".join(celdas))

    print("\n=== RESUMEN por combinación ===")
    print(f"{'estrategia/modo':22s} {'correctas':10s} {'procesos':9s} {'PER medio':9s}")
    for (est, inf) in COMBOS:
        r = resumen[(est, inf)]
        per_m = sum(r["per"]) / len(r["per"]) if r["per"] else 0
        modo = "infantil" if inf else "adulto"
        print(f"{est+'/'+modo:22s} {r['correctas']:<10d} {r['procesos']:<9d} {per_m:.3f}")
    print("\n(La app usa por defecto: restringida/adulto. Cambia con ESTRATEGIA_RECONOCEDOR y MODO_INFANTIL.)")


if __name__ == "__main__":
    main()
