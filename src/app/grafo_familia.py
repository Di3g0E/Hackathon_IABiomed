"""
Grafo agéntico FAMILIA/NIÑO — flujo CONDUCIDO POR EL LLM ("Lumi").

Un ORQUESTADOR (LLM con tool-calling) conduce el proceso y, en cada turno, decide qué paso
toca, lo anuncia y emite una SEÑAL DE ACCIÓN para la UI (las tools SON las acciones).
Subagentes: OPERATIVO (palabras de la prueba + ejercicios) y ANÁLISIS (evalúa, clasifica,
guarda histórico y redacta la nota clínica para el especialista).

Reglas clave:
  - El audio NUNCA llega al LLM (lo procesa /familia/audio y se acumula en el estado).
  - La familia ve SIEMPRE su resultado en versión SIMPLE: solo el nivel y la recomendación
    (sin cifras, sin detalle por palabra). El detalle vive en el informe profesional.
  - Los ejercicios son de ESTIMULACIÓN del habla, nunca "terapia" ni diagnóstico.
  - La ronda extra de repetición se ofrece de forma NEUTRA (jamás "porque falló").

Sin GROQ_API_KEY, degrada a una orquestación determinista por estado (mismas acciones).

Respuesta de `responder`: {mensaje, accion, datos, fin, estado, llm}.
Acciones: pedir_registro · iniciar_grabacion · mostrar_resultado · mostrar_ejercicios ·
          ofrecer_envio · ninguna.  (la oferta de ronda extra viaja dentro de
          mostrar_resultado.datos.ronda_extra y la grabación extra reutiliza iniciar_grabacion)
"""
from __future__ import annotations

import json
import os
import sys

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)

from langchain_core.tools import tool

from app import config, herramientas

# nombre obligatorio; el resto opcional. La EDAD ya no se pide en el registro: si falta,
# la estima el modelo especializado de voz en el primer juego y queda en el perfil.
CAMPOS_REGISTRO = [
    {"campo": "nombre", "obligatorio": True, "nota": "nombre o apodo, sin apellidos"},
    {"campo": "edad", "obligatorio": False,
     "nota": "años (3-6); si no se indica, se estima automáticamente con la voz"},
    {"campo": "sexo", "obligatorio": False},
    {"campo": "lengua_materna", "obligatorio": False},
    {"campo": "bilinguismo", "obligatorio": False, "nota": "¿se habla más de un idioma en casa?"},
    {"campo": "problemas_auditivos", "obligatorio": False, "nota": "otitis de repetición / hipoacusia"},
    {"campo": "email_especialista", "obligatorio": False},
    {"campo": "consentimiento", "obligatorio": True,
     "nota": "acepto el uso de la app (cribado, no diagnóstico)"},
    {"campo": "consentimiento_datos", "obligatorio": False, "tipo": "checkbox",
     "nota": "Permito guardar la voz y la edad de forma anónima para mejorar el sistema "
             "(opcional; si no se marca, el audio solo se usa para esta prueba y el especialista)"},
]

TONO_ORQ = (
    "Eres 'Lumi', un zorrito que guía a las familias por una herramienta que ORIENTA sobre el "
    "habla infantil (niños 3-6). Hablas español de España, muy cálido, cercano y sencillo; frases "
    "cortas. CONDUCES el proceso: en cada turno decides el siguiente paso, lo ANUNCIAS con "
    "naturalidad y llamas a la herramienta correspondiente.\n"
    "Flujo: 1) sin registro -> pedir_registro; 2) con registro -> confirmar_registro y anunciar el "
    "juego de palabras -> iniciar_prueba; 3) cuando la familia diga que terminó de grabar -> "
    "analizar_prueba (muestra el resultado simple); 3b) si el resultado ofrece una 'ronda_extra' y "
    "la familia ACEPTA jugar otra ronda -> iniciar_repeticion; cuando terminen esa ronda -> "
    "cerrar_repeticion; 4) después -> proponer_ejercicios; 5) si la familia hace un ejercicio y lo "
    "cuenta -> marcar_ejercicio; 6) al final -> preparar_envio.\n"
    "REGLAS ESTRICTAS: a la familia SOLO se le comunica el nivel del resultado y la recomendación, "
    "en positivo y sin alarmar. NUNCA cifras, porcentajes, fonemas, 'trastorno' ni 'diagnóstico'. "
    "Los ejercicios son JUEGOS de estimulación del habla, NUNCA los llames terapia. La ronda extra "
    "se ofrece como '¿jugamos una ronda más?' SIN decir jamás que es por fallos, y SOLO si el "
    "resultado de analizar_prueba incluye 'ronda_extra' (si no, no la menciones). No inventes datos. "
    "Usa SIEMPRE el mecanismo nativo de tool-calling (nunca escribas '<function=...>' en el texto). "
    "Responde en 1-3 frases."
)


# ---------------------------------------------------------------- subagente ANÁLISIS
def _sub_analisis_nota(analisis, edad, avisos=None):
    """Subagente de análisis: nota clínica BREVE para el especialista (no para la familia)."""
    base = (f"PCC {analisis.get('pcc_medio')}% ({analisis.get('severidad_pcc')}), riesgo "
            f"{analisis.get('riesgo')}, {analisis.get('n_errores_impropios')} errores impropios "
            f"para la edad {edad}. Procesos: "
            + (", ".join(p["proceso"] for p in analisis.get("procesos", [])) or "ninguno") + ".")
    if avisos:
        base += " Avisos: " + " ".join(avisos)
    if not config.hay_llm():
        return "Cribado (no diagnóstico). " + base
    from langchain_core.messages import HumanMessage, SystemMessage
    sys_p = ("Eres el subagente de análisis clínico de un cribado fonológico pediátrico. Redacta "
             "una nota técnica BREVE (2-3 frases) para el logopeda/pediatra a partir de los datos. "
             "Es un cribado de habla, NO un diagnóstico. No inventes cifras.")
    try:
        return config.chat(temperatura=0.2).invoke(
            [SystemMessage(content=sys_p), HumanMessage(content=base)]).content
    except Exception:
        return "Cribado (no diagnóstico). " + base


# ---------------------------------------------------------------- tools = acciones
@tool
def pedir_registro(nino_id: str) -> dict:
    """Pide a la familia los datos de registro (la UI mostrará el formulario)."""
    return {"ok": True, "_accion": "pedir_registro", "_datos": {"campos": CAMPOS_REGISTRO}}


@tool
def confirmar_registro(nino_id: str) -> dict:
    """Confirma y guarda los datos de registro que la familia ya ha proporcionado."""
    estado = herramientas.cargar_estado(nino_id) or {}
    reg = estado.get("registro") or {}
    if not reg.get("nombre") and not reg.get("alias"):
        return {"error": "Falta el nombre (obligatorio)."}
    # la edad es opcional: si falta, la estimará el modelo de voz en el primer juego
    alias = reg.get("nombre") or reg.get("alias")
    # solo claves con valor: registrar_nino fusiona, así no anulamos datos ya guardados
    # (p. ej. avatar/lengua/email) con None
    factores = {k: reg[k] for k in ("sexo", "lengua_materna", "bilinguismo",
                                    "problemas_auditivos", "email_especialista", "avatar")
                if reg.get(k) is not None}
    herramientas.registrar_nino(nino_id, alias=alias, edad=reg.get("edad"),
                                sexo=reg.get("sexo"), factores=factores or None)
    return {"ok": True, "_accion": None, "alias": alias, "edad": reg.get("edad")}


@tool
def iniciar_prueba(nino_id: str) -> dict:
    """Subagente OPERATIVO: prepara la prueba (1ª vez las 32 palabras; en el re-test núcleo +
    palabras a reforzar) y señala a la UI iniciar la grabación."""
    estado = herramientas.cargar_estado(nino_id) or {"historial": []}
    n = herramientas.prueba_actual(nino_id)
    palabras = herramientas.lista_palabras_prueba(nino_id)
    estado["n_prueba"], estado["sesion_id"], estado["palabras"] = n, f"{nino_id}_p{n}", []
    estado.pop("repeticion", None)
    herramientas.guardar_estado(nino_id, estado)
    return {"ok": True, "_accion": "iniciar_grabacion",
            "_datos": {"palabras": palabras, "n_prueba": n, "ronda": "principal",
                       "sesion_id": f"{nino_id}_p{n}"}}


@tool
def analizar_prueba(nino_id: str) -> dict:
    """Subagente ANÁLISIS: evalúa la prueba grabada, guarda el histórico y la nota clínica, y
    muestra a la familia SOLO el resultado simple (nivel + recomendación). Si procede, incluye
    la oferta NEUTRA de una ronda extra de juego."""
    estado = herramientas.cargar_estado(nino_id) or {}
    palabras = estado.get("palabras", [])
    if not palabras:
        return {"error": "Aún no hay palabras grabadas en esta prueba."}
    reg = estado.get("registro") or {}
    # sin edad en el registro: la estima el modelo de voz con los audios de la prueba
    # (queda guardada en el perfil como 'edad_estimada' para que la familia la revise)
    edad = herramientas.edad_o_estimada(nino_id)
    # completa sexo/origen faltantes desde la voz de la prueba (determinista; audio nunca
    # va al LLM); quedan como '*_estimado' para que la familia los revise en el perfil
    herramientas.enriquecer_perfil_voz(nino_id)
    reg = (herramientas.cargar_estado(nino_id) or {}).get("registro") or reg
    res = herramientas.finalizar_sesion(nino_id, edad, palabras,
                                        alias=reg.get("nombre") or reg.get("alias"),
                                        factores=reg)
    analisis = herramientas.analisis_clinico(res["informe"])
    avisos = res["informe"].get("avisos_equidad")
    nota = _sub_analisis_nota(analisis, edad, avisos)
    vista = herramientas.resumen_familiar(res["informe"])
    oferta = herramientas.oferta_repeticion(nino_id, res["informe"])

    estado = herramientas.cargar_estado(nino_id) or estado
    estado["resultado"] = {"resumen": res["resumen"], "analisis": analisis,
                           "nota_clinica": nota, "sesion_id": res["sesion_id"]}
    estado["palabras"] = []
    if oferta:
        estado["repeticion"] = {"palabras": [], "procesos": oferta["procesos"],
                                "candidatas": oferta["palabras"]}
    estado.pop("ejercicios", None); estado.pop("envio", None)
    herramientas.guardar_estado(nino_id, estado)

    datos = dict(vista)
    if oferta:
        datos["ronda_extra"] = {"palabras": oferta["palabras"],
                                "ventana_seg": oferta["ventana_seg"]}
    return {"ok": True, "_accion": "mostrar_resultado", "_datos": datos,
            "_interno": ("Resultado guardado para el especialista. Comunica SOLO el nivel y la "
                         "recomendación, sin cifras." +
                         (" Hay ronda_extra disponible: ofrécela como '¿jugamos una ronda más?' "
                          "SIN mencionar fallos." if oferta else ""))}


@tool
def iniciar_repeticion(nino_id: str) -> dict:
    """Si la familia acepta la ronda extra de juego: señala grabar esas palabras (ronda
    'repeticion'). Nunca se menciona que es por fallos."""
    estado = herramientas.cargar_estado(nino_id) or {}
    rep = estado.get("repeticion") or {}
    if not rep.get("candidatas"):
        return {"error": "No hay ronda extra pendiente."}
    return {"ok": True, "_accion": "iniciar_grabacion",
            "_datos": {"palabras": rep["candidatas"], "ronda": "repeticion",
                       "n_prueba": estado.get("n_prueba"),
                       "sesion_id": estado.get("sesion_id")}}


@tool
def cerrar_repeticion(nino_id: str) -> dict:
    """Cierra la ronda extra: re-evalúa el resultado con las palabras de la ronda (si mejora,
    el resultado se corrige; todo queda anotado para el especialista) y muestra el resultado."""
    out = herramientas.aplicar_repeticion(nino_id)
    if out.get("error"):
        return out
    estado = herramientas.cargar_estado(nino_id) or {}
    resumen = (estado.get("resultado") or {}).get("resumen", {})
    vista = herramientas.resumen_familiar({"resumen_riesgo": resumen})
    return {"ok": True, "_accion": "mostrar_resultado", "_datos": vista,
            "_interno": ("Ronda extra cerrada. " +
                         ("El resultado ha MEJORADO tras la ronda; comunícalo en positivo."
                          if out.get("corregido") else
                          "El resultado se mantiene; comunícalo con normalidad, sin mencionar "
                          "fallos.") + " Solo nivel y recomendación, sin cifras.")}


@tool
def proponer_ejercicios(nino_id: str) -> dict:
    """Subagente OPERATIVO: propone los EJERCICIOS DE ESTIMULACIÓN del habla (plan global del
    especialista según nivel y edad) y el plazo para repetir la prueba."""
    estado = herramientas.cargar_estado(nino_id) or {}
    res = estado.get("resultado")
    if not res:
        return {"error": "Primero hay que analizar la prueba."}
    edad = int((estado.get("registro") or {}).get("edad", 5))
    plan = herramientas.proponer_ejercicios_para(res["resumen"], edad)
    herramientas.guardar_evento(nino_id, "ejercicios_asignados", plan)
    estado["ejercicios"] = plan
    herramientas.guardar_estado(nino_id, estado)
    return {"ok": True, "_accion": "mostrar_ejercicios",
            "_datos": {"mensaje": plan["mensaje"], "ejercicios": plan["ejercicios"],
                       "plazo": plan["plazo"], "fecha_retest": plan["fecha_retest"],
                       "seguimiento_opcional": plan["seguimiento_opcional"],
                       "nota": plan["nota"]}}


@tool
def marcar_ejercicio(nino_id: str, titulo: str) -> dict:
    """Registra que la familia ha realizado un ejercicio (para el seguimiento)."""
    herramientas.guardar_evento(nino_id, "ejercicio_realizado", {"titulo": titulo})
    return {"ok": True, "_accion": None, "titulo": titulo}


@tool
def preparar_envio(nino_id: str) -> dict:
    """Prepara la descarga del informe profesional (PDF) y el enlace de envío al especialista."""
    estado = herramientas.cargar_estado(nino_id) or {}
    email = (estado.get("registro") or {}).get("email_especialista")
    env = herramientas.exportar_y_enlace(nino_id, email)
    estado["envio"] = env
    herramientas.guardar_estado(nino_id, estado)
    return {"ok": True, "_accion": "ofrecer_envio",
            "_datos": {"informe_url": env.get("informe_url"), "pdf_url": env["pdf_url"],
                       "mailto_url": env["mailto_url"]}}


TOOLS = [pedir_registro, confirmar_registro, iniciar_prueba, analizar_prueba,
         iniciar_repeticion, cerrar_repeticion, proponer_ejercicios, marcar_ejercicio,
         preparar_envio]
_BY_NAME = {t.name: t for t in TOOLS}


# ---------------------------------------------------------------- orquestador
def _resumen_estado(estado):
    rep = estado.get("repeticion") or {}
    return (f"registro={'sí' if (estado.get('registro') or {}).get('edad') else 'no'}; "
            f"palabras_grabadas_prueba={len(estado.get('palabras', []))}; "
            f"prueba_analizada={'sí' if estado.get('resultado') else 'no'}; "
            f"ronda_extra_pendiente={'sí' if rep.get('candidatas') else 'no'}; "
            f"palabras_ronda_extra_grabadas={len(rep.get('palabras', []))}; "
            f"ejercicios_propuestos={'sí' if estado.get('ejercicios') else 'no'}; "
            f"envio_preparado={'sí' if estado.get('envio') else 'no'}")


def _orquestar(nino_id, mensaje, historial, max_iter=8):
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
    estado = herramientas.cargar_estado(nino_id) or {}
    contexto = (f"\n\nNiño activo: '{nino_id}'. Usa SIEMPRE ese nino_id en las herramientas.\n"
                f"Estado actual -> {_resumen_estado(estado)}")
    llm = config.chat(temperatura=0.3).bind_tools(TOOLS)
    msgs = [SystemMessage(content=TONO_ORQ + contexto)]
    for m in (historial or [])[-8:]:
        msgs.append(HumanMessage(content=m["content"]) if m["role"] == "user"
                    else AIMessage(content=m["content"]))
    if not historial or historial[-1]["role"] != "user":
        msgs.append(HumanMessage(content=mensaje or "(continúa)"))
    from app.llm_util import rescatar_llamadas_texto
    accion, datos = None, {}
    for _ in range(max_iter):
        ai = llm.invoke(msgs)
        calls = getattr(ai, "tool_calls", None) or []
        if not calls:
            # llama a veces escribe la llamada como texto: rescatarla como tool_call real
            calls, limpio = rescatar_llamadas_texto(ai.content, set(_BY_NAME))
            if calls:
                ai = AIMessage(content=limpio or "", tool_calls=calls)
        msgs.append(ai)
        if not calls:
            return ai.content or "…", accion, datos
        for tc in calls:
            herr = _BY_NAME.get(tc["name"])
            try:
                out = herr.invoke(tc["args"]) if herr else {"error": "tool desconocida"}
            except Exception as e:
                out = {"error": str(e)}
            if isinstance(out, dict) and out.get("_accion"):
                accion, datos = out["_accion"], out.get("_datos", {})
            msgs.append(ToolMessage(content=json.dumps(out, ensure_ascii=False, default=str),
                                    tool_call_id=tc["id"]))
    msgs.append(HumanMessage(content="Responde a la familia en 1-2 frases según lo hecho "
                             "(solo nivel y recomendación, sin cifras). No llames más herramientas."))
    return config.chat(temperatura=0.3).invoke(msgs).content or "…", accion, datos


# ---------------------------------------------------------------- fallback determinista (sin LLM)
def _fallback(nino_id, mensaje, estado):
    low = (mensaje or "").lower()
    reg = estado.get("registro") or {}
    rep = estado.get("repeticion") or {}
    if not (reg.get("nombre") or reg.get("alias")):
        out = pedir_registro.invoke({"nino_id": nino_id})
        return ("¡Hola! Soy Lumi 🦊. Para empezar necesito unos datitos del peque.",
                out["_accion"], out["_datos"])
    if rep.get("palabras"):                       # ronda extra grabada -> cerrar
        out = cerrar_repeticion.invoke({"nino_id": nino_id})
        return ("¡Qué bien lo habéis hecho! Aquí tenéis el resultado actualizado. 😊",
                out.get("_accion"), out.get("_datos", {}))
    if rep.get("candidatas") and any(k in low for k in ("sí", "si", "vale", "ronda", "jugamos")):
        out = iniciar_repeticion.invoke({"nino_id": nino_id})
        return ("¡Genial, una ronda más! 🎤", out.get("_accion"), out.get("_datos", {}))
    if estado.get("palabras"):                    # prueba grabada -> analizar
        out = analizar_prueba.invoke({"nino_id": nino_id})
        extra = " ¿Jugamos una ronda más?" if (out.get("_datos") or {}).get("ronda_extra") else ""
        return ("¡Terminado! Este es el resultado." + extra,
                out.get("_accion"), out.get("_datos", {}))
    if estado.get("resultado") and not estado.get("ejercicios"):
        out = proponer_ejercicios.invoke({"nino_id": nino_id})
        return ("Os propongo unos juegos para casa:", out.get("_accion"), out.get("_datos", {}))
    if estado.get("ejercicios") and not estado.get("envio"):
        out = preparar_envio.invoke({"nino_id": nino_id})
        return ("Podéis descargar el informe o enviárselo al especialista.",
                out.get("_accion"), out.get("_datos", {}))
    if estado.get("envio"):
        return ("¡Gracias por jugar conmigo! Nos vemos en la próxima. 🦊", None, {})
    confirmar_registro.invoke({"nino_id": nino_id})
    out = iniciar_prueba.invoke({"nino_id": nino_id})
    return ("¡Genial! Vamos a jugar a decir unas palabras. 🎤", out["_accion"], out["_datos"])


# ---------------------------------------------------------------- entrada
def responder(nino_id, mensaje, estado=None):
    """Procesa un turno. La UI ejecuta 'accion' con 'datos'. Devuelve
    {mensaje, accion, datos, fin, estado, llm}."""
    estado = herramientas.cargar_estado(nino_id) or dict(estado or {"historial": []})
    estado.setdefault("historial", [])
    if mensaje:
        estado["historial"].append({"role": "user", "content": mensaje})
    herramientas.guardar_estado(nino_id, estado)

    if config.hay_llm():
        try:
            texto, accion, datos = _orquestar(nino_id, mensaje, estado["historial"])
        except Exception:
            texto, accion, datos = _fallback(nino_id, mensaje,
                                             herramientas.cargar_estado(nino_id) or estado)
    else:
        texto, accion, datos = _fallback(nino_id, mensaje, estado)

    estado = herramientas.cargar_estado(nino_id) or estado     # recarga tras las tools
    estado.setdefault("historial", [])
    estado["historial"].append({"role": "assistant", "content": texto})
    herramientas.guardar_estado(nino_id, estado)
    return {"mensaje": texto, "accion": accion, "datos": datos,
            "fin": accion == "ofrecer_envio", "estado": estado, "llm": config.hay_llm()}
