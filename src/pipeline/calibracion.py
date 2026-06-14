"""
Calibración por palabra: suelo de error del reconocedor en habla adulta CORRECTA.

Con las 227 grabaciones adultas (que dicen bien las 32 palabras), medimos con qué frecuencia
el reconocedor inventa cada proceso fonológico aunque la palabra esté bien dicha. Eso da, por
palabra: una FIABILIDAD (1 = el ASR casi nunca se equivoca) y los procesos que son RUIDO típico
del ASR en esa palabra.

USO (importante): es solo INFORMATIVO. Marca "interpretar con cautela" para el profesional y
alimenta la sugerencia de repetir, pero NUNCA descuenta un proceso del conteo de riesgo (se
prioriza la sensibilidad: mejor falso positivo que falso negativo).

El CSV lo genera scripts/7_calibrar.py -> data/calibracion_palabras.csv.
"""
from __future__ import annotations

import csv
import json
import os

# fiabilidad por debajo de la cual una palabra se considera "poco fiable" (sugerir repetir)
UMBRAL_BAJA_FIABILIDAD = 0.6
# frecuencia de un proceso-ruido por encima de la cual se marca 'posible artefacto del ASR'
UMBRAL_ARTEFACTO = 0.15


def ruta(raiz):
    return os.path.join(raiz, "data", "calibracion_palabras.csv")


def cargar(raiz):
    """Devuelve {palabra: {fiabilidad, pcc_esperado, procesos_ruido{slug:freq}}} o {} si no existe."""
    r = ruta(raiz)
    if not os.path.exists(r):
        return {}
    out = {}
    with open(r, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["palabra"]] = {
                "fiabilidad": float(row["fiabilidad"]),
                "pcc_esperado": float(row["pcc_esperado"]),
                "n": int(row["n"]),
                "procesos_ruido": json.loads(row["procesos_ruido"] or "{}"),
            }
    return out


def es_artefacto(calib, palabra, slug):
    """True si 'slug' es ruido típico del ASR en 'palabra' (interpretar con cautela)."""
    info = calib.get(palabra)
    return bool(info and info["procesos_ruido"].get(slug, 0.0) >= UMBRAL_ARTEFACTO)


def fiabilidad(calib, palabra):
    info = calib.get(palabra)
    return info["fiabilidad"] if info else None
