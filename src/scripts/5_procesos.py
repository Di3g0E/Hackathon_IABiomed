"""
Paso 5 — T1 clínico: detección de PROCESOS FONOLÓGICOS + PCC.

Reutiliza el reconocedor wav2vec2; sobre adultos da la línea base (PCC alto).
Produce la salida de cribado (JSON) que consumiría la app.

Ejecutar:  uv run python src/scripts/5_procesos.py
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

from pipeline.reconocedor import W2V, normaliza_sec, buscar_ref
from pipeline.procesos_fonologicos import detectar_procesos

META = os.path.join(RAIZ, "data", "processed", "metadata.csv")
DIR_RES = os.path.join(RAIZ, "results")
PCC_MEDIO, PCC_ALTO = 90.0, 75.0


def riesgo(pcc):
    return "bajo" if pcc >= PCC_MEDIO else ("medio" if pcc >= PCC_ALTO else "alto")


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
        ref, hip = buscar_ref(r["palabra"]), normaliza_sec(w2v.reconoce(wav))
        d = detectar_procesos(ref, hip)
        for p in d["procesos"]:
            procesos_tot[p.split(" (")[0]] += 1
        filas.append({"palabra": r["palabra"], "hablante": r["hablante"], "origen": r["origen"],
                      "pcc": d["pcc"], "n_procesos": d["n_procesos"],
                      "procesos": "; ".join(d["procesos"]),
                      "esperado": " ".join(ref), "detectado": " ".join(hip)})
    dur = time.perf_counter() - t0
    res = pd.DataFrame(filas)
    os.makedirs(DIR_RES, exist_ok=True)
    res.to_csv(os.path.join(DIR_RES, "procesos_por_clip.csv"), index=False, encoding="utf-8")

    print(f"\nProcesados {len(res)} clips en {dur:.1f}s | PCC medio (adultos): {res['pcc'].mean():.1f}%")
    for orig, sub in res.groupby("origen"):
        print(f"    {orig:10s} n={len(sub):3d}  PCC={sub['pcc'].mean():.1f}%")
    print("Procesos por tipo (línea base adulta):")
    for tipo, n in procesos_tot.most_common():
        print(f"    {n:4d}  {tipo}")

    if procesos_tot:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        tipos, vals = zip(*procesos_tot.most_common())
        ax.barh(range(len(tipos)), vals, color="#c0392b")
        ax.set_yticks(range(len(tipos))); ax.set_yticklabels(tipos, fontsize=8); ax.invert_yaxis()
        ax.set_title("Frecuencia de procesos fonológicos (línea base adulta)")
        fig.tight_layout(); fig.savefig(os.path.join(DIR_RES, "procesos_frecuencia.png"), dpi=120)

    ej = res.iloc[0]
    screening = {
        "hablante": ej["hablante"], "palabra": ej["palabra"], "origen": ej["origen"],
        "fonemas_esperados": ej["esperado"].split(), "fonemas_detectados": ej["detectado"].split(),
        "pcc": ej["pcc"],
        "procesos_fonologicos": ej["procesos"].split("; ") if ej["procesos"] else [],
        "riesgo_palabra": riesgo(ej["pcc"]),
        "_nota": "Riesgo por palabra ilustrativo; el cribado real agrega todas las "
                 "palabras del niño y calibra umbrales con normas por edad.",
    }
    with open(os.path.join(DIR_RES, "ejemplo_screening.json"), "w", encoding="utf-8") as f:
        json.dump(screening, f, ensure_ascii=False, indent=2)
    print("\nGuardado: results/procesos_por_clip.csv, procesos_frecuencia.png, ejemplo_screening.json")


if __name__ == "__main__":
    main()