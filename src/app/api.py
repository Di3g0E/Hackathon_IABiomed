"""
Backend FastAPI de la app TDL: expone el motor y los dos grafos agénticos.

La UI (Claude Design) consumirá estos endpoints. El audio infantil se procesa aquí y
NUNCA se envía al LLM (solo fonemas/métricas). Arrancar:

  uv run uvicorn app.api:app --app-dir src --reload
  (docs interactivos en http://127.0.0.1:8000/docs)

Endpoints clave:
  GET  /                                   salud
  POST /familia/audio/{palabra}            sube audio de una palabra -> fonemas + errores
  POST /sesion/finalizar                   cierra prueba: riesgo + guarda + longitudinal
  POST /logopeda/reanalizar/{sesion_id}    aplica ediciones del editor y re-puntúa
  GET  /sesion/{id}/revision.html          editor interactivo de timeline
  GET  /sesion/{id}/informe                informe JSON
  GET  /nino/{id}/evolucion                evolución longitudinal
  GET  /informe/{id}/pdf                   PDF descargable
  POST /familia/chat   POST /logopeda/chat  chat con los grafos (Fase C)
"""
from __future__ import annotations

import io
import json
import os
import sys

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from contextlib import asynccontextmanager

import librosa
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import herramientas, informe_pdf, revision_html
from app.config import DIR_RESULTS, DIR_STATIC, hay_llm, safe_id, safe_palabra

SR = 16_000


class StaticSinCache(StaticFiles):
    """Sirve los estáticos con revalidación obligatoria: el navegador comprueba en cada
    recarga si el fichero cambió (304 si no, 200 con la versión nueva si sí). Evita ver
    JS/CSS antiguos en caché tras un cambio (un recargado normal basta)."""
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
        return resp


@asynccontextmanager
async def _lifespan(app):
    # Warm-up: carga el reconocedor al ARRANCAR para que la primera palabra de la
    # prueba no haga esperar al niño. Desactivable con WARMUP_MODELO=0 (dev rápido).
    if os.getenv("WARMUP_MODELO", "1") not in ("0", "false", "no"):
        print("[startup] Cargando el reconocedor de fonemas (W2V)…", flush=True)
        try:
            herramientas.get_w2v()
            print("[startup] Reconocedor listo.", flush=True)
        except Exception as e:
            print(f"[startup] AVISO: no se pudo precargar el reconocedor ({e}); "
                  "se cargará en la primera palabra.", flush=True)
        print("[startup] Cargando el estimador de edad por voz…", flush=True)
        try:
            herramientas._get_edad_model()
            print("[startup] Estimador de edad listo; la app está lista.", flush=True)
        except Exception as e:
            print(f"[startup] AVISO: no se pudo precargar el estimador de edad ({e}); "
                  "se cargará al cerrar la primera prueba.", flush=True)
    yield


app = FastAPI(title="App TDL — cribado fonológico", version="0.1.0", lifespan=_lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ----------------------------------------------------------------- modelos
class Finalizar(BaseModel):
    nino_id: str
    edad: int
    palabras: list | None = None   # si falta, se leen del estado acumulado en el servidor
    alias: str | None = None
    factores: dict | None = None
    screening: dict | None = None


class Ediciones(BaseModel):
    ediciones: dict
    edad: int = 5


class ScreeningReq(BaseModel):
    respuestas: dict
    edad: int = 5
    nino_id: str | None = None     # si llega, el resultado se guarda en su histórico


class ChatReq(BaseModel):
    id: str                        # familia: nino_id · logopeda: sesion_id de la prueba
    mensaje: str = ""
    datos: dict | None = None      # datos de paso (p.ej. {"registro": {...}} del formulario)


# ----------------------------------------------------------------- SPA + salud
@app.get("/", response_class=FileResponse)
def index():
    """La aplicación web (SPA) de la familia/niño."""
    return FileResponse(os.path.join(DIR_STATIC, "index.html"))


@app.get("/salud")
def salud():
    return {"ok": True, "servicio": "App TDL — cribado fonológico (NO diagnóstico)",
            "llm": hay_llm(), "palabras": 32}


# ----------------------------------------------------------------- perfiles
class PerfilReq(BaseModel):
    alias: str | None = None
    edad: int | None = None
    sexo: str | None = None
    factores: dict | None = None


@app.get("/ninos")
def ninos_lista():
    """Perfiles registrados (selector de perfiles de la UI)."""
    return {"ninos": herramientas.listar_ninos()}


@app.get("/nino/{nino_id}")
def nino_detalle(nino_id: str):
    n = herramientas.obtener_nino(safe_id(nino_id))
    if n is None:
        raise HTTPException(404, "No existe ese perfil.")
    return n


@app.put("/nino/{nino_id}")
def nino_editar(nino_id: str, req: PerfilReq):
    """Edita el perfil (upsert) y sincroniza el registro en el estado del chat,
    para que Lali use siempre los datos actualizados. Si cambia la edad, recalcula los
    informes guardados con la nueva edad."""
    nino_id = safe_id(nino_id)
    previo = herramientas.obtener_nino(nino_id)
    herramientas.registrar_nino(nino_id, alias=req.alias, edad=req.edad,
                                sexo=req.sexo, factores=req.factores)
    estado = herramientas.cargar_estado(nino_id) or {"historial": []}
    reg = estado.get("registro") or {}
    if req.alias is not None:
        reg["nombre"] = req.alias
    if req.edad is not None:
        reg["edad"] = req.edad
    if req.sexo is not None:
        reg["sexo"] = req.sexo
    for k, v in (req.factores or {}).items():
        reg[k] = v
    estado["registro"] = reg
    herramientas.guardar_estado(nino_id, estado)
    # la edad cambió → recalcular el riesgo de las pruebas ya hechas con la nueva edad
    if req.edad is not None and (not previo or previo.get("edad") != req.edad):
        herramientas.reevaluar_pruebas_edad(nino_id, req.edad)
    return herramientas.obtener_nino(nino_id)


@app.delete("/nino/{nino_id}")
def nino_eliminar(nino_id: str):
    """Borra por completo un perfil (BD + audios + informes). Acción irreversible."""
    return herramientas.eliminar_nino(safe_id(nino_id))


@app.get("/avatares")
def avatares_lista():
    """Imágenes de avatar disponibles (cuadradas; la UI las muestra circulares). Lista lo
    que haya en static/avatares/, así basta con copiar archivos ahí para añadir opciones."""
    d = os.path.join(DIR_STATIC, "avatares")
    exts = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(exts)) if os.path.isdir(d) else []
    return {"avatares": [f"/static/avatares/{f}" for f in files]}


# ----------------------------------------------------------------- audio
def _decodificar_audio(raw: bytes):
    """Bytes de audio (wav/ogg/webm...) -> onda float32 16kHz mono."""
    try:
        onda, _ = librosa.load(io.BytesIO(raw), sr=SR, mono=True)
        return onda
    except Exception as e:
        raise HTTPException(415, f"No se pudo decodificar el audio ({e}). Envía WAV/OGG/FLAC.")


# Clip de referencia elegido a mano para palabras cuyo clip por defecto no convence.
# Para cambiar otra palabra, añade aquí "palabra": "fichero.wav" (ver data/processed/<palabra>/).
AUDIO_OVERRIDE = {
    "espada": "espada_bienhablado_h_col.wav",
    "fruta": "fruta_joseangel_h_esp.wav",
    "niño": "niño_mith_h_esp.wav",
}


@app.get("/palabra/{palabra}/audio")
def palabra_audio(palabra: str):
    """Clip humano de referencia de la palabra (Nivel 1: la app dice la palabra en voz
    alta). Determinista: clip fijo elegido a mano (AUDIO_OVERRIDE) o, si no, el primer
    locutor de España (coherente con la referencia canónica θ/ʎ)."""
    palabra = safe_palabra(palabra)
    d = os.path.join(RAIZ, "data", "processed", palabra)
    if not os.path.isdir(d):
        raise HTTPException(404, f"No hay audios de referencia para '{palabra}'.")
    elegido = AUDIO_OVERRIDE.get(palabra)
    if elegido and os.path.exists(os.path.join(d, elegido)):
        return FileResponse(os.path.join(d, elegido), media_type="audio/wav")
    wavs = sorted(f for f in os.listdir(d) if f.endswith(".wav"))
    if not wavs:
        raise HTTPException(404, f"No hay audios de referencia para '{palabra}'.")
    pref = [w for w in wavs if "_esp" in w] or wavs
    return FileResponse(os.path.join(d, pref[0]), media_type="audio/wav")


@app.get("/prueba/{nino_id}/palabras")
def prueba_palabras(nino_id: str):
    """Palabras de la prueba en curso (1ª vez: las 32; re-test: núcleo + falladas).
    Solo lectura; para arrancar de verdad usa POST /prueba/{id}/iniciar."""
    nino_id = safe_id(nino_id)
    return {"palabras": herramientas.lista_palabras_prueba(nino_id),
            "n_prueba": herramientas.prueba_actual(nino_id)}


@app.post("/prueba/{nino_id}/iniciar")
def prueba_iniciar(nino_id: str):
    """Prepara la prueba desde el menú (sin pasar por el chat): fija el nº de prueba
    y vacía las palabras acumuladas."""
    return herramientas.preparar_prueba(safe_id(nino_id))


@app.post("/prueba/{nino_id}/abandonar")
def prueba_abandonar(nino_id: str, ronda: str = "principal"):
    """Descarta una prueba dejada a medias: borra los audios de la sesión y no se
    analiza nada. Las copias anónimas de entrenamiento (si hubo consentimiento de
    datos) se conservan."""
    ronda = "repeticion" if ronda == "repeticion" else "principal"
    return herramientas.abandonar_prueba(safe_id(nino_id), ronda=ronda)


@app.post("/prueba/{nino_id}/estimar-edad")
def prueba_estimar_edad(nino_id: str):
    """Estima la edad por la voz de la prueba en curso (sin finalizar nada). La UI la
    muestra como valor por defecto para que la familia la confirme antes del informe."""
    edad = herramientas.estimar_edad_sesion(safe_id(nino_id))
    return {"edad": edad, "estimada": edad is not None}


@app.get("/nino/{nino_id}/propuesta")
def nino_propuesta(nino_id: str):
    """Ejercicios propuestos tras la última prueba (por riesgo, ligados a los errores) +
    recomendación de repetir la prueba tras el plazo del plan de seguimiento."""
    return herramientas.propuesta_tras_prueba(safe_id(nino_id))


@app.post("/familia/audio/{palabra}")
async def familia_audio(palabra: str, archivo: UploadFile = File(...),
                        nino_id: str = Form(...), reintentada: bool = Form(False),
                        ronda: str = Form("principal")):
    """Procesa el audio de UNA palabra (no envía audio al LLM), guarda el wav VERSIONADO
    por prueba (sesiones/<nino>/p<N>/; la ronda extra en p<N>/repeticion/) y lo acumula
    en el estado de la prueba en curso."""
    nino_id, palabra = safe_id(nino_id), safe_palabra(palabra)
    ronda = "repeticion" if ronda == "repeticion" else "principal"
    onda = _decodificar_audio(await archivo.read())
    return herramientas.registrar_audio(nino_id, palabra, onda, reintentada=reintentada,
                                        ronda=ronda)


# ----------------------------------------------------------------- screening
@app.post("/familia/screening")
def familia_screening(req: ScreeningReq):
    resultado = herramientas.evaluar_screening_respuestas(req.respuestas, req.edad)
    if req.nino_id:
        herramientas.guardar_evento(safe_id(req.nino_id), "screening", resultado)
    return resultado


@app.get("/familia/screening/items")
def screening_items():
    return herramientas.items_screening()


# ----------------------------------------------------------------- sesión
@app.post("/sesion/finalizar")
def sesion_finalizar(req: Finalizar):
    nino_id = safe_id(req.nino_id)
    # si la UI no manda las palabras, se leen del estado acumulado en el servidor
    palabras = req.palabras or (herramientas.cargar_estado(nino_id) or {}).get("palabras", [])
    if not palabras:
        raise HTTPException(400, "No hay palabras para puntuar (sube audios o pásalas en 'palabras').")
    return herramientas.finalizar_sesion(
        nino_id, req.edad, palabras, alias=req.alias,
        factores=req.factores, screening=req.screening)


@app.get("/sesion/{sesion_id}/informe")
def sesion_informe(sesion_id: str):
    sesion_id = safe_id(sesion_id)
    ruta = os.path.join(DIR_RESULTS, f"informe_{sesion_id}.json")
    if not os.path.exists(ruta):
        raise HTTPException(404, f"No hay informe para {sesion_id}")
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------------------------- ejercicios / config
class PlanReq(BaseModel):
    filas: list   # [{riesgo, edad, dias, n_ejercicios}, ...]


class EjercicioHecho(BaseModel):
    titulo: str


@app.get("/ejercicios")
def ejercicios_biblioteca(edad: int | None = None, riesgo: str | None = None):
    """Biblioteca COMPLETA de ejercicios de estimulación, agrupada por nivel (1 general,
    2 conciencia fonológica, 3 personalizados). Filtros opcionales por edad y riesgo."""
    return herramientas.biblioteca_ejercicios(edad=edad, riesgo=riesgo)


@app.post("/nino/{nino_id}/ejercicio")
def nino_ejercicio_hecho(nino_id: str, req: EjercicioHecho):
    """Registra que la familia ha realizado un ejercicio (seguimiento de adherencia)."""
    ev_id = herramientas.guardar_evento(safe_id(nino_id), "ejercicio_realizado",
                                        {"titulo": req.titulo})
    return {"ok": True, "evento_id": ev_id}


@app.delete("/nino/{nino_id}/ejercicio")
def nino_ejercicio_desmarcar(nino_id: str, req: EjercicioHecho):
    """Desmarca un ejercicio hecho (borra el último evento con ese título)."""
    return {"ok": herramientas.desmarcar_ejercicio(safe_id(nino_id), req.titulo)}


@app.get("/logopeda/config/plan")
def get_plan():
    """Plan de seguimiento global (riesgo × edad → días hasta repetir + nº de ejercicios)."""
    return {"filas": herramientas.plan_seguimiento_filas()}


@app.put("/logopeda/config/plan")
def put_plan(req: PlanReq):
    """El especialista configura el plan global (merge por celda; aplica a todos los niños)."""
    return {"filas": herramientas.guardar_plan_seguimiento(req.filas)}


# ----------------------------------------------------------------- logopeda
@app.get("/sesion/{sesion_id}/revision.html", response_class=HTMLResponse)
def sesion_revision(sesion_id: str):
    """Editor interactivo de timeline (mismo origen -> re-puntúa contra esta API)."""
    sesion_id = safe_id(sesion_id)
    try:
        salida = revision_html.generar_html(sesion_id, api_base="")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    with open(salida, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/logopeda/reanalizar/{sesion_id}")
def logopeda_reanalizar(sesion_id: str, req: Ediciones):
    """Aplica las ediciones del editor (palabra -> secuencia) y re-puntúa."""
    sesion_id = safe_id(sesion_id)
    palabras = [{"palabra": w, "detectado": seq, "confianza": 1.0}
                for w, seq in req.ediciones.items()]
    informe = {"registro": {"nombre": sesion_id, "edad": req.edad}, "palabras": palabras}
    informe = herramientas.repuntuar_informe(informe)
    # guarda la versión revisada y registra el evento
    ruta = os.path.join(DIR_RESULTS, f"informe_{sesion_id}_revisado.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)
    herramientas.guardar_evento(sesion_id, "revision_logopeda",
                                {"resumen_riesgo": informe["resumen_riesgo"]})
    return informe


# ----------------------------------------------------------------- longitudinal / export
@app.get("/nino/{nino_id}/evolucion")
def nino_evolucion(nino_id: str):
    return herramientas.evolucion_longitudinal(safe_id(nino_id))


@app.get("/nino/{nino_id}/historico")
def nino_historico(nino_id: str):
    """Histórico para la FAMILIA: pruebas con riesgo general, estrellas por participación
    y ejercicios. Sin detalle clínico por palabra (eso vive en el informe del logopeda)."""
    return herramientas.historico_familiar(safe_id(nino_id))


@app.get("/informe/{nino_id}/envio")
def informe_envio(nino_id: str, email: str | None = None):
    """Genera el PDF y un enlace mailto al especialista (descargar y/o enviar)."""
    return herramientas.exportar_y_enlace(safe_id(nino_id), email)


@app.get("/sesion/{sesion_id}/palabras.html", response_class=HTMLResponse)
def informe_palabras_ver(sesion_id: str):
    """Informe PALABRA A PALABRA de una prueba: audio + letras detectadas en el tiempo
    (reprocesa los wav de la sesión). Se abre/descarga; imprimible a PDF."""
    from app import informe_palabras_html as _ip
    sesion_id = safe_id(sesion_id)
    try:
        return HTMLResponse(_ip.desde_sesion(sesion_id))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/informe/{ident}/html", response_class=HTMLResponse)
def informe_html_ver(ident: str):
    """Informe clínico en HTML con la plantilla de marca (cara profesional). Se abre en el
    navegador; el especialista puede imprimirlo a PDF (Ctrl+P). Usa la BD (longitudinal)
    si el niño existe; si no, el informe JSON suelto."""
    from app import informe_html as _ih
    ident = safe_id(ident)
    ev = herramientas.evolucion_longitudinal(ident)
    if ev.get("pruebas"):
        return HTMLResponse(_ih.desde_nino(ident))
    ruta_json = os.path.join(DIR_RESULTS, f"informe_{ident}.json")
    if not os.path.exists(ruta_json):
        raise HTTPException(404, f"No hay datos para {ident}")
    return HTMLResponse(_ih.desde_informe(ruta_json))


@app.get("/informe/{ident}/pdf")
def informe_pdf_descarga(ident: str):
    """PDF: usa la BD (longitudinal) si el niño existe; si no, el informe JSON."""
    ident = safe_id(ident)
    ev = herramientas.evolucion_longitudinal(ident)
    if ev.get("pruebas"):
        salida = informe_pdf.desde_nino(ident)
    else:
        ruta_json = os.path.join(DIR_RESULTS, f"informe_{ident}.json")
        if not os.path.exists(ruta_json):
            raise HTTPException(404, f"No hay datos para {ident}")
        salida = informe_pdf.desde_informe(ruta_json)
    return FileResponse(salida, media_type="application/pdf",
                        filename=os.path.basename(salida))


# ----------------------------------------------------------------- chat (estado en servidor)
@app.get("/familia/chat/{nino_id}/historial")
def familia_chat_historial(nino_id: str):
    """Historial persistido del chat de Lali (recuperable tras recargar la página)."""
    estado = herramientas.cargar_estado(safe_id(nino_id)) or {}
    return {"historial": estado.get("historial", []), "llm": hay_llm()}


@app.post("/familia/chat")
def familia_chat(req: ChatReq):
    """Chat familiar conducido por el LLM. Devuelve {mensaje, accion, datos, fin, llm};
    la UI ejecuta 'accion' (pedir_registro, iniciar_grabacion, mostrar_resultado, mostrar_ejercicios, ofrecer_envio...)."""
    from app.grafo_familia import responder
    nino_id = safe_id(req.id)
    if req.datos:                              # p.ej. el formulario de registro
        estado = herramientas.cargar_estado(nino_id) or {"historial": []}
        estado.update(req.datos)
        herramientas.guardar_estado(nino_id, estado)
    turno = responder(nino_id, req.mensaje, None)
    return {"mensaje": turno["mensaje"], "accion": turno["accion"], "datos": turno["datos"],
            "fin": turno["fin"], "llm": turno["llm"]}


@app.post("/logopeda/chat")
def logopeda_chat(req: ChatReq):
    """Chat del especialista sobre una prueba concreta (id = sesion_id, p.ej. 'ana_5_p1')."""
    from app.grafo_logopeda import responder
    sesion_id = safe_id(req.id)
    estado = herramientas.cargar_estado(f"logopeda_{sesion_id}") or {"historial": []}
    turno = responder(sesion_id, req.mensaje, estado)
    herramientas.guardar_estado(f"logopeda_{sesion_id}", turno["estado"])
    return {"respuesta": turno["respuesta"], "llm": turno.get("llm")}


# ----------------------------------------------------------------- estáticos (al final)
app.mount("/static", StaticSinCache(directory=DIR_STATIC), name="static")
