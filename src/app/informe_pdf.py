"""
Export del informe en PDF (resumen claro y conciso para el especialista/familia).

Contiene: registro + triaje de screening + resultado de la(s) prueba(s) de audio
(semáforo, errores, PCC/severidad, procesos) + EVOLUCIÓN entre la 1ª y la 2ª prueba
(deltas + tiempos entre pruebas y ejercicios) + ejercicios propuestos + encuadre
cribado != diagnóstico + factores de equidad.

Reutiliza el patrón FPDF de scripts/generate_pdf.py y las fuentes DejaVu de la raíz.

Ejecutar:
  uv run python -m app.informe_pdf results/informe_diego_6.json   # desde un informe
  uv run python -m app.informe_pdf --nino diego_6                  # longitudinal (BD)
"""
from __future__ import annotations

import os
import sys

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from fpdf import FPDF

from app import almacen, herramientas
from app.config import DIR_RESULTS

SEMAFORO = {"bajo": (34, 197, 94), "medio": (234, 179, 8), "alto": (239, 68, 68)}
SLATE = (30, 41, 59)
GRIS = (100, 116, 139)
FUENTE = os.path.join(RAIZ, "DejaVuSans.ttf")
FUENTE_B = os.path.join(RAIZ, "DejaVuSans-Bold.ttf")


def _asegura_fuentes():
    import ssl
    import urllib.request
    ssl._create_default_https_context = ssl._create_unverified_context
    urls = {
        FUENTE: "https://raw.githubusercontent.com/prawnpdf/prawn/master/data/fonts/DejaVuSans.ttf",
        FUENTE_B: "https://raw.githubusercontent.com/prawnpdf/prawn/master/data/fonts/DejaVuSans-Bold.ttf",
    }
    for ruta, url in urls.items():
        if not os.path.exists(ruta):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(ruta, "wb") as out:
                out.write(resp.read())


class InformePDF(FPDF):
    def header(self):
        self.set_fill_color(*SLATE)
        self.rect(0, 0, 210, 8, "F")
        self.set_font("DejaVuSans", "", 8)
        self.set_text_color(*GRIS)
        self.set_y(12)
        self.cell(0, 5, "Cribado fonológico pediátrico — informe orientativo", align="R")
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVuSans", "", 7.5)
        self.set_text_color(*GRIS)
        self.cell(0, 8, "Cribado, NO diagnóstico. Apoyo a la valoración de logopeda/pediatra. "
                        f"· Página {self.page_no()}", align="C")


def _titulo(pdf, texto, sub=None):
    pdf.set_font("DejaVuSans", "B", 18)
    pdf.set_text_color(*SLATE)
    pdf.cell(0, 10, texto, new_x="LMARGIN", new_y="NEXT")
    if sub:
        pdf.set_font("DejaVuSans", "", 11)
        pdf.set_text_color(*GRIS)
        pdf.cell(0, 7, sub, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_draw_color(59, 130, 246)
    pdf.set_line_width(1.0)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(5)


def _seccion(pdf, texto):
    pdf.ln(2)
    pdf.set_font("DejaVuSans", "B", 12)
    pdf.set_text_color(*SLATE)
    pdf.multi_cell(0, 6, texto, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _parrafo(pdf, texto, size=10, color=(51, 65, 85)):
    pdf.set_font("DejaVuSans", "", size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, 5.5, texto, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _badge_semaforo(pdf, nivel, recomendacion=""):
    color = SEMAFORO.get(nivel, GRIS)
    pdf.set_fill_color(*color)
    y = pdf.get_y()
    pdf.set_draw_color(*color)
    pdf.rect(20, y, 170, 11, "F")
    pdf.set_xy(24, y)
    pdf.set_font("DejaVuSans", "B", 12)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(50, 11, f"RIESGO {nivel.upper()}")
    if recomendacion:
        pdf.set_font("DejaVuSans", "", 9)
        pdf.set_xy(74, y)
        pdf.cell(112, 11, recomendacion[:78])
    pdf.set_xy(20, y + 13)


def _kv(pdf, pares):
    pdf.set_font("DejaVuSans", "", 10)
    for k, v in pares:
        pdf.set_text_color(*GRIS)
        pdf.cell(70, 6, f"  {k}")
        pdf.set_text_color(*SLATE)
        pdf.set_font("DejaVuSans", "B", 10)
        pdf.cell(0, 6, str(v), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVuSans", "", 10)
    pdf.ln(1)


def _render_prueba(pdf, prueba):
    rr = prueba["resumen"]
    ac = prueba.get("analisis", {})
    etq = f"Prueba {prueba.get('n_prueba', 1)}" + (f" — {prueba['ts'][:10]}" if prueba.get("ts") else "")
    _seccion(pdf, etq)
    _badge_semaforo(pdf, rr.get("riesgo", "bajo"), rr.get("recomendacion", ""))
    _kv(pdf, [
        ("Errores impropios para la edad", rr.get("n_errores_impropios", 0)),
        ("Palabras correctas", rr.get("palabras_correctas", 0)),
        ("Inteligibilidad media", f"{rr.get('inteligibilidad_media', 0):.0%}"),
        ("PCC medio / severidad", f"{ac.get('pcc_medio', '—')} % ({ac.get('severidad_pcc', '—')})"),
    ])
    procesos = rr.get("errores_por_tipo", {})
    if procesos:
        _parrafo(pdf, "Procesos detectados: " +
                 "; ".join(f"{n} ({c})" for n, c in procesos.items()))
    if ac.get("procesos_atipicos"):
        _parrafo(pdf, "⚠ Procesos atípicos (mayor relevancia): " +
                 ", ".join(ac["procesos_atipicos"]), color=SEMAFORO["alto"])
    # vista PROFESIONAL: severidad PCC por grupo de error y por palabra
    if ac.get("pcc_por_grupo"):
        _parrafo(pdf, "PCC por grupo de error: " +
                 "; ".join(f"{g['proceso']}: {g['pcc']}% ({g['severidad']}, "
                           f"{g['n_palabras']} pal.)" for g in ac["pcc_por_grupo"]))
    if ac.get("severidad_por_palabra"):
        peores = sorted(ac["severidad_por_palabra"], key=lambda x: x["pcc"])[:10]
        _parrafo(pdf, "Palabras con menor PCC: " +
                 "; ".join(f"{w['palabra']} {w['pcc']}% ({w['severidad']})" for w in peores),
                 size=9, color=GRIS)
    pers = prueba.get("persistencia")
    if pers:
        pr = pers.get("procesos", {})
        _parrafo(pdf, f"Persistencia vs histórico — persistentes: "
                 f"{', '.join(pr.get('persistentes', [])) or '—'} · nuevos: "
                 f"{', '.join(pr.get('nuevos', [])) or '—'} · resueltos: "
                 f"{', '.join(pr.get('resueltos', [])) or '—'}.")
    rep = prueba.get("repeticion")
    if rep:
        _parrafo(pdf, "Ronda extra de repetición — corregidos: "
                 f"{', '.join(rep.get('procesos_corregidos', [])) or '—'} · confirmados: "
                 f"{', '.join(rep.get('procesos_confirmados', [])) or '—'}.")
    for aviso in prueba.get("avisos", []) or []:
        _parrafo(pdf, f"⚠ {aviso}", size=9, color=(154, 52, 18))
    plan = prueba.get("ejercicios")
    if plan and plan.get("ejercicios"):
        _parrafo(pdf, "Ejercicios de estimulación propuestos tras esta prueba"
                 + (f" · repetir en {plan['plazo']}" if plan.get("plazo") else "") + ":",
                 size=9.5, color=SLATE)
        for a in plan["ejercicios"]:
            _parrafo(pdf, f"  • {a['titulo']} [{a.get('proceso', '')}]: {a['actividad']}",
                     size=9, color=(71, 85, 105))


def _render_evolucion(pdf, ev):
    if not ev or not ev.get("tiene_evolucion"):
        return
    _seccion(pdf, "Evolución entre pruebas")
    d = ev["delta"]
    _kv(pdf, [
        ("Cambio de riesgo", d.get("riesgo", "—")),
        ("Δ errores impropios", d.get("n_errores_impropios", "—")),
        ("Δ palabras correctas", d.get("palabras_correctas", "—")),
        ("Δ inteligibilidad", d.get("inteligibilidad_media", "—")),
        ("Δ PCC medio", d.get("pcc_medio", "—")),
        ("Días entre pruebas", ev.get("dias_entre_pruebas", "—")),
        ("Ejercicios entre pruebas", ev.get("n_ejercicios_entre_pruebas", 0)),
        ("Días desde último ejercicio a la prueba", ev.get("dias_ultimo_ejercicio_a_prueba", "—")),
    ])


def _render_ejercicios(pdf, plan):
    if not plan:
        return
    _seccion(pdf, "Ejercicios de estimulación propuestos")
    _parrafo(pdf, plan.get("mensaje", ""))
    for a in plan.get("ejercicios", plan.get("actividades", [])):
        pdf.set_font("DejaVuSans", "B", 10)
        pdf.set_text_color(*SLATE)
        pdf.multi_cell(0, 5.5, f"• {a['titulo']}  [{a.get('proceso', '')}]",
                       new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVuSans", "", 9.5)
        pdf.set_text_color(71, 85, 105)
        pdf.multi_cell(0, 5, f"   {a['actividad']}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(0.5)
    _parrafo(pdf, plan.get("nota", ""), size=8.5, color=GRIS)


def generar_pdf(datos, salida):
    """datos: {alias, edad, fecha, encuadre, screening, pruebas[], evolucion, ejercicios, factores}."""
    _asegura_fuentes()
    pdf = InformePDF()
    pdf.add_font("DejaVuSans", "", FUENTE)
    pdf.add_font("DejaVuSans", "B", FUENTE_B)
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    sub = f"{datos.get('alias', '—')} · {datos.get('edad', '—')} años"
    if datos.get("fecha"):
        sub += f" · {datos['fecha']}"
    _titulo(pdf, "Informe de cribado fonológico", sub)

    _parrafo(pdf, datos.get("encuadre", "Esta herramienta orienta un cribado del habla; NO es un "
             "diagnóstico. Un resultado de aviso recomienda una valoración, no confirma un trastorno."),
             color=GRIS)

    scr = datos.get("screening")
    if scr:
        _seccion(pdf, "Cuestionario inicial (familia)")
        _kv(pdf, [("Triaje preliminar", scr.get("riesgo_preliminar", "—").upper()),
                  ("Señales reportadas", len(scr.get("banderas", [])))])
        if scr.get("factores_equidad"):
            _parrafo(pdf, "Factores a tener en cuenta (pueden explicar parte de las dificultades): "
                     + "; ".join(scr["factores_equidad"]))

    for prueba in datos.get("pruebas", []):
        _render_prueba(pdf, prueba)

    _render_evolucion(pdf, datos.get("evolucion"))
    # los ejercicios se muestran dentro de cada prueba (uno por prueba); si llega un plan
    # global suelto (compatibilidad), se añade al final
    if datos.get("ejercicios"):
        _render_ejercicios(pdf, datos.get("ejercicios"))

    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)
    pdf.output(salida)
    return salida


# ----------------------------------------------------------------- adaptadores
def _prueba_desde_informe(informe, n_prueba=1, ts=None, edad=None):
    rr = informe.get("resumen_riesgo", {})
    ed = edad or informe.get("registro", {}).get("edad") or 5
    # ejercicios propuestos DE ESTA prueba (según su riesgo y errores) — uno por prueba
    return {"n_prueba": n_prueba, "ts": ts, "resumen": rr,
            "analisis": herramientas.analisis_clinico(informe),
            "persistencia": informe.get("persistencia"),
            "repeticion": informe.get("repeticion"),
            "avisos": informe.get("avisos_equidad") or [],
            "ejercicios": herramientas.proponer_ejercicios_para(rr, ed)}


def datos_desde_informe(ruta):
    """Construye el dict 'datos' (mismo formato que la plantilla informe_clinico.html)
    a partir de un informe JSON suelto."""
    import json
    with open(ruta, encoding="utf-8") as f:
        informe = json.load(f)
    reg = informe.get("registro", {})
    edad = reg.get("edad")
    return {
        "alias": reg.get("nombre", "—"), "edad": edad,
        "pruebas": [_prueba_desde_informe(informe, n_prueba=reg.get("n_prueba", 1), edad=edad)],
    }


def datos_desde_nino(nino_id):
    """Construye el dict 'datos' longitudinal (todas las pruebas + evolución) de un niño.
    Cada prueba lleva SUS ejercicios propuestos (según su riesgo/errores)."""
    conn = almacen.conectar(RAIZ)
    fila = conn.execute("SELECT * FROM ninos WHERE id=?", (nino_id,)).fetchone()
    tl = almacen.timeline(conn, nino_id)
    ev = almacen.evolucion(conn, nino_id)
    conn.close()

    edad = fila["edad"] if fila else None
    pruebas_ev = [e for e in tl if e["tipo"] == "prueba_audio"]
    if edad is None:
        edad = (pruebas_ev[-1]["payload"]["registro"]["edad"] if pruebas_ev else 5)
    pruebas = [_prueba_desde_informe(e["payload"], n_prueba=e["n_prueba"], ts=e["ts"], edad=edad)
               for e in pruebas_ev]
    scr = next((e["payload"] for e in reversed(tl) if e["tipo"] == "screening"), None)

    return {
        "alias": (fila["alias"] if fila else nino_id), "edad": edad,
        "screening": scr, "pruebas": pruebas, "evolucion": ev,
    }


def desde_informe(ruta, salida=None):
    datos = datos_desde_informe(ruta)
    salida = salida or os.path.join(DIR_RESULTS, os.path.basename(ruta).replace(".json", ".pdf"))
    return generar_pdf(datos, salida)


def desde_nino(nino_id, salida=None):
    datos = datos_desde_nino(nino_id)
    salida = salida or os.path.join(DIR_RESULTS, f"informe_{nino_id}.pdf")
    return generar_pdf(datos, salida)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = sys.argv[1:]
    if args and args[0] == "--nino":
        out = desde_nino(args[1])
    elif args:
        out = desde_informe(args[0])
    else:
        print("Uso: python -m app.informe_pdf <informe.json> | --nino <id>")
        sys.exit(1)
    print(f"PDF generado: {os.path.relpath(out, RAIZ)}")
