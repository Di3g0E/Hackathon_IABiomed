"""
Re-puntúa un informe tras editar manualmente los parámetros del sistema.

El profesional abre results/informe_<id>.json, corrige el campo 'detectado' de las
palabras que el sistema transcribió mal (p.ej. "res" -> "t ɾ e s") y ejecuta esto:
recalcula los 8 errores, el PCC y el riesgo, y guarda informe_<id>_revisado.json.

Ejecutar:  uv run python src/scripts/reanalizar.py results/informe_diego_6.json
"""
from __future__ import annotations

import os
import sys
import json
import glob

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from pipeline.clinico import ref_clinico, clasificar_errores, evaluar_riesgo
from pipeline.normas import cargar as cargar_normas

DIR_RES = os.path.join(RAIZ, "results")


def main():
    if len(sys.argv) > 1:
        ruta = sys.argv[1]
    else:
        cands = [p for p in glob.glob(os.path.join(DIR_RES, "informe_*.json"))
                 if "_revisado" not in p]
        if not cands:
            print("No hay informes en results/. Genera uno con app.py."); return
        ruta = max(cands, key=os.path.getmtime)
    with open(ruta, encoding="utf-8") as f:
        informe = json.load(f)

    edad = int(informe["registro"]["edad"])
    tabla = cargar_normas(RAIZ)
    for p in informe["palabras"]:
        ref = ref_clinico(p["palabra"])
        hyp = p["detectado"].split()
        cl = clasificar_errores(ref, hyp)
        p["eventos"], p["pcc"] = cl["eventos"], cl["pcc"]
        p["valida"], p["motivo_no_valida"] = cl["valida"], cl["motivo_no_valida"]
    informe["resumen_riesgo"] = evaluar_riesgo(informe["palabras"], edad, tabla)

    salida = ruta.replace(".json", "_revisado.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)
    r = informe["resumen_riesgo"]
    print(f"Re-puntuado desde: {os.path.relpath(ruta, RAIZ)}")
    print(f"  Riesgo: {r['riesgo'].upper()} | impropios: {r['n_errores_impropios']} | "
          f"correctas: {r['palabras_correctas']} | a repetir: {len(r['palabras_a_repetir'])}")
    print(f"  Guardado: {os.path.relpath(salida, RAIZ)}")


if __name__ == "__main__":
    main()