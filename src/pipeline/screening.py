"""
Cribado/triaje previo a la prueba de audio (diapositiva 3: "Test de Screening").

Cuestionario breve a los padres (anamnesis) que produce un RIESGO PRELIMINAR y, sobre
todo, registra FACTORES DE EQUIDAD (bilingüismo, audición/otitis, estructura orofacial,
resfriado) que son confounds conocidos del habla (docs/mejoras_clinicas.md §4): se
muestran en el informe y ATENÚAN la derivación, para no sobre-derivar a niños bilingües
o con otitis. Las "banderas" son marcadores de desarrollo observables por la familia.

Es CONFIGURABLE: se vuelca a data/screening_items.csv y se lee de ahí si existe
(la logopeda puede editar el texto/peso de los ítems sin tocar código).

Encuadre: triaje orientativo, NO diagnóstico. Prima la sensibilidad (mejor sobre-avisar
y que la prueba de audio + el profesional afinen).

Ejecutar:  uv run python src/pipeline/screening.py   ->  (re)genera data/screening_items.csv
"""
from __future__ import annotations

import csv
import os
import sys

# id, texto (pregunta a los padres, respuesta Sí/No), factor, peso
# factor 'equidad'  = confound que se reporta y atenúa (NO suma riesgo)
# factor 'bandera'  = marcador de desarrollo (suma riesgo según peso)
_ITEMS = [
    # --- Factores de equidad / confounds (no puntúan, condicionan la lectura) ---
    # NOTA: bilingüismo y audición se preguntan ahora en el REGISTRO (sign-in), no aquí.
    {"id": "orofacial", "factor": "equidad", "peso": 0,
     "texto": "¿Os han comentado algo del frenillo de la lengua, paladar o dentición?"},
    {"id": "resfriado", "factor": "equidad", "peso": 0,
     "texto": "¿Está hoy resfriado o muy congestionado?"},
    # --- Banderas de desarrollo (observables por la familia) ---
    {"id": "inteligibilidad", "factor": "bandera", "peso": 2,
     "texto": "¿Le cuesta que personas de fuera de la familia le entiendan al hablar?"},
    {"id": "tardio", "factor": "bandera", "peso": 2,
     "texto": "¿Empezó a hablar (primeras palabras o frases) más tarde que otros niños?"},
    {"id": "frases_cortas", "factor": "bandera", "peso": 1,
     "texto": "¿Usa frases más cortas o simples que otros niños de su edad?"},
    {"id": "encontrar_palabras", "factor": "bandera", "peso": 1,
     "texto": "¿Le cuesta encontrar las palabras o las confunde a menudo?"},
    {"id": "instrucciones", "factor": "bandera", "peso": 1,
     "texto": "¿Tiene dificultad para seguir instrucciones de varios pasos?"},
    {"id": "antecedentes", "factor": "bandera", "peso": 1,
     "texto": "¿Hay antecedentes familiares de dificultades del lenguaje?"},
]

CAMPOS = ["id", "texto", "factor", "peso"]
# umbrales sobre la puntuación de banderas (peso total posible = 8)
UMBRAL_MEDIO = 2
UMBRAL_ALTO = 5


def _ruta(raiz):
    return os.path.join(raiz, "data", "screening_items.csv")


def escribir_csv(raiz):
    with open(_ruta(raiz), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for it in _ITEMS:
            w.writerow({k: it[k] for k in CAMPOS})
    return _ITEMS


def cargar(raiz):
    """Devuelve la lista de ítems. Lee el CSV si existe; si no, lo crea."""
    ruta = _ruta(raiz)
    if not os.path.exists(ruta):
        escribir_csv(raiz)
    items = []
    with open(ruta, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            items.append({"id": r["id"], "texto": r["texto"], "factor": r["factor"],
                          "peso": int(r["peso"])})
    return items


def evaluar_screening(respuestas, edad, items=None, raiz=None):
    """Evalúa el cuestionario.

    respuestas: dict {item_id: bool}  (True = Sí).
    Devuelve {riesgo_preliminar, puntuacion, banderas[], factores_equidad[], nota}.
    """
    if items is None:
        items = cargar(raiz) if raiz else _ITEMS
    edad = max(3, min(6, int(edad)))
    by_id = {it["id"]: it for it in items}

    banderas, factores, puntuacion = [], [], 0
    for iid, val in respuestas.items():
        it = by_id.get(iid)
        if not it or not val:
            continue
        if it["factor"] == "equidad":
            factores.append(it["texto"])
        else:
            banderas.append(it["texto"])
            puntuacion += it["peso"]

    if puntuacion >= UMBRAL_ALTO:
        riesgo = "alto"
    elif puntuacion >= UMBRAL_MEDIO:
        riesgo = "medio"
    else:
        riesgo = "bajo"

    nota = ("Triaje orientativo a partir de lo que cuenta la familia; no es un diagnóstico. "
            "La prueba de sonidos y el profesional son los que afinan el resultado.")
    if factores:
        nota += (" Atención: hay factores (bilingüismo, audición, etc.) que pueden explicar "
                 "parte de las dificultades; se tendrán en cuenta para no sobreestimar el riesgo.")
    return {
        "edad": edad, "riesgo_preliminar": riesgo, "puntuacion": puntuacion,
        "banderas": banderas, "factores_equidad": factores, "nota": nota,
    }


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    items = escribir_csv(raiz)
    print(f"Escrito data/screening_items.csv ({len(items)} ítems).")

    demos = {
        "bajo (sin banderas)": {},
        "medio (2 banderas)": {"frases_cortas": True, "instrucciones": True},
        "alto (inteligibilidad+tardío+más)": {"inteligibilidad": True, "tardio": True,
                                              "frases_cortas": True, "orofacial": True},
    }
    for nombre, resp in demos.items():
        r = evaluar_screening(resp, edad=4, raiz=raiz)
        print(f"\n  {nombre} -> {r['riesgo_preliminar'].upper()} (punt {r['puntuacion']})")
        if r["factores_equidad"]:
            print(f"     confounds: {len(r['factores_equidad'])} -> {r['factores_equidad']}")
