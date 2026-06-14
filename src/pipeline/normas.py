"""
Normas de desarrollo fonológico por edad (tabla §8 del documento clínico).

Para cada uno de los 8 procesos fonológicos y cada edad (3-6 años) se guarda la
etiqueta original del documento y un NIVEL normalizado (escala ordinal única):
  - normal   : esperable a esa edad (NO cuenta como error impropio)
  - vigilar  : en transición / poco frecuente (NO cuenta, pero se reporta)
  - alerta   : impropio para la edad (CUENTA para el riesgo)

Es CONFIGURABLE: se escribe a data/normas_edad.csv y, si ese fichero existe, se
lee de ahí (la logopeda puede editar las celdas sin tocar código).

Ejecutar:  uv run python src/pipeline/normas.py   ->  (re)genera data/normas_edad.csv
"""
from __future__ import annotations

import csv
import os
import sys

# slug -> nombre legible (los 8 procesos del documento)
ERRORES = {
    "reduccion_grupos": "Reducción de grupos consonánticos",
    "sustitucion_r_l": "Sustitución r→l",
    "errores_rr": "Errores en rr",
    "omision_silabas": "Omisión de sílabas",
    "oclusivizacion": "Oclusivización",
    "simplificacion_diptongos": "Simplificación de diptongos",
    "omision_consonantes_finales": "Omisión de consonantes finales",
    "asimilaciones": "Asimilaciones",
}

# slug -> {edad: etiqueta original del documento}
_DOC = {
    "reduccion_grupos":            {3: "Normal", 4: "Normal", 5: "Alerta leve", 6: "Alerta"},
    "sustitucion_r_l":             {3: "Normal", 4: "Frecuente", 5: "Alerta leve", 6: "Alerta"},
    "errores_rr":                  {3: "Normal", 4: "Frecuente", 5: "Ocasional", 6: "Alerta"},
    "omision_silabas":             {3: "Normal", 4: "Ocasional", 5: "Alerta", 6: "Alerta"},
    "oclusivizacion":              {3: "Frecuente", 4: "Disminuye", 5: "Alerta", 6: "Alerta"},
    "simplificacion_diptongos":    {3: "Frecuente", 4: "Ocasional", 5: "Alerta", 6: "Alerta"},
    "omision_consonantes_finales": {3: "Frecuente", 4: "Ocasional", 5: "Alerta", 6: "Alerta"},
    "asimilaciones":               {3: "Frecuente", 4: "Disminuye", 5: "Raras", 6: "Patológicas"},
}

# etiqueta del documento -> nivel normalizado
ETIQUETA_A_NIVEL = {
    "Normal": "normal", "Frecuente": "normal",
    "Ocasional": "vigilar", "Disminuye": "vigilar", "Raras": "vigilar",
    "Alerta leve": "alerta", "Alerta": "alerta", "Patológicas": "alerta",
}
EDADES = [3, 4, 5, 6]


def _ruta(raiz):
    return os.path.join(raiz, "data", "normas_edad.csv")


def escribir_csv(raiz):
    filas = []
    for slug, nombre in ERRORES.items():
        for edad in EDADES:
            etq = _DOC[slug][edad]
            filas.append({"error": slug, "nombre": nombre, "edad": edad,
                          "etiqueta_doc": etq, "nivel": ETIQUETA_A_NIVEL[etq]})
    with open(_ruta(raiz), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["error", "nombre", "edad", "etiqueta_doc", "nivel"])
        w.writeheader(); w.writerows(filas)
    return filas


def cargar(raiz):
    """Devuelve dict {(error_slug, edad): nivel}. Lee el CSV si existe; si no, lo crea."""
    ruta = _ruta(raiz)
    if not os.path.exists(ruta):
        escribir_csv(raiz)
    tabla = {}
    with open(ruta, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            tabla[(r["error"], int(r["edad"]))] = r["nivel"]
    return tabla


def nivel(tabla, error_slug, edad):
    edad = max(3, min(6, int(edad)))
    return tabla.get((error_slug, edad), "vigilar")


def cuenta_para_riesgo(tabla, error_slug, edad):
    """Un error cuenta para el riesgo si su nivel es 'alerta' (impropio para la edad)."""
    return nivel(tabla, error_slug, edad) == "alerta"


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    filas = escribir_csv(raiz)
    print(f"Escrito data/normas_edad.csv ({len(filas)} celdas).")
    for slug, nombre in ERRORES.items():
        niveles = " ".join(f"{e}:{ETIQUETA_A_NIVEL[_DOC[slug][e]][:3]}" for e in EDADES)
        print(f"  {nombre:38s} {niveles}")