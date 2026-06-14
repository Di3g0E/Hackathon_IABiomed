"""
Informe PALABRA A PALABRA en HTML (plantilla de marca templates/informe_palabras.html).

Cara profesional para el especialista: por cada palabra grabada de una prueba, el audio
embebido, la forma de onda y la línea de tiempo de las letras (fonemas) detectadas con su
instante y confianza. Reutiliza revision_html.construir_datos_sesion (reprocesa los wav con
el reconocedor: alineamiento temporal por fonema) y solo añade la presentación on-brand.

Se sirve en GET /sesion/{sesion_id}/palabras.html y se abre/descarga (audio en base64 →
autocontenido). Imprimible a PDF con Ctrl+P.
"""
from __future__ import annotations

import base64
import os
import sys
from datetime import date

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import herramientas, revision_html
from app.config import DIR_STATIC

_TPL_DIR = os.path.join(SRC, "app", "templates")
_ENV = Environment(loader=FileSystemLoader(_TPL_DIR),
                   autoescape=select_autoescape(["html", "xml"]))


def _logo_data_uri():
    ruta = os.path.join(DIR_STATIC, "brand", "habli-logo.png")
    try:
        with open(ruta, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return "/static/brand/habli-logo.png"


def _wave_poly(peaks, w=100.0, h=30.0):
    """Polígono SVG (envolvente reflejada) de la forma de onda a partir de los picos 0-1."""
    peaks = peaks or [0.0]
    n = len(peaks)
    mid = h / 2
    amp = mid - 1
    paso = w / max(1, n - 1)
    arriba = [(i * paso, mid - p * amp) for i, p in enumerate(peaks)]
    abajo = [(i * paso, mid + p * amp) for i, p in enumerate(peaks)][::-1]
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in arriba + abajo)


def desde_sesion(sesion_id, edad=None):
    """Renderiza el HTML del detalle por palabra de una prueba (sesion_id = '<nino>_p<N>')."""
    nino_id = sesion_id.rsplit("_p", 1)[0]
    n_prueba = sesion_id.rsplit("_p", 1)[1] if "_p" in sesion_id else "—"
    nino = herramientas.obtener_nino(nino_id) or {}
    if edad is None:
        edad = nino.get("edad") or 5

    datos = revision_html.construir_datos_sesion(sesion_id, edad=edad)
    for w in datos["palabras"]:
        w["wave_poly"] = _wave_poly(w.get("peaks"))
        finmax = max((s["t_fin"] for s in w.get("segmentos", [])), default=0) or 0
        w["dur"] = w.get("duracion") or finmax or 1

    return _ENV.get_template("informe_palabras.html").render(
        alias=nino.get("alias") or nino_id,
        edad=edad,
        n_prueba=n_prueba,
        sesion=sesion_id,
        fecha=date.today().strftime("%d/%m/%Y"),
        anio=str(date.today().year),
        logo_src=_logo_data_uri(),
        resumen=datos.get("resumen"),
        palabras=datos["palabras"],
    )
