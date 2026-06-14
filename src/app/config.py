"""
Configuración central de la app TDL: rutas, modelos Groq y carga de .env.

GROQ_API_KEY se lee de .env (en la raíz del repo) o del entorno. Copia .env.example
a .env y pon tu clave. Modelos configurables por entorno (MODELO_ORQUESTADOR / MODELO_LIGERO).
"""
from __future__ import annotations

import os
import re

from dotenv import load_dotenv

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.dirname(SRC)

load_dotenv(os.path.join(RAIZ, ".env"))

# --- Rutas ---
DIR_DATA = os.path.join(RAIZ, "data")
DIR_RESULTS = os.path.join(RAIZ, "results")
DIR_SESIONES = os.path.join(DIR_DATA, "raw", "sesiones")
DIR_ENTRENAMIENTO = os.path.join(DIR_DATA, "entrenamiento")   # audios con consentimiento
DIR_STATIC = os.path.join(SRC, "app", "static")

# --- Reconocedor de fonemas (estrategia conmutable) ---
# "restringida" = decodificación por hipótesis clínicas + GOP (por defecto, menos ruido)
# "libre"       = decodificación CTC abierta (la original; disponible para comparar)
ESTRATEGIA_RECONOCEDOR = os.getenv("ESTRATEGIA_RECONOCEDOR", "restringida")
# Modo infantil: pitch/formant-shift en test-time hacia rango adulto (mismo modelo)
MODO_INFANTIL = os.getenv("MODO_INFANTIL", "0") in ("1", "true", "True", "si", "sí")
PITCH_SHIFT_SEMITONOS = float(os.getenv("PITCH_SHIFT_SEMITONOS", "4"))
LORA_ADAPTER = os.getenv("LORA_ADAPTER", "")                  # ruta a adapter LoRA (futuro)
USAR_VAD = os.getenv("USAR_VAD", "1") in ("1", "true", "True", "si", "sí")

# --- LLM (Groq) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# 70b para orquestación/redacción; 8b para pasos simples/rápidos.
MODELO_ORQUESTADOR = os.getenv("MODELO_ORQUESTADOR", "llama-3.3-70b-versatile")
MODELO_LIGERO = os.getenv("MODELO_LIGERO", "llama-3.1-8b-instant")
TEMPERATURA = float(os.getenv("TEMPERATURA", "0.4"))


def hay_llm():
    return bool(GROQ_API_KEY)


# --- Saneado de identificadores que llegan de la API (evita path traversal) ---
_RE_ID = re.compile(r"[^A-Za-z0-9_-]")


def safe_id(s, fallback="sesion"):
    """ID de sesión/niño seguro para usar en rutas: solo [A-Za-z0-9_-], máx 64."""
    limpio = _RE_ID.sub("", str(s or ""))[:64]
    return limpio or fallback


def safe_palabra(p):
    """Nombre de palabra seguro para fichero (conserva letras como 'ñ'/acentos,
    bloquea separadores y '..')."""
    limpio = str(p or "").replace("/", "").replace("\\", "").replace("..", "").strip()
    return limpio[:40] or "palabra"


def chat(modelo=None, temperatura=None):
    """Crea un ChatGroq. Lanza un error claro si falta la clave."""
    if not GROQ_API_KEY:
        raise RuntimeError(
            "Falta GROQ_API_KEY. Copia .env.example a .env y añade tu clave de Groq "
            "(https://console.groq.com/keys).")
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=modelo or MODELO_ORQUESTADOR,
        temperature=TEMPERATURA if temperatura is None else temperatura,
        api_key=GROQ_API_KEY,
    )
