"""
Capa de servicio: funciones puras que envuelven el motor clínico existente.

Son la "verdad" funcional de la app (testeable sin grafo ni LLM). Los grafos de la
Fase C las exponen como @tool de LangChain; la API las llama directamente. El LLM NUNCA
recibe audio: estas funciones devuelven solo fonemas y métricas derivadas.

Reutiliza: reconocedor.W2V (reconoce_conf, reconoce_alineado), clinico (ref_clinico,
normaliza_clinico, clasificar_errores, evaluar_riesgo), normas (cargar, ERRORES),
ejercicios (proponer_ejercicios), screening (evaluar_screening), almacen (SQLite).
"""
from __future__ import annotations

import json
import os
import sys

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

import soundfile as sf

from pipeline.clinico import (clasificar_errores, evaluar_riesgo, normaliza_clinico,
                              ref_clinico)
from pipeline.normas import ERRORES, cargar as cargar_normas
from pipeline import ejercicios as _ejercicios
from pipeline import screening as _screening
from app import almacen
from app.config import DIR_SESIONES, DIR_ENTRENAMIENTO

SR = 16_000

# --- Reconocedor (carga perezosa, singleton: el modelo pesa y tarda en cargar) ---
import threading

# Arquitectura híbrida: _W2V_FULL (fp32, cloud/informe) y _W2V_EDGE (int8, móvil/vivo).
_W2V_FULL = None
_W2V_EDGE = None
_W2V_LOCK = threading.Lock()


def get_w2v_full():
    global _W2V_FULL
    if _W2V_FULL is None:
        with _W2V_LOCK:
            if _W2V_FULL is None:
                from pipeline.reconocedor import W2V
                _W2V_FULL = W2V()
    return _W2V_FULL


def get_w2v_edge():
    global _W2V_EDGE
    if _W2V_EDGE is None:
        with _W2V_LOCK:
            if _W2V_EDGE is None:
                from pipeline.cuantizacion import cargar_w2v_cuantizado
                _W2V_EDGE = cargar_w2v_cuantizado()
    return _W2V_EDGE


def get_w2v(rol="vivo"):
    """Reconocedor según backend y ROL. rol='vivo' (juego/grabación) usa EDGE int8 salvo
    en backend 'cloud'; rol='informe' (especialista) usa FULL fp32 salvo en backend 'edge'.
    En 'hibrido' (def): el niño juega con el modelo rápido y el informe usa el completo."""
    from app import config
    backend = getattr(config, "BACKEND_RECONOCEDOR", "cloud")
    if rol == "informe":
        return get_w2v_edge() if backend == "edge" else get_w2v_full()
    return get_w2v_edge() if backend in ("edge", "hibrido") else get_w2v_full()


# --- Estimación de edad por voz (modelo especializado audeering w2v2 age-gender) ---
# Se usa SOLO si el perfil no tiene edad: el registro ya no la pide; se estima con los
# audios del primer juego y queda preconfigurada en el perfil (la familia puede ajustarla).
EDAD_MODEL_ID = "audeering/wav2vec2-large-robust-24-ft-age-gender"
_EDAD = None
_EDAD_LOCK = threading.Lock()


def _get_edad_model():
    global _EDAD
    if _EDAD is None:
        with _EDAD_LOCK:
            if _EDAD is None:
                import torch
                import torch.nn as nn
                from transformers import Wav2Vec2Processor
                from transformers.models.wav2vec2.modeling_wav2vec2 import (
                    Wav2Vec2Model, Wav2Vec2PreTrainedModel)

                class _Head(nn.Module):
                    def __init__(self, config, n):
                        super().__init__()
                        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
                        self.dropout = nn.Dropout(config.final_dropout)
                        self.out_proj = nn.Linear(config.hidden_size, n)

                    def forward(self, x):
                        x = self.dropout(x)
                        x = torch.tanh(self.dense(x))
                        x = self.dropout(x)
                        return self.out_proj(x)

                class _AgeGender(Wav2Vec2PreTrainedModel):
                    _tied_weights_keys = []
                    all_tied_weights_keys = {}

                    def __init__(self, config):
                        super().__init__(config)
                        self.wav2vec2 = Wav2Vec2Model(config)
                        self.age = _Head(config, 1)
                        self.gender = _Head(config, 3)   # las pesas existen en el checkpoint
                        self.init_weights()

                    def forward(self, x):
                        h = torch.mean(self.wav2vec2(x)[0], dim=1)
                        return self.age(h)

                proc = Wav2Vec2Processor.from_pretrained(EDAD_MODEL_ID)
                model = _AgeGender.from_pretrained(EDAD_MODEL_ID).eval()
                # No hay versión int8 oficial: en backend edge/híbrido se cuantiza local
                # (móvil); en cloud se mantiene fp32.
                from app import config
                if getattr(config, "BACKEND_RECONOCEDOR", "cloud") in ("edge", "hibrido"):
                    from pipeline.cuantizacion import cuantizar_modelo
                    model = cuantizar_modelo(model)
                _EDAD = (proc, model)
    return _EDAD


def estimar_edad_sesion(nino_id, max_clips=6):
    """Edad estimada (acotada a 3-6) a partir de los audios de la prueba en curso.
    Devuelve None si no hay audios o el modelo falla (nunca rompe el flujo)."""
    import glob
    estado = cargar_estado(nino_id) or {}
    n = estado.get("n_prueba") or prueba_actual(nino_id)
    wavs = sorted(glob.glob(os.path.join(DIR_SESIONES, f"{nino_id}_p{n}", "*.wav")))[:max_clips]
    if not wavs:
        return None
    try:
        import librosa
        import torch
        proc, model = _get_edad_model()
        edades = []
        for w in wavs:
            sig, _ = librosa.load(w, sr=SR)
            iv = torch.from_numpy(proc(sig, sampling_rate=SR)["input_values"][0]).unsqueeze(0)
            with torch.no_grad():
                age = model(iv)
            edades.append(float(age.item()) * 100.0)   # la salida del modelo es edad/100
        media = sum(edades) / len(edades)
        return int(round(min(6.0, max(3.0, media))))
    except Exception:
        return None


def edad_o_estimada(nino_id):
    """Edad del registro o, si falta, la estimada por el modelo de voz. La estimación se
    persiste en el perfil con la marca 'edad_estimada' para que la familia la revise."""
    estado = cargar_estado(nino_id) or {}
    reg = estado.get("registro") or {}
    if reg.get("edad"):
        return int(reg["edad"])
    edad = estimar_edad_sesion(nino_id)
    if edad is None:
        return 5            # punto medio neutro si no se puede estimar
    reg["edad"] = edad
    estado["registro"] = reg
    guardar_estado(nino_id, estado)
    nino = obtener_nino(nino_id) or {}
    factores = nino.get("factores") or {}
    factores["edad_estimada"] = True
    registrar_nino(nino_id, edad=edad, factores=factores)
    return edad


# severidad por PCC (Shriberg & Kwiatkowski, 1982)
def severidad_pcc(pcc):
    if pcc is None:
        return None
    if pcc >= 85:
        return "leve"
    if pcc >= 65:
        return "leve-moderado"
    if pcc >= 50:
        return "moderado-grave"
    return "grave"


# procesos atípicos (señal de alarma mayor; mejoras_clinicas §3). De los 8 del doc,
# la omisión de sílabas es la más cercana a 'atípico/evolutivo tardío'.
ATIPICOS = {"omision_silabas"}


# --- Detectores de ORIGEN y SEXO (ECAPA, opcionales) ---------------------------
# Auto-sugerencia con human-in-the-loop: si decision='consultar' la app debe usar el
# dato de REGISTRO en vez de la predicción. Requieren models/ entrenados
# (uv run python src/scripts/10_detectores.py); si faltan, devuelven None sin romper.
_DETECTORES: dict = {}
_DET_LOCK = threading.Lock()


def _get_detector(tarea):
    if tarea not in _DETECTORES:
        with _DET_LOCK:
            if tarea not in _DETECTORES:
                try:
                    from pipeline.detectores import cargar_detector
                    _DETECTORES[tarea] = cargar_detector(tarea, RAIZ)
                except Exception:
                    _DETECTORES[tarea] = None        # modelo no entrenado todavía
    return _DETECTORES[tarea]


def sugerir_origen(onda):
    """Auto-sugiere origen (España/Latam/No nativo) desde una onda. None si no hay modelo."""
    det = _get_detector("origen")
    return det.predict(onda) if det else None


def sugerir_sexo(onda):
    """Auto-sugiere sexo desde una onda. OJO: poco fiable en niños 3-6; usar como
    respaldo del dato de registro (decision='consultar' -> preguntar). None si no hay modelo."""
    det = _get_detector("sexo")
    return det.predict(onda) if det else None


# convención del perfil: el detector usa hombre/mujer y España/Latam/No nativo
_SEXO_PERFIL = {"hombre": "m", "mujer": "f"}
_ORIGEN_PERFIL = {"España": "es", "Latam": "latam", "No nativo": "no_nativo"}


def _wavs_sesion(nino_id, max_clips=8):
    import glob
    estado = cargar_estado(nino_id) or {}
    n = estado.get("n_prueba") or prueba_actual(nino_id)
    return sorted(glob.glob(os.path.join(DIR_SESIONES, f"{nino_id}_p{n}", "*.wav")))[:max_clips]


def _agrega_predicciones(preds):
    """Media de probabilidades por clase sobre varios clips -> (etiqueta, confianza).
    Más robusto que el voto simple ante clips dudosos."""
    if not preds:
        return None
    acc = {}
    for p in preds:
        for c, v in p["probas"].items():
            acc[c] = acc.get(c, 0.0) + v
    etq = max(acc, key=acc.get)
    return etq, round(acc[etq] / len(preds), 3)


def estimar_sexo_sesion(nino_id, max_clips=8):
    """Sexo estimado por la voz de la prueba en curso (media de probabilidades sobre los
    clips). Devuelve {'sexo'('m'/'f'),'etiqueta','confianza','decision'} o None."""
    det = _get_detector("sexo")
    wavs = _wavs_sesion(nino_id, max_clips)
    if det is None or not wavs:
        return None
    try:
        ag = _agrega_predicciones(det.predict(wavs))
    except Exception:
        return None
    if ag is None:
        return None
    etq, conf = ag
    return {"sexo": _SEXO_PERFIL.get(etq), "etiqueta": etq, "confianza": conf,
            "decision": "auto" if conf >= det.umbral else "consultar"}


def estimar_origen_sesion(nino_id, max_clips=8):
    """Origen estimado por la voz (media de probabilidades). Devuelve
    {'origen'('es'/'latam'/'no_nativo'),'etiqueta','confianza','decision'} o None."""
    det = _get_detector("origen")
    wavs = _wavs_sesion(nino_id, max_clips)
    if det is None or not wavs:
        return None
    try:
        ag = _agrega_predicciones(det.predict(wavs))
    except Exception:
        return None
    if ag is None:
        return None
    etq, conf = ag
    return {"origen": _ORIGEN_PERFIL.get(etq), "etiqueta": etq, "confianza": conf,
            "decision": "auto" if conf >= det.umbral else "consultar"}


def enriquecer_perfil_voz(nino_id):
    """Tras grabar, completa el SEXO y el ORIGEN que falten en el perfil a partir de la voz
    de la prueba (determinista; el audio NUNCA va al LLM). Se marcan como estimados
    ('sexo_estimado'/'origen_estimado') para que la familia los revise en el perfil; NUNCA
    pisa un dato que la familia ya haya indicado. Devuelve las sugerencias aplicadas.

    Sexo: se rellena siempre que falte (mejor predicción). Origen: solo si hay confianza
    suficiente (F1 bajo en palabra suelta: no se afirma un origen dudoso, se deja al perfil)."""
    estado = cargar_estado(nino_id) or {}
    reg = estado.get("registro") or {}
    nino = obtener_nino(nino_id) or {}
    factores = dict(nino.get("factores") or {})
    aplicado = {}

    if not (reg.get("sexo") or nino.get("sexo")):
        s = estimar_sexo_sesion(nino_id)
        if s and s.get("sexo"):
            reg["sexo"] = s["sexo"]
            factores["sexo_estimado"] = True
            aplicado["sexo"] = s

    if not (reg.get("origen") or factores.get("origen")):
        o = estimar_origen_sesion(nino_id)
        if o and o.get("origen") and o.get("decision") == "auto":
            reg["origen"] = factores["origen"] = o["origen"]
            factores["origen_estimado"] = True
            aplicado["origen"] = o

    if aplicado:
        estado["registro"] = reg
        guardar_estado(nino_id, estado)
        registrar_nino(nino_id, sexo=reg.get("sexo"), factores=factores)
    return aplicado


# ---------------------------------------------------------------- audio -> palabra
def transcribir(onda):
    """onda (np.float32 16kHz mono) -> {fonemas:[...], confianza}."""
    fon, conf = get_w2v().reconoce_conf(onda)
    return {"fonemas": normaliza_clinico(fon), "confianza": round(float(conf), 3)}


DUR_TRILL_MIN = 0.05      # s: por debajo, una /r/ "correcta" parece tap (vibrante simple)


def _anota_duda_rr(rec, onda, w2v):
    """Si la palabra esperada tiene vibrante múltiple /r/ y se dio por correcta, mide la
    duración del segmento rótico; si es corta (típica de tap), añade una discrepancia
    'otro' informativa (duda_rr). NO cambia el riesgo (política FP>FN, sin inflar conteo)."""
    if "r" not in rec.get("esperado", "").split():
        return
    if any(e["tipo"] == "errores_rr" for e in rec.get("eventos", [])):
        return        # ya detectado como proceso, no hace falta la heurística
    try:
        segs, _dur = w2v.reconoce_alineado(onda)
        from pipeline.clinico import normaliza_clinico
        roticas = [s for s in segs if normaliza_clinico([s["tok"]])[:1] == ["r"]]
        if roticas and max(s["t_fin"] - s["t_ini"] for s in roticas) < DUR_TRILL_MIN:
            rec.setdefault("eventos", []).append(
                {"tipo": "otro", "detalle": "posible vibrante simple (duración corta) — revisar"})
            rec["duda_rr"] = True
    except Exception:
        pass


def _preproc_audio(onda, modo_infantil):
    """Aplica (o no) el preprocesado de modo infantil (pitch/formant-shift) antes del modelo."""
    if not modo_infantil:
        return onda
    try:
        from pipeline.preproc_infantil import adapta_infantil
        from app import config
        return adapta_infantil(onda, config.PITCH_SHIFT_SEMITONOS)
    except Exception:
        return onda          # si el módulo no está, no rompe el flujo


def puntuar_palabra(palabra, onda, reintentada=False, estrategia=None, modo_infantil=None):
    """Procesa una palabra y devuelve el registro (mismo formato en ambas estrategias).
    estrategia: 'restringida' (def, hipótesis clínicas + GOP) o 'libre' (CTC abierto).
    modo_infantil: pitch-shift en test-time. Por defecto se leen de config."""
    from app import config
    estrategia = estrategia or config.ESTRATEGIA_RECONOCEDOR
    modo_infantil = config.MODO_INFANTIL if modo_infantil is None else modo_infantil
    onda = _preproc_audio(onda, modo_infantil)
    w2v = get_w2v()
    modo_audio = "infantil" if modo_infantil else "adulto"

    if estrategia == "restringida":
        rec = w2v.reconoce_restringido(onda, palabra)
        rec["reintentada"] = reintentada
        rec["modo_audio"] = modo_audio
        _anota_duda_rr(rec, onda, w2v)
        return rec

    # estrategia libre (original): transcripción abierta + alineamiento
    fon, conf = w2v.reconoce_conf(onda)
    ref, hyp = ref_clinico(palabra), normaliza_clinico(fon)
    cl = clasificar_errores(ref, hyp)
    return {"palabra": palabra, "esperado": " ".join(ref), "detectado": " ".join(hyp),
            "confianza": round(float(conf), 3), "reintentada": reintentada,
            "pcc": cl["pcc"], "eventos": cl["eventos"],
            "valida": cl["valida"], "motivo_no_valida": cl["motivo_no_valida"],
            "estrategia": "libre", "modo_audio": modo_audio}


def segmentos_alineados(onda):
    """Para el editor/informe: segmentos de fonema con tiempos (plegado clínico).
    Usa el modelo de INFORME (full fp32 en híbrido) para máxima calidad clínica."""
    segs_raw, dur = get_w2v("informe").reconoce_alineado(onda)
    segs = []
    for s in segs_raw:
        nz = normaliza_clinico([s["tok"]])
        if nz:
            segs.append({"label": nz[0], "t_ini": s["t_ini"], "t_fin": s["t_fin"],
                         "conf": s["conf"]})
    return {"segmentos": segs, "duracion": round(dur, 3)}


# ---------------------------------------------------------------- sesión / riesgo
def evaluar_sesion(palabras, edad, umbral_confianza=0.50):
    """Calcula el resumen de riesgo de una sesión (lista de registros de palabra)."""
    tabla = cargar_normas(RAIZ)
    return evaluar_riesgo(palabras, edad, tabla, umbral_confianza=umbral_confianza)


def prueba_actual(nino_id):
    """Número de la prueba en curso para el niño (= pruebas finalizadas + 1)."""
    conn = abrir_db()
    n = almacen.n_pruebas(conn, nino_id)
    conn.close()
    return n + 1


def palabras_falladas(nino_id):
    """Palabras con error clínico en pruebas previas del niño (para enfocar el re-test)."""
    conn = abrir_db()
    f = almacen.palabras_falladas(conn, nino_id)
    conn.close()
    return f


N_PALABRAS_PRUEBA = 15


def lista_palabras_prueba(nino_id):
    """Palabras a pedir en la prueba. 1ª prueba = 15 palabras ALEATORIAS que cubren todos
    los procesos de error (lista distinta cada vez). Re-test = núcleo + palabras falladas
    previas (para confirmar lo que falló)."""
    from pipeline.fonemas_canonicos import NUCLEO
    if prueba_actual(nino_id) <= 1:
        return _ejercicios.seleccionar_palabras_prueba(N_PALABRAS_PRUEBA)
    return sorted(set(NUCLEO) | set(palabras_falladas(nino_id)))


def registrar_audio(nino_id, palabra, onda, reintentada=False, guardar_wav=True,
                    ronda="principal"):
    """Puntúa una palabra, guarda el wav VERSIONADO por prueba (sesiones/<nino>/p<N>/,
    la ronda extra en p<N>/repeticion/) y la acumula en el estado de la prueba en curso.
    El audio NUNCA va al LLM."""
    estado = cargar_estado(nino_id) or {"historial": []}
    n = estado.get("n_prueba") or prueba_actual(nino_id)
    sesion_id = f"{nino_id}_p{n}"
    estado["n_prueba"], estado["sesion_id"] = n, sesion_id
    if guardar_wav:
        d = os.path.join(DIR_SESIONES, sesion_id,
                         *( ["repeticion"] if ronda == "repeticion" else [] ))
        os.makedirs(d, exist_ok=True)
        sf.write(os.path.join(d, f"{palabra}.wav"), onda, SR)
    from pipeline import vad
    registro = puntuar_palabra(palabra, onda, reintentada=reintentada)
    registro["calidad"] = vad.calidad(onda)        # puerta de calidad (para re-elicitar en la UI)
    # consentimiento de datos: si la familia lo autorizó, el audio va también a entrenamiento
    reg = estado.get("registro") or {}
    if reg.get("consentimiento_datos"):
        try:
            guardar_entrenamiento(palabra, onda, reg.get("edad"), nino_id, reg.get("sexo"))
        except Exception:
            pass
    if ronda == "repeticion":
        rep = estado.setdefault("repeticion", {"palabras": [], "procesos": []})
        rep["palabras"] = [p for p in rep["palabras"] if p["palabra"] != palabra] + [registro]
        total = len(rep["palabras"])
    else:
        pal = [p for p in estado.get("palabras", []) if p["palabra"] != palabra]
        pal.append(registro)
        estado["palabras"] = pal
        total = len(pal)
    guardar_estado(nino_id, estado)
    return {**registro, "palabras_en_sesion": total, "sesion_id": sesion_id,
            "n_prueba": n, "ronda": ronda}


def preparar_prueba(nino_id):
    """Prepara una prueba desde la UI (equivale a iniciar_prueba del grafo): fija el
    número de prueba en curso y vacía las palabras acumuladas. Evita que una prueba
    nueva reutilice el n_prueba de una ya finalizada."""
    estado = cargar_estado(nino_id) or {"historial": []}
    n = prueba_actual(nino_id)
    palabras = lista_palabras_prueba(nino_id)
    estado["n_prueba"], estado["sesion_id"], estado["palabras"] = n, f"{nino_id}_p{n}", []
    estado.pop("repeticion", None)
    guardar_estado(nino_id, estado)
    return {"palabras": palabras, "n_prueba": n, "sesion_id": f"{nino_id}_p{n}",
            "ronda": "principal"}


def abandonar_prueba(nino_id, ronda="principal"):
    """Descarta una prueba dejada a medias: borra los audios de la sesión en curso y
    vacía el estado SIN analizar nada. Las copias de ENTRENAMIENTO (si la familia marcó
    el consentimiento de datos) se conservan: se guardaron al subir cada palabra.
    En la ronda extra solo se descarta la subcarpeta 'repeticion' (la prueba principal
    ya está finalizada) y la oferta queda pendiente por si quieren retomarla."""
    import shutil
    estado = cargar_estado(nino_id) or {}
    n = estado.get("n_prueba") or prueba_actual(nino_id)
    base = os.path.join(DIR_SESIONES, f"{nino_id}_p{n}")
    if ronda == "repeticion":
        rep = estado.get("repeticion") or {}
        descartadas = len(rep.get("palabras", []))
        rep["palabras"] = []
        if estado.get("repeticion") is not None:
            estado["repeticion"] = rep
        ruta = os.path.join(base, "repeticion")
    else:
        descartadas = len(estado.get("palabras", []))
        estado["palabras"] = []
        ruta = base
    if descartadas and os.path.isdir(ruta):
        shutil.rmtree(ruta, ignore_errors=True)
    guardar_estado(nino_id, estado)
    return {"ok": True, "descartadas": descartadas, "ronda": ronda}


def oferta_repeticion(nino_id, informe, max_palabras=6):
    """Palabras para la ronda extra (solo re-tests con procesos NUEVOS vs histórico).
    Prefiere palabras DISTINTAS con la misma estructura del error; si no quedan, las que
    fallaron. Se presenta a la familia de forma NEUTRA (nunca 'porque falló')."""
    slugs_nuevos = (informe.get("persistencia") or {}).get("slugs_nuevos", [])
    if not slugs_nuevos:
        return None
    usadas = {p["palabra"] for p in informe.get("palabras", [])}
    seleccion, fallback = [], []
    for slug in slugs_nuevos:
        candidatas = _ejercicios.palabras_para_proceso(slug)
        nuevas = [w for w in candidatas if w not in usadas and w not in seleccion]
        if nuevas:
            seleccion.extend(nuevas[:2])
        else:   # sin alternativas: repetir las falladas con ese proceso
            fallback.extend(p["palabra"] for p in informe.get("palabras", [])
                            if any(e["tipo"] == slug for e in p.get("eventos", [])))
    palabras = (seleccion + [w for w in fallback if w not in seleccion])[:max_palabras]
    return {"palabras": palabras, "procesos": slugs_nuevos, "ventana_seg": 120} if palabras else None


def aplicar_repeticion(nino_id):
    """Cierra la ronda extra: si un proceso NUEVO no aparece en las palabras repetidas →
    'corregido' (se descuenta y SE RE-EVALÚA el riesgo); si reaparece → 'confirmado'
    (riesgo intacto). Todo queda anotado en el informe versionado y en la BD."""
    import copy
    estado = cargar_estado(nino_id) or {}
    rep = estado.get("repeticion") or {}
    repetidas = rep.get("palabras", [])
    n = estado.get("n_prueba") or prueba_actual(nino_id) - 1
    sesion_id = f"{nino_id}_p{n}"
    ruta = os.path.join(RAIZ, "results", f"informe_{sesion_id}.json")
    if not repetidas or not os.path.exists(ruta):
        return {"error": "No hay ronda de repetición pendiente."}
    with open(ruta, encoding="utf-8") as f:
        informe = json.load(f)
    objetivo = (informe.get("persistencia") or {}).get("slugs_nuevos", [])
    # solo cuentan las producciones VÁLIDAS de la ronda (si dijo otra cosa, no confirma nada)
    vistos = {e["tipo"] for p in repetidas if p.get("valida", True)
              for e in p.get("eventos", []) if e["tipo"] in ERRORES}
    corregidos = [s for s in objetivo if s not in vistos]
    confirmados = [s for s in objetivo if s in vistos]

    resultado = {"palabras": repetidas,
                 "procesos_corregidos": sorted(ERRORES[s] for s in corregidos),
                 "procesos_confirmados": sorted(ERRORES[s] for s in confirmados)}
    if corregidos:
        # re-evaluar descontando los procesos corregidos (los originales quedan anotados)
        palabras_corr = copy.deepcopy(informe["palabras"])
        for p in palabras_corr:
            p["eventos"] = [e for e in p.get("eventos", []) if e["tipo"] not in corregidos]
        resumen_corr = evaluar_sesion(palabras_corr, int(informe["registro"]["edad"]))
        resumen_corr["riesgo_corregido_tras_repeticion"] = True
        informe["resumen_riesgo_original"] = informe["resumen_riesgo"]
        informe["resumen_riesgo"] = resumen_corr
    informe["repeticion"] = resultado

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)
    conn = abrir_db()
    almacen.actualizar_evento_prueba(conn, nino_id, n, informe)
    conn.close()
    # refresca el resultado en el estado del chat y consume la ronda
    if estado.get("resultado"):
        estado["resultado"]["resumen"] = informe["resumen_riesgo"]
    estado.pop("repeticion", None)
    estado["repeticion_hecha"] = resultado
    guardar_estado(nino_id, estado)
    return {"ok": True, **resultado, "riesgo": informe["resumen_riesgo"]["riesgo"],
            "corregido": bool(corregidos)}


def _historial_procesos(nino_id):
    """(slugs de procesos vistos en pruebas previas, riesgo de la última prueba,
    palabras con error clínico en pruebas previas)."""
    conn = abrir_db()
    eventos = almacen.timeline(conn, nino_id)
    falladas = set(almacen.palabras_falladas(conn, nino_id))
    conn.close()
    slugs, riesgo_ultimo = set(), None
    for ev in eventos:
        if ev["tipo"] != "prueba_audio":
            continue
        inf = ev["payload"]
        riesgo_ultimo = inf.get("resumen_riesgo", {}).get("riesgo", riesgo_ultimo)
        for p in inf.get("palabras", []):
            slugs |= {e["tipo"] for e in p.get("eventos", []) if e["tipo"] in ERRORES}
    return slugs, riesgo_ultimo, falladas


def _calcular_persistencia(palabras, prev_slugs, prev_falladas):
    """Clasifica procesos (persistente/nuevo/resuelto) y anota estado_historico por palabra."""
    cur_slugs = set()
    for p in palabras:
        slugs_p = {e["tipo"] for e in p.get("eventos", []) if e["tipo"] in ERRORES}
        cur_slugs |= slugs_p
        if slugs_p:
            p["estado_historico"] = "persistente" if p["palabra"] in prev_falladas else "nuevo"
        elif p["palabra"] in prev_falladas:
            p["estado_historico"] = "resuelta"
    nombres = lambda ss: sorted(ERRORES[s] for s in ss)
    return {
        "procesos": {"persistentes": nombres(cur_slugs & prev_slugs),
                     "nuevos": nombres(cur_slugs - prev_slugs),
                     "resueltos": nombres(prev_slugs - cur_slugs)},
        "slugs_nuevos": sorted(cur_slugs - prev_slugs),
        "slugs_persistentes": sorted(cur_slugs & prev_slugs),
    }


def finalizar_sesion(nino_id, edad, palabras=None, n_prueba=None, alias=None,
                     factores=None, screening=None, guardar=True):
    """Cierra UNA prueba: puntúa, marca PERSISTENCIA vs histórico, aplica las VÁLVULAS
    (2 'alto' seguidos → especialista; baja inteligibilidad → repetir ya), guarda el
    informe versionado y registra el evento longitudinal. La propuesta de ejercicios va
    aparte. Devuelve {informe, resumen, sesion_id, n_prueba}."""
    estado = cargar_estado(nino_id) or {}
    palabras = palabras if palabras is not None else estado.get("palabras", [])
    n = n_prueba or estado.get("n_prueba") or prueba_actual(nino_id)
    sesion_id = f"{nino_id}_p{n}"

    prev_slugs, riesgo_ultimo, prev_falladas = _historial_procesos(nino_id)
    persistencia = _calcular_persistencia(palabras, prev_slugs, prev_falladas) if n > 1 else None
    resumen = evaluar_sesion(palabras, edad)

    # válvulas de seguridad sobre la recomendación
    if riesgo_ultimo == "alto" and resumen["riesgo"] == "alto":
        resumen["derivar_especialista"] = True
        resumen["recomendacion"] = ("El resultado se mantiene en dos pruebas seguidas: "
                                    "conviene pedir cita con un especialista (logopeda).")
    if resumen.get("baja_inteligibilidad"):
        resumen["repetir_ahora"] = True
        resumen["recomendacion"] = ("Muchas palabras no se oyeron con claridad; conviene "
                                    "repetir la prueba ahora, en un sitio tranquilo y con el "
                                    "micrófono más cerca.")

    informe = {"registro": {"nombre": alias or nino_id, "edad": edad, "nino_id": nino_id,
                            "n_prueba": n, "factores": factores or {}},
               "resumen_riesgo": resumen, "palabras": palabras}
    if persistencia:
        informe["persistencia"] = persistencia
    avisos = avisos_equidad(factores or (estado.get("registro") or {}))
    if avisos:
        informe["avisos_equidad"] = avisos
    if guardar:
        dir_res = os.path.join(RAIZ, "results")
        os.makedirs(dir_res, exist_ok=True)
        with open(os.path.join(dir_res, f"informe_{sesion_id}.json"), "w", encoding="utf-8") as f:
            json.dump(informe, f, ensure_ascii=False, indent=2)
        if screening:
            guardar_evento(nino_id, "screening", screening, alias=alias, edad=edad, factores=factores)
        guardar_evento(nino_id, "prueba_audio", informe, alias=alias, edad=edad,
                       factores=factores, n_prueba=n)
    return {"informe": informe, "resumen": resumen, "sesion_id": sesion_id, "n_prueba": n}


def repuntuar_informe(informe):
    """Re-puntúa un informe a partir del campo 'detectado' de cada palabra
    (reusa la lógica de scripts/reanalizar.py). Útil tras edición del logopeda."""
    edad = int(informe["registro"]["edad"])
    tabla = cargar_normas(RAIZ)
    for p in informe["palabras"]:
        ref = ref_clinico(p["palabra"])
        hyp = p["detectado"].split()
        cl = clasificar_errores(ref, hyp)
        p["eventos"], p["pcc"] = cl["eventos"], cl["pcc"]
        p["valida"], p["motivo_no_valida"] = cl["valida"], cl["motivo_no_valida"]
    informe["resumen_riesgo"] = evaluar_riesgo(informe["palabras"], edad, tabla)
    return informe


def aplicar_ediciones(informe, ediciones):
    """ediciones: {palabra: 'nueva secuencia detectada'}; actualiza y re-puntúa."""
    by_word = {p["palabra"]: p for p in informe["palabras"]}
    for palabra, secuencia in ediciones.items():
        if palabra in by_word:
            by_word[palabra]["detectado"] = secuencia
            by_word[palabra]["editada"] = True
    return repuntuar_informe(informe)


# ---------------------------------------------------------------- ejercicios / screening
def proponer_ejercicios_para(resumen_riesgo, edad, hoy=None):
    import datetime
    hoy = hoy or datetime.date.today().isoformat()
    return _ejercicios.proponer_ejercicios(resumen_riesgo, edad, raiz=RAIZ, hoy=hoy)


def propuesta_tras_prueba(nino_id):
    """Propuesta DETERMINISTA tras la prueba: ejercicios según el riesgo (bajo=1×N1 ·
    medio=N1+N2 · alto=N1+N2+N3 relacionado con los errores) y recomendación de repetir
    la prueba tras el plazo del plan. Registra la asignación una vez por sesión."""
    estado = cargar_estado(nino_id) or {}
    res = estado.get("resultado") or {}
    resumen = res.get("resumen")
    if not resumen:
        return {"error": "Todavía no hay resultado de prueba."}
    edad = int((estado.get("registro") or {}).get("edad") or 5)
    plan = proponer_ejercicios_para(resumen, edad)
    if estado.get("ejercicios_sesion") != res.get("sesion_id"):
        guardar_evento(nino_id, "ejercicios_asignados", plan)
        estado["ejercicios_sesion"] = res.get("sesion_id")
    estado["ejercicios"] = plan
    guardar_estado(nino_id, estado)
    return plan


def reevaluar_pruebas_edad(nino_id, edad):
    """Recalcula el riesgo de TODAS las pruebas guardadas con la edad indicada, para que
    los informes (familia y especialista) reflejen la edad corregida. Devuelve el nº de
    pruebas actualizadas."""
    conn = abrir_db()
    eventos = almacen.timeline(conn, nino_id)
    actualizadas = 0
    for ev in eventos:
        if ev["tipo"] != "prueba_audio":
            continue
        inf = ev["payload"]
        palabras = inf.get("palabras", [])
        if not palabras:
            continue
        inf["resumen_riesgo"] = evaluar_sesion(palabras, edad)
        inf.setdefault("registro", {})["edad"] = edad
        almacen.actualizar_evento_prueba(conn, nino_id, ev["n_prueba"], inf)
        ruta = os.path.join(RAIZ, "results", f"informe_{nino_id}_p{ev['n_prueba']}.json")
        if os.path.exists(ruta):
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(inf, f, ensure_ascii=False, indent=2)
        actualizadas += 1
    conn.close()
    return actualizadas


def biblioteca_ejercicios(edad=None, riesgo=None):
    """Catálogo completo agrupado por nivel/edad (pantalla 'todos los ejercicios')."""
    return _ejercicios.biblioteca(RAIZ, edad=edad, riesgo=riesgo)


def plan_seguimiento_filas():
    return _ejercicios.cargar_plan_filas(RAIZ)


def guardar_plan_seguimiento(filas):
    return _ejercicios.guardar_plan_filas(RAIZ, filas)


def desmarcar_ejercicio(nino_id, titulo):
    """Quita la marca de 'ejercicio hecho' (borra el último evento con ese título)."""
    conn = abrir_db()
    ok = almacen.eliminar_ejercicio_realizado(conn, nino_id, titulo)
    conn.close()
    return ok


def evaluar_screening_respuestas(respuestas, edad):
    return _screening.evaluar_screening(respuestas, edad, raiz=RAIZ)


def items_screening():
    return _screening.cargar(RAIZ)


# ---------------------------------------------------------------- análisis clínico
def _cons_de(esperado):
    """Nº de consonantes de la secuencia esperada (para agregar PCC por grupo)."""
    from pipeline.clinico import CONS
    return sum(1 for t in str(esperado).split() if t in CONS)


def analisis_clinico(informe):
    """Resumen técnico para el PROFESIONAL (determinista): severidad PCC global, por
    PALABRA y por GRUPO de error (% + etiqueta), conteo de procesos y atípicos.
    La familia NO ve esto: su vista es resumen_familiar()."""
    from pipeline import calibracion as _calib
    calib = _calib.cargar(RAIZ)        # informativo (avisa de artefactos del ASR; NO descuenta)
    palabras = informe.get("palabras", [])
    rr = informe.get("resumen_riesgo", {})
    pccs = [p["pcc"] for p in palabras if isinstance(p.get("pcc"), (int, float))]
    pcc_medio = round(sum(pccs) / len(pccs), 1) if pccs else None

    # conteo de procesos por slug + oportunidades + agregados de consonantes por grupo
    conteo, palabras_con, grupo_cons = {}, {}, {}
    severidad_por_palabra, baja_fiabilidad, pcc_cal = [], [], []
    for p in palabras:
        pcc_p = p.get("pcc")
        cons = _cons_de(p.get("esperado", ""))
        fiab = _calib.fiabilidad(calib, p.get("palabra"))
        if isinstance(pcc_p, (int, float)):
            info = calib.get(p.get("palabra")) or {}
            esp = info.get("pcc_esperado")
            # PCC calibrado: rendimiento RELATIVO al techo del propio reconocedor en esa palabra
            pccc = round(min(100.0, 100.0 * pcc_p / esp), 1) if esp else None
            if pccc is not None:
                pcc_cal.append(pccc)
            severidad_por_palabra.append({
                "palabra": p.get("palabra"), "pcc": pcc_p, "severidad": severidad_pcc(pcc_p),
                "fiabilidad": fiab, "pcc_calibrado": pccc,
                **({"estado_historico": p["estado_historico"]} if p.get("estado_historico") else {}),
            })
        if fiab is not None and fiab < _calib.UMBRAL_BAJA_FIABILIDAD:
            baja_fiabilidad.append(p.get("palabra"))
        slugs_pal = {e["tipo"] for e in p.get("eventos", []) if e["tipo"] in ERRORES}
        for slug in slugs_pal:
            palabras_con[slug] = palabras_con.get(slug, 0) + 1
            if isinstance(pcc_p, (int, float)) and cons:
                g = grupo_cons.setdefault(slug, [0.0, 0])
                g[0] += pcc_p / 100.0 * cons     # consonantes correctas estimadas
                g[1] += cons
        for e in p.get("eventos", []):
            if e["tipo"] in ERRORES:
                conteo[e["tipo"]] = conteo.get(e["tipo"], 0) + 1

    # calibración por palabra (informativa: avisa de artefactos del ASR, NO descuenta nada)
    palabras_de_slug = {}
    for p in palabras:
        for e in p.get("eventos", []):
            if e["tipo"] in ERRORES:
                palabras_de_slug.setdefault(e["tipo"], set()).add(p.get("palabra"))

    procesos, pcc_por_grupo = [], []
    n_pal = max(1, len(palabras))
    for slug, n in sorted(conteo.items(), key=lambda kv: kv[1], reverse=True):
        afectadas = palabras_de_slug.get(slug, set())
        artefacto = bool(calib) and any(_calib.es_artefacto(calib, w, slug) for w in afectadas)
        procesos.append({
            "proceso": ERRORES[slug], "slug": slug, "ocurrencias": n,
            "palabras_afectadas": palabras_con.get(slug, 0),
            "pct_palabras": round(100.0 * palabras_con.get(slug, 0) / n_pal, 1),
            "atipico": slug in ATIPICOS,
            "posible_artefacto_asr": artefacto,
        })
        ok, tot = grupo_cons.get(slug, (0.0, 0))
        if tot:
            pcc_g = round(100.0 * ok / tot, 1)
            pcc_por_grupo.append({"proceso": ERRORES[slug], "slug": slug,
                                  "n_palabras": palabras_con.get(slug, 0),
                                  "pcc": pcc_g, "severidad": severidad_pcc(pcc_g)})

    return {
        "pcc_medio": pcc_medio,
        "pcc_calibrado_medio": round(sum(pcc_cal) / len(pcc_cal), 1) if pcc_cal else None,
        "severidad_pcc": severidad_pcc(pcc_medio),
        "severidad_por_palabra": severidad_por_palabra,
        "pcc_por_grupo": pcc_por_grupo,
        "riesgo": rr.get("riesgo"),
        "n_errores_impropios": rr.get("n_errores_impropios"),
        "inteligibilidad_media": rr.get("inteligibilidad_media"),
        "procesos": procesos,
        "procesos_atipicos": [p["proceso"] for p in procesos if p["atipico"]],
        "palabras_baja_fiabilidad": baja_fiabilidad,
        "persistencia": informe.get("persistencia"),
        "nota": "Severidad por PCC (Shriberg & Kwiatkowski): leve >85 · leve-moderado 65-85 · "
                "moderado-grave 50-65 · grave <50. Calibración: el reconocedor tiene un suelo "
                "de error ~18% (PER adultos), que reduce el PCC aparente. Cribado, no "
                "diagnóstico; apoyo a la decisión del profesional.",
    }


def resumen_familiar(informe):
    """Vista SIMPLE para la familia: SOLO nivel de riesgo + recomendación (sin cifras,
    sin detalle por palabra/grupo). El detalle vive en el informe profesional descargable."""
    rr = informe.get("resumen_riesgo", {})
    return {
        "nivel_riesgo": rr.get("riesgo"),
        "recomendacion": rr.get("recomendacion"),
        "encuadre": "Esta prueba orienta sobre el habla, no es un diagnóstico. Si quieres, "
                    "puedes descargar el informe completo para el especialista.",
    }


def avisos_equidad(factores):
    """Avisos para el PROFESIONAL según los datos del registro (no modifican el riesgo)."""
    avisos = []
    f = factores or {}
    if f.get("bilinguismo"):
        avisos.append("Entorno bilingüe: parte de las diferencias puede ser transferencia "
                      "entre lenguas, no un trastorno (interpretar con cautela).")
    lm = str(f.get("lengua_materna") or "").strip().lower()
    if lm and lm not in ("es", "español", "espanol", "castellano"):
        avisos.append(f"Lengua materna '{f.get('lengua_materna')}': posibles patrones de L2; "
                      "valorar transferencia interlingüística.")
    if f.get("problemas_auditivos"):
        avisos.append("Antecedentes auditivos (otitis/hipoacusia): descartar causa auditiva "
                      "antes de interpretar los errores como fonológicos.")
    return avisos


# ---------------------------------------------------------------- almacén
def abrir_db():
    return almacen.conectar(RAIZ)


def guardar_entrenamiento(palabra, onda, edad, nino_id, sexo=None):
    """Si hay consentimiento, copia el audio a la carpeta de ENTRENAMIENTO compartida
    (anonimizada) y registra la etiqueta. RGPD: id seudónimo->hash, solo edad/sexo/palabra."""
    import csv
    import datetime
    import hashlib
    id_anon = hashlib.sha1(str(nino_id).encode()).hexdigest()[:10]
    dir_pal = os.path.join(DIR_ENTRENAMIENTO, palabra)
    os.makedirs(dir_pal, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    nombre = f"{id_anon}_{ts}.wav"
    sf.write(os.path.join(dir_pal, nombre), onda, SR)
    etiquetas = os.path.join(DIR_ENTRENAMIENTO, "etiquetas.csv")
    nuevo = not os.path.exists(etiquetas)
    with open(etiquetas, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["palabra", "edad", "sexo", "ruta", "fecha", "id_anon"])
        w.writerow([palabra, edad, sexo or "", os.path.join(palabra, nombre), ts, id_anon])


def registrar_nino(nino_id, alias=None, edad=None, sexo=None, factores=None):
    """Crea/actualiza el registro del niño (sin añadir evento)."""
    conn = abrir_db()
    almacen.registrar_nino(conn, nino_id, alias=alias, edad=edad, sexo=sexo, factores=factores)
    conn.close()


def listar_ninos():
    """Perfiles registrados, con nº de pruebas hechas (para el selector de la UI)."""
    conn = abrir_db()
    ninos = almacen.listar_ninos(conn)
    for n in ninos:
        n["n_pruebas"] = almacen.n_pruebas(conn, n["id"])
    conn.close()
    return ninos


def obtener_nino(nino_id):
    conn = abrir_db()
    n = almacen.obtener_nino(conn, nino_id)
    if n is not None:
        n["n_pruebas"] = almacen.n_pruebas(conn, nino_id)
    conn.close()
    return n


def eliminar_nino(nino_id):
    """Borra por completo un perfil: BD (perfil, eventos, estado de chat), audios de sus
    sesiones (data/raw/sesiones/<id>_p*) e informes (results/informe_<id>*)."""
    import glob
    import shutil
    conn = abrir_db()
    almacen.eliminar_nino(conn, nino_id)
    conn.close()
    for d in glob.glob(os.path.join(DIR_SESIONES, f"{nino_id}_p*")):
        shutil.rmtree(d, ignore_errors=True)
    for f in glob.glob(os.path.join(RAIZ, "results", f"informe_{nino_id}_p*")) + \
             glob.glob(os.path.join(RAIZ, "results", f"informe_{nino_id}.*")):
        try:
            os.remove(f)
        except OSError:
            pass
    return {"ok": True}


ESTRELLAS_POR_PRUEBA = 3      # gamificación por PARTICIPACIÓN (nunca por rendimiento)
ESTRELLAS_POR_EJERCICIO = 1


def historico_familiar(nino_id):
    """Histórico para la vista de FAMILIA: pruebas con su riesgo GENERAL (nunca detalle
    por palabra), ejercicios hechos/propuestos y estrellas por participación."""
    conn = abrir_db()
    eventos = almacen.timeline(conn, nino_id)
    conn.close()
    pruebas, hechos, propuestos = [], [], []
    for ev in eventos:
        if ev["tipo"] == "prueba_audio":
            inf = ev["payload"]
            rr = inf.get("resumen_riesgo", {})
            pruebas.append({"n_prueba": ev["n_prueba"], "fecha": ev["ts"],
                            "n_palabras_jugadas": len(inf.get("palabras", [])),
                            "riesgo_general": rr.get("riesgo"),
                            "recomendacion": rr.get("recomendacion"),
                            "estrellas": ESTRELLAS_POR_PRUEBA})
        elif ev["tipo"] in almacen._EJERCICIO_HECHO:
            hechos.append({"titulo": ev["payload"].get("titulo"), "fecha": ev["ts"]})
        elif ev["tipo"] in almacen._EJERCICIO_ASIGNADO:
            propuestos = ev["payload"].get("ejercicios") or propuestos
    return {"pruebas": pruebas, "ejercicios_hechos": hechos,
            "ejercicios_propuestos": propuestos,
            "estrellas_total": (ESTRELLAS_POR_PRUEBA * len(pruebas)
                                + ESTRELLAS_POR_EJERCICIO * len(hechos)),
            "informe_url": f"/informe/{nino_id}/html",
            "pdf_url": f"/informe/{nino_id}/pdf"}


def guardar_evento(nino_id, tipo, payload=None, alias=None, edad=None, sexo=None,
                   factores=None, ts=None, n_prueba=None):
    """Registra el niño (si hace falta) y añade un evento. Devuelve el id del evento."""
    conn = abrir_db()
    almacen.registrar_nino(conn, nino_id, alias=alias, edad=edad, sexo=sexo, factores=factores)
    ev_id = almacen.añadir_evento(conn, nino_id, tipo, payload=payload, ts=ts, n_prueba=n_prueba)
    conn.close()
    return ev_id


def evolucion_longitudinal(nino_id):
    conn = abrir_db()
    ev = almacen.evolucion(conn, nino_id)
    conn.close()
    return ev


def exportar_y_enlace(nino_id, email=None):
    """Enlaces para enviar/ver el informe del especialista (se generan bajo demanda en
    sus endpoints: informe_url HTML, pdf_url PDF) y un mailto prerrellenado. mailto NO
    adjunta ficheros: el cuerpo pide adjuntar el informe descargado. Devuelve
    {informe_url, pdf_url, mailto_url}."""
    import urllib.parse
    salida = {"informe_url": f"/informe/{nino_id}/html",
              "pdf_url": f"/informe/{nino_id}/pdf", "mailto_url": None}
    if email:
        asunto = f"Informe de cribado fonológico — {nino_id}"
        cuerpo = ("Le remito el informe de cribado fonológico para su valoración experta. "
                  "Adjunto el informe descargado desde la aplicación.\n\n"
                  "(Herramienta de cribado orientativa, NO es un diagnóstico.)")
        params = urllib.parse.urlencode({"subject": asunto, "body": cuerpo},
                                        quote_via=urllib.parse.quote)
        salida["mailto_url"] = f"mailto:{email}?{params}"
    return salida


# ---------------------------------------------------------------- estado de chat (servidor)
def cargar_estado(sesion_id):
    conn = abrir_db()
    estado = almacen.cargar_estado(conn, sesion_id)
    conn.close()
    return estado


def guardar_estado(sesion_id, estado):
    conn = abrir_db()
    almacen.guardar_estado(conn, sesion_id, estado)
    conn.close()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    import json
    ruta = os.path.join(RAIZ, "results", "informe_diego_6.json")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            informe = json.load(f)
        ac = analisis_clinico(informe)
        print("Análisis clínico de informe_diego_6.json:")
        print(json.dumps(ac, ensure_ascii=False, indent=2))
        plan = proponer_ejercicios_para(informe["resumen_riesgo"], informe["registro"]["edad"])
        print(f"\nTerapia propuesta: {len(plan['actividades'])} actividades, nivel {plan['nivel']}.")
    else:
        print("(no hay results/informe_diego_6.json para la demo)")
