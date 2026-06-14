"""
Informe clínico en HTML (plantilla de marca templates/informe_clinico.html).

Es la cara PROFESIONAL del informe (modo clínico, sin Lali): se sirve en /informe/{id}/html
y se abre en el navegador; el especialista puede imprimirlo a PDF (Ctrl+P, la plantilla ya
tiene @page A4 y pie legal en cada hoja). Reutiliza el mismo dict 'datos' que el PDF
(app.informe_pdf.datos_desde_nino / datos_desde_informe) para no duplicar la lógica clínica.

El logo se embebe como data-URI para que el HTML descargado sea autocontenido.
"""
from __future__ import annotations

import base64
import os
import sys
from datetime import date

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import informe_pdf
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


def renderizar(datos):
    """datos: mismo dict que informe_pdf.generar_pdf -> HTML (str)."""
    datos = dict(datos)
    datos.setdefault("logo_src", _logo_data_uri())
    datos.setdefault("fecha", date.today().strftime("%d/%m/%Y"))
    datos.setdefault("anio", str(date.today().year))
    return _ENV.get_template("informe_clinico.html").render(**datos)


def desde_nino(nino_id):
    return renderizar(informe_pdf.datos_desde_nino(nino_id))


def desde_informe(ruta):
    return renderizar(informe_pdf.datos_desde_informe(ruta))
