"""
DEMO longitudinal end-to-end: prueba 1 -> ejercicios -> prueba 2 -> evolución + PDF.

Como aún no hay grabaciones infantiles repetidas, simula la mejora: puntúa una sesión
real como PRUEBA 1, y construye la PRUEBA 2 "corrigiendo" parte de los errores (efecto
de los ejercicios). Registra los eventos con fechas retro en la BD y genera el PDF con la evolución
(deltas + tiempos entre pruebas y ejercicios).

Ejecutar:  uv run python src/scripts/demo_longitudinal.py
"""
from __future__ import annotations

import copy
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

from app import almacen, herramientas, informe_pdf
from app.config import DIR_SESIONES
from pipeline.normas import ERRORES

SR = 16_000
NINO = "evo_demo"
EDAD = 5


def main():
    wavs = sorted(glob.glob(os.path.join(DIR_SESIONES, "diego_6", "*.wav")))
    if not wavs:
        raise SystemExit("Falta data/raw/sesiones/diego_6 (sesión de ejemplo).")
    print(f"Puntuando {len(wavs)} palabras como PRUEBA 1 (cargando modelo)...")
    palabras1 = []
    for w in wavs:
        palabra = os.path.splitext(os.path.basename(w))[0]
        onda, _ = librosa.load(w, sr=SR, mono=True)
        palabras1.append(herramientas.puntuar_palabra(palabra, onda))
    inf1 = {"registro": {"nombre": NINO, "edad": EDAD},
            "resumen_riesgo": herramientas.evaluar_sesion(palabras1, EDAD), "palabras": palabras1}

    # PRUEBA 2: simula el efecto de los ejercicios corrigiendo la mitad de las palabras con error.
    palabras2 = copy.deepcopy(palabras1)
    con_error = [p for p in palabras2 if any(e["tipo"] in ERRORES for e in p["eventos"])]
    for p in con_error[: max(1, len(con_error) // 2 + 1)]:
        p["detectado"] = p["esperado"]      # ya lo dice bien
        p["confianza"] = max(p.get("confianza", 0.8), 0.85)
    inf2 = herramientas.repuntuar_informe(
        {"registro": {"nombre": NINO, "edad": EDAD}, "palabras": palabras2})

    # Registrar la línea temporal con fechas retro.
    conn = almacen.conectar(RAIZ)
    conn.execute("DELETE FROM eventos WHERE nino_id=?", (NINO,))
    conn.commit()
    almacen.registrar_nino(conn, NINO, alias="Peque (demo)", edad=EDAD, sexo="m",
                           factores={"bilingue": True})
    almacen.añadir_evento(conn, NINO, "screening", {"riesgo_preliminar": "medio"},
                          ts="2026-03-01T10:00:00+00:00")
    almacen.añadir_evento(conn, NINO, "prueba_audio", inf1, ts="2026-03-01T10:10:00+00:00")
    almacen.añadir_evento(conn, NINO, "ejercicios_asignados",
                          herramientas.proponer_ejercicios_para(inf1["resumen_riesgo"], EDAD),
                          ts="2026-03-06T10:00:00+00:00")
    almacen.añadir_evento(conn, NINO, "prueba_audio", inf2, ts="2026-04-20T10:00:00+00:00")
    conn.close()

    ev = herramientas.evolucion_longitudinal(NINO)
    print("\n=== EVOLUCIÓN ===")
    print(f"  Prueba 1: riesgo {ev['pruebas'][0]['riesgo']}, impropios "
          f"{ev['pruebas'][0]['n_errores_impropios']}, PCC {ev['pruebas'][0]['pcc_medio']}")
    print(f"  Prueba 2: riesgo {ev['pruebas'][1]['riesgo']}, impropios "
          f"{ev['pruebas'][1]['n_errores_impropios']}, PCC {ev['pruebas'][1]['pcc_medio']}")
    print(f"  Cambio de riesgo: {ev['delta']['riesgo']}")
    print(f"  Δ impropios: {ev['delta']['n_errores_impropios']} | "
          f"Δ PCC: {ev['delta']['pcc_medio']} | Δ inteligibilidad: {ev['delta']['inteligibilidad_media']}")
    print(f"  Días entre pruebas: {ev['dias_entre_pruebas']} | "
          f"ejercicios entre pruebas: {ev['n_ejercicios_entre_pruebas']}")

    pdf = informe_pdf.desde_nino(NINO)
    print(f"\nPDF longitudinal: {os.path.relpath(pdf, RAIZ)}")


if __name__ == "__main__":
    main()
