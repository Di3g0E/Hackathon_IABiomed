"""
CLI del grafo LOGOPEDA/SANITARIO — asistente profesional sobre una sesión.

Con GROQ_API_KEY responde el agente con tool-calling real; sin clave, da un resumen
profesional determinista (análisis clínico + plan + evolución + genera el editor).

Ejecutar:
  uv run python src/scripts/app_logopeda_cli.py --sesion diego_6
  uv run python src/scripts/app_logopeda_cli.py --sesion diego_6 --mensaje "Exporta el PDF para derivar"
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)

from app import config
from app.grafo_logopeda import responder


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sesion", default="diego_6")
    ap.add_argument("--mensaje", default="Analiza esta sesión y dime cómo está y qué hacer.")
    args = ap.parse_args()

    print("=" * 64)
    print(f"  ASISTENTE LOGOPEDA — {'LLM Groq' if config.hay_llm() else 'modo respaldo (sin GROQ_API_KEY)'}")
    print("=" * 64)
    print(f"\n👩‍⚕️ Profesional: {args.mensaje}\n")
    turno = responder(args.sesion, args.mensaje)
    print(f"🤖 Asistente:\n{turno['respuesta']}")


if __name__ == "__main__":
    main()
