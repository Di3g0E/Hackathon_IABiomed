"""
Calibración del reconocedor por palabra (suelo de error del ASR).

Pasa las 227 grabaciones adultas CORRECTAS (data/processed/metadata.csv) por la decodificación
restringida y mide, por palabra, con qué frecuencia el reconocedor inventa cada proceso aunque
la palabra esté bien dicha. Resultado -> data/calibracion_palabras.csv:
  palabra, n, fiabilidad (1 = casi nunca falla), pcc_esperado, procesos_ruido (json {slug:freq})

Es INFORMATIVO: el cribado lo usa para avisar "interpretar con cautela" y sugerir repetir, NUNCA
para descontar errores (se prioriza la sensibilidad).

Ejecutar:  uv run python src/scripts/7_calibrar.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import librosa
import pandas as pd

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from app import herramientas
from pipeline.calibracion import ruta as ruta_calib
from pipeline.normas import ERRORES

SR = 16_000
META = os.path.join(RAIZ, "data", "processed", "metadata.csv")
NOMBRE_A_SLUG = {v: k for k, v in ERRORES.items()}


def main():
    df = pd.read_csv(META)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    print(f"Calibrando con {len(df)} grabaciones adultas (decodificación restringida)...")
    herramientas.get_w2v()       # carga el modelo una vez

    agg = {}   # palabra -> {n, con_error, procesos:{slug:count}, pcc:[...]}
    for k, r in df.iterrows():
        palabra = r["palabra"]
        wav, _ = librosa.load(os.path.join(RAIZ, r["ruta_proc"]), sr=SR, mono=True)
        rec = herramientas.puntuar_palabra(palabra, wav, estrategia="restringida",
                                           modo_infantil=False)
        a = agg.setdefault(palabra, {"n": 0, "con_error": 0, "procesos": {}, "pcc": []})
        a["n"] += 1
        a["pcc"].append(rec["pcc"])
        slugs = [e["tipo"] for e in rec["eventos"] if e["tipo"] in ERRORES]
        if slugs:
            a["con_error"] += 1
        for s in slugs:
            a["procesos"][s] = a["procesos"].get(s, 0) + 1
        if (k + 1) % 40 == 0:
            print(f"  {k + 1}/{len(df)}")

    filas = []
    for palabra, a in sorted(agg.items()):
        n = a["n"]
        filas.append({
            "palabra": palabra, "n": n,
            "fiabilidad": round(1.0 - a["con_error"] / n, 3),
            "pcc_esperado": round(sum(a["pcc"]) / n, 1),
            "procesos_ruido": json.dumps({s: round(c / n, 3) for s, c in a["procesos"].items()},
                                         ensure_ascii=False),
        })
    with open(ruta_calib(RAIZ), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["palabra", "n", "fiabilidad", "pcc_esperado", "procesos_ruido"])
        w.writeheader(); w.writerows(filas)

    print(f"\nEscrito {os.path.relpath(ruta_calib(RAIZ), RAIZ)} ({len(filas)} palabras).")
    flojas = sorted(filas, key=lambda x: x["fiabilidad"])[:8]
    print("Palabras menos fiables (más ruido del ASR):")
    for r in flojas:
        print(f"  {r['palabra']:10s} fiabilidad {r['fiabilidad']:.2f} | pcc_esp {r['pcc_esperado']:.0f} "
              f"| ruido {r['procesos_ruido']}")


if __name__ == "__main__":
    main()
