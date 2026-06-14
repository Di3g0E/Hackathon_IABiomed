"""
Grafo agéntico LOGOPEDA/SANITARIO (LangGraph + Groq).

Asistente profesional para el especialista: carga la sesión, genera el editor
interactivo de timeline, re-puntúa tras las ediciones (human-in-the-loop), produce el
análisis clínico (severidad PCC, procesos, atípicos), propone los ejercicios de
estimulación, revisa la evolución longitudinal y exporta el informe PDF para derivar.

Usa tool-calling REAL del LLM (Groq) sobre la capa de servicio (herramientas.py). Si no
hay GROQ_API_KEY, degrada a un RESUMEN PROFESIONAL determinista que encadena las mismas
herramientas (sigue siendo útil y testeable). Encuadre: cribado, no diagnóstico.
"""
from __future__ import annotations

import json
import os
import sys

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)

from langchain_core.tools import tool

from app import config, herramientas, informe_pdf, revision_html
from app.config import DIR_RESULTS

TONO_LOGOPEDA = (
    "Eres el asistente clínico de una herramienta de CRIBADO fonológico pediátrico, dirigido "
    "a logopedas y pediatras. Hablas español, claro, técnico pero conciso. SIEMPRE recuerdas "
    "que es un cribado de HABLA orientativo, NO un diagnóstico ni una evaluación de LENGUAJE. "
    "Usas las herramientas disponibles para cargar datos, analizar, re-puntuar tras la revisión "
    "del profesional, proponer plan y exportar. No inventas cifras: las obtienes de las tools. "
    "Sé útil y propón el siguiente paso (revisar el editor, exportar PDF, derivar)."
)


def _cargar_informe(sesion_id):
    for nombre in (f"informe_{sesion_id}_revisado.json", f"informe_{sesion_id}.json"):
        ruta = os.path.join(DIR_RESULTS, nombre)
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(f"No hay informe para '{sesion_id}'. Genera uno con el flujo familiar.")


# ----------------------------------------------------------------- tools (LLM)
@tool
def cargar_informe(sesion_id: str) -> dict:
    """Carga el informe de cribado de una sesión: resumen de riesgo y palabras."""
    inf = _cargar_informe(sesion_id)
    return {"registro": inf.get("registro"), "resumen_riesgo": inf.get("resumen_riesgo"),
            "n_palabras": len(inf.get("palabras", []))}


@tool
def analisis_clinico(sesion_id: str) -> dict:
    """Análisis técnico: PCC medio y severidad (Shriberg), procesos, % por palabras y atípicos."""
    return herramientas.analisis_clinico(_cargar_informe(sesion_id))


@tool
def plan_ejercicios(sesion_id: str) -> dict:
    """Propone ejercicios de estimulación según los procesos impropios y la edad."""
    inf = _cargar_informe(sesion_id)
    return herramientas.proponer_ejercicios_para(inf["resumen_riesgo"], inf["registro"]["edad"])


@tool
def generar_editor(sesion_id: str) -> dict:
    """Genera el editor HTML interactivo de timeline de fonemas para revisar/corregir."""
    ruta = revision_html.generar_html(sesion_id, api_base="")
    return {"ruta": os.path.relpath(ruta), "url_api": f"/sesion/{sesion_id}/revision.html"}


@tool
def reanalizar(sesion_id: str, ediciones: dict) -> dict:
    """Re-puntúa tras la corrección del profesional. ediciones: {palabra: 'secuencia fonemas'}."""
    edad = _cargar_informe(sesion_id).get("registro", {}).get("edad", 5)
    palabras = [{"palabra": w, "detectado": s, "confianza": 1.0} for w, s in ediciones.items()]
    informe = {"registro": {"nombre": sesion_id, "edad": edad}, "palabras": palabras}
    informe = herramientas.repuntuar_informe(informe)
    return informe["resumen_riesgo"]


@tool
def evolucion(nino_id: str) -> dict:
    """Evolución longitudinal entre pruebas (deltas y tiempos entre pruebas/ejercicios)."""
    return herramientas.evolucion_longitudinal(nino_id)


@tool
def exportar_pdf(ident: str) -> dict:
    """Exporta el informe PDF (longitudinal si el niño está en la BD; si no, desde el informe)."""
    ev = herramientas.evolucion_longitudinal(ident)
    ruta = informe_pdf.desde_nino(ident) if ev.get("pruebas") else \
        informe_pdf.desde_informe(os.path.join(DIR_RESULTS, f"informe_{ident}.json"))
    return {"pdf": os.path.relpath(ruta), "url_api": f"/informe/{ident}/pdf"}


TOOLS = [cargar_informe, analisis_clinico, plan_ejercicios, generar_editor,
         reanalizar, evolucion, exportar_pdf]
_BY_NAME = {t.name: t for t in TOOLS}


# ----------------------------------------------------------------- ejecución
def _correr_llm(sesion_id, mensaje, historial, max_iter=10):
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
    # temperatura baja: el tool-calling es más fiable y determinista que la narración.
    llm_base = config.chat(temperatura=0.1)
    llm = llm_base.bind_tools(TOOLS)
    contexto = (f"\n\nLa sesión/niño activo es '{sesion_id}'. Usa SIEMPRE '{sesion_id}' como "
                f"sesion_id y nino_id en las herramientas; no inventes otros identificadores.")
    msgs = [SystemMessage(content=TONO_LOGOPEDA + contexto)]
    # 'historial' ya incluye el mensaje del usuario actual (lo añade responder()),
    # así que NO se vuelve a añadir aparte (evita duplicarlo en el contexto del LLM).
    for m in (historial or [])[-8:]:
        msgs.append(HumanMessage(content=m["content"]) if m["role"] == "user"
                    else AIMessage(content=m["content"]))
    if not historial or historial[-1]["role"] != "user":
        msgs.append(HumanMessage(content=mensaje or "(continúa)"))
    from app.llm_util import rescatar_llamadas_texto
    for _ in range(max_iter):
        ai = llm.invoke(msgs)
        calls = getattr(ai, "tool_calls", None) or []
        if not calls:
            calls, limpio = rescatar_llamadas_texto(ai.content, set(_BY_NAME))
            if calls:
                ai = AIMessage(content=limpio or "", tool_calls=calls)
        msgs.append(ai)
        if not calls:
            return ai.content or "(sin contenido)"
        for tc in calls:
            herramienta = _BY_NAME.get(tc["name"])
            try:
                out = herramienta.invoke(tc["args"]) if herramienta else {"error": "tool desconocida"}
            except Exception as e:
                out = {"error": str(e)}
            msgs.append(ToolMessage(content=json.dumps(out, ensure_ascii=False, default=str),
                                    tool_call_id=tc["id"]))
    # se agotaron las iteraciones de tools: fuerza una respuesta final SIN herramientas
    msgs.append(HumanMessage(content="Con la información ya obtenida, redacta la respuesta final "
                             "para el profesional (resumen y siguiente paso). No llames a más herramientas."))
    return llm_base.invoke(msgs).content or "(sin respuesta)"


def _resumen_profesional(sesion_id):
    """Fallback determinista sin LLM: encadena las herramientas y redacta un resumen."""
    inf = _cargar_informe(sesion_id)
    ac = herramientas.analisis_clinico(inf)
    edad = inf["registro"]["edad"]
    plan = herramientas.proponer_ejercicios_para(inf["resumen_riesgo"], edad)
    ev = herramientas.evolucion_longitudinal(sesion_id)
    editor = revision_html.generar_html(sesion_id, api_base="")
    procesos = "; ".join(f"{p['proceso']} ({p['palabras_afectadas']} pal.)" for p in ac["procesos"]) or "—"
    lineas = [
        f"Sesión {sesion_id} · edad {edad} · cribado (NO diagnóstico).",
        f"Riesgo: {ac['riesgo']} | errores impropios: {ac['n_errores_impropios']} | "
        f"PCC medio: {ac['pcc_medio']}% ({ac['severidad_pcc']}) | "
        f"inteligibilidad: {ac['inteligibilidad_media']}.",
        f"Procesos: {procesos}.",
    ]
    if ac["procesos_atipicos"]:
        lineas.append(f"⚠ Procesos atípicos (mayor relevancia): {', '.join(ac['procesos_atipicos'])}.")
    if ev.get("tiene_evolucion"):
        d = ev["delta"]
        lineas.append(f"Evolución: {d['riesgo']} | Δimpropios {d['n_errores_impropios']} | "
                      f"{ev['dias_entre_pruebas']} días entre pruebas.")
    lineas.append(f"Ejercicios propuestos: {len(plan['ejercicios'])} (plazo {plan['plazo']}).")
    lineas.append(f"Editor de revisión: {os.path.relpath(editor)} (URL API: /sesion/{sesion_id}/revision.html).")
    lineas.append("Siguiente paso: revisar/corregir en el editor, re-puntuar y exportar PDF para derivar.")
    return "\n".join(lineas)


def responder(sesion_id, mensaje, estado=None):
    """Procesa un turno del asistente logopeda. Devuelve {respuesta, estado, llm}."""
    estado = dict(estado or {"historial": []})
    estado.setdefault("historial", [])
    if mensaje:
        estado["historial"].append({"role": "user", "content": mensaje})
    if config.hay_llm():
        try:
            respuesta = _correr_llm(sesion_id, mensaje, estado["historial"])
        except Exception as e:
            respuesta = f"(error del modelo: {e})\n\n" + _resumen_profesional(sesion_id)
    else:
        respuesta = _resumen_profesional(sesion_id)
    estado["historial"].append({"role": "assistant", "content": respuesta})
    return {"respuesta": respuesta, "estado": estado, "llm": config.hay_llm()}
