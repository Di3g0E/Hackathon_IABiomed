"""
Fase 4c (runner) — Aplica el detector de procesos fonológicos sobre los audios.

Reutiliza el reconocedor wav2vec2 (ganador en 4b) y la referencia plegada.
Sobre adultos sirve de LÍNEA BASE (deben dar PCC alto y pocos procesos reales);
el mismo pipeline, aplicado a un niño, produce la señal de cribado.

Salidas:
  results/procesos_por_clip.csv   (PCC y procesos por audio)
  results/procesos_frecuencia.png (frecuencia de cada tipo de proceso)
  results/ejemplo_screening.json  (salida estructurada que consumiría la app)

Ejecutar:  uv run python src/scripts/detectar_procesos.py
"""
from __future__ import annotations

import os
import sys
import json
import time
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd
import librosa
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from scripts.reconocer_fonemas import W2V, normaliza_sec, buscar_ref
from pipeline.procesos_fonologicos import detectar_procesos

META = os.path.join(RAIZ, "data", "processed", "metadata.csv")
DIR_RES = os.path.join(RAIZ, "results")
PCC_MEDIO, PCC_ALTO = 90.0, 75.0   # umbrales placeholder (calibrar con normas por edad)


def riesgo(pcc: float) -> str:
    if pcc >= PCC_MEDIO:
        return "bajo"
    if pcc >= PCC_ALTO:
        return "medio"
    return "alto"


def tipo_proceso(p: str) -> str:
    return p.split(" (")[0]


def main():
    df = pd.read_csv(META)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    df["abs"] = df["ruta_proc"].apply(lambda r: os.path.join(RAIZ, r))

    print("Cargando wav2vec2...")
    w2v = W2V()

    filas, procesos_tot = [], Counter()
    t0 = time.perf_counter()
    for _, r in df.iterrows():
        wav, _ = librosa.load(r["abs"], sr=16000)
        ref = buscar_ref(r["palabra"])
        hip = normaliza_sec(w2v.reconoce(wav))
        d = detectar_procesos(ref, hip)
        for p in d["procesos"]:
            procesos_tot[tipo_proceso(p)] += 1
        filas.append({
            "palabra": r["palabra"], "hablante": r["hablante"], "origen": r["origen"],
            "pcc": d["pcc"], "n_procesos": d["n_procesos"],
            "procesos": "; ".join(d["procesos"]),
            "esperado": " ".join(ref), "detectado": " ".join(hip),
        })
    dur = time.perf_counter() - t0
    res = pd.DataFrame(filas)

    os.makedirs(DIR_RES, exist_ok=True)
    res.to_csv(os.path.join(DIR_RES, "procesos_por_clip.csv"), index=False, encoding="utf-8")

    # ---- Resumen ----
    print(f"\nProcesados {len(res)} clips en {dur:.1f}s ({dur/len(res)*1000:.0f} ms/clip)")
    print(f"PCC medio (adultos, línea base): {res['pcc'].mean():.1f}%")
    print("PCC medio por origen:")
    for orig, sub in res.groupby("origen"):
        print(f"    {orig:10s} n={len(sub):3d}  PCC={sub['pcc'].mean():.1f}%")
    print(f"\nProcesos detectados por tipo (en habla adulta correcta = artefactos/dialecto):")
    for tipo, n in procesos_tot.most_common():
        print(f"    {n:4d}  {tipo}")

    # ---- Figura ----
    if procesos_tot:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        tipos, valores = zip(*procesos_tot.most_common())
        ax.barh(range(len(tipos)), valores, color="#c0392b")
        ax.set_yticks(range(len(tipos))); ax.set_yticklabels(tipos, fontsize=8)
        ax.invert_yaxis(); ax.set_title("Frecuencia de procesos fonológicos (línea base adulta)")
        fig.tight_layout()
        fig.savefig(os.path.join(DIR_RES, "procesos_frecuencia.png"), dpi=120)

    # ---- Ejemplo de salida para la app (formato screening) ----
    ej = res.iloc[0]
    screening = {
        "hablante": ej["hablante"], "palabra": ej["palabra"], "origen": ej["origen"],
        "fonemas_esperados": ej["esperado"].split(),
        "fonemas_detectados": ej["detectado"].split(),
        "pcc": ej["pcc"],
        "procesos_fonologicos": ej["procesos"].split("; ") if ej["procesos"] else [],
        "riesgo_palabra": riesgo(ej["pcc"]),
        "_nota": "Riesgo por palabra ilustrativo; el cribado real agrega todas las "
                 "palabras del niño y calibra umbrales con normas por edad.",
    }
    with open(os.path.join(DIR_RES, "ejemplo_screening.json"), "w", encoding="utf-8") as f:
        json.dump(screening, f, ensure_ascii=False, indent=2)
    print("\nEjemplo de salida (app):")
    print(json.dumps(screening, ensure_ascii=False, indent=2))
    print(f"\nGuardado: results/procesos_por_clip.csv, procesos_frecuencia.png, ejemplo_screening.json")


if __name__ == "__main__":
    main()
