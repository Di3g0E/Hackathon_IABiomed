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

import glob

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import herramientas, revision_html
from app.config import DIR_RESULTS, DIR_SESIONES, DIR_STATIC

_TPL_DIR = os.path.join(SRC, "app", "templates")
_ENV = Environment(loader=FileSystemLoader(_TPL_DIR),
                   autoescape=select_autoescape(["html", "xml"]))
_TPL_FILE = os.path.join(_TPL_DIR, "informe_palabras.html")


def _cache_fresca(salida, sesion_id):
    """True si el HTML cacheado existe y es más nuevo que los wav de la sesión, la
    plantilla y este módulo (reprocesar los audios con el modelo es lo caro)."""
    if not os.path.exists(salida):
        return False
    m_out = os.path.getmtime(salida)
    entradas = glob.glob(os.path.join(DIR_SESIONES, sesion_id, "*.wav"))
    entradas += [_TPL_FILE, os.path.abspath(__file__)]
    return all(os.path.getmtime(e) <= m_out for e in entradas if os.path.exists(e))


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


def desde_sesion(sesion_id, edad=None, usar_cache=True):
    """HTML del detalle por palabra de una prueba (sesion_id='<nino>_p<N>').
    Cachea el resultado: reprocesar los audios con el modelo es lo caro (~1 s/palabra),
    así que las aperturas posteriores son instantáneas mientras los wav no cambien."""
    salida = os.path.join(DIR_RESULTS, f"palabras_{sesion_id}.html")
    if usar_cache and _cache_fresca(salida, sesion_id):
        with open(salida, encoding="utf-8") as f:
            return f.read()

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

    html = _ENV.get_template("informe_palabras.html").render(
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
    try:
        os.makedirs(DIR_RESULTS, exist_ok=True)
        with open(salida, "w", encoding="utf-8") as f:
            f.write(html)
    except OSError:
        pass
    return html
