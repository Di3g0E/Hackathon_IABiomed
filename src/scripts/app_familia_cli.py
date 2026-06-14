"""
CLI del grafo FAMILIA/NIÑO — chat CONDUCIDO POR EL LLM (Lumi).

Tú escribes y Lumi conduce el proceso (registro → grabación → resultado → ejercicios → envío),
emitiendo ACCIONES. Como no hay micrófono aquí, cuando Lumi pide grabar, el CLI SIMULA la
grabación puntuando los wav de una sesión (data/raw/sesiones/<sesion>). El registro se
autorrellena desde los argumentos. El resto es interactivo (escribe lo que quieras).

Ejecutar:
  uv run python src/scripts/app_familia_cli.py --alias Ana --edad 5 --sesion diego_6
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import librosa

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from app import config, herramientas
from app.config import DIR_SESIONES, safe_id
from app.grafo_familia import responder

SR = 16_000


def _mostrar(turno):
    print(f"\n🦊 Lumi: {turno['mensaje']}")
    acc, datos = turno.get("accion"), turno.get("datos") or {}
    if acc == "mostrar_resultado":
        print(f"   [vista familiar: nivel {datos.get('nivel_riesgo')} — {datos.get('recomendacion')}]")
        if datos.get("ronda_extra"):
            print(f"   [UI: botón '¿jugamos una ronda más?' → {datos['ronda_extra']['palabras']}]")
    elif acc == "mostrar_ejercicios":
        print(f"   [ejercicios · plazo {datos.get('plazo')} · re-test {datos.get('fecha_retest')}"
              f"{' · seguimiento OPCIONAL' if datos.get('seguimiento_opcional') else ''}]")
        for a in datos.get("ejercicios", []):
            print(f"     • N{a.get('nivel', '?')} {a['titulo']}: {a['actividad'][:80]}…")
    elif acc == "ofrecer_envio":
        print(f"   [descargar PDF: {datos.get('pdf_url')}]")
        print(f"   [enviar al especialista: {(datos.get('mailto_url') or '')[:70]}…]")
    elif acc:
        print(f"   [acción para la UI: {acc}]")
    return turno.get("accion"), datos


def _autorrellenar_registro(nino_id, args):
    estado = herramientas.cargar_estado(nino_id) or {"historial": []}
    estado["registro"] = {"nombre": args.alias, "edad": args.edad, "sexo": None,
                          "lengua_materna": args.idiomas, "bilinguismo": False,
                          "problemas_auditivos": False,
                          "email_especialista": args.email, "consentimiento": True}
    herramientas.guardar_estado(nino_id, estado)
    print(f"   (registro autorrellenado: {args.alias}, edad {args.edad}, "
          f"lengua '{args.idiomas}', email {args.email})")


def _simular_grabacion(nino_id, palabras, sesion, ronda="principal"):
    """Puntúa los wav disponibles de 'sesion' para las palabras pedidas (sin micrófono)."""
    hechas = 0
    for palabra in palabras:
        w = os.path.join(DIR_SESIONES, sesion, f"{palabra}.wav")
        if os.path.exists(w):
            onda, _ = librosa.load(w, sr=SR, mono=True)
            herramientas.registrar_audio(nino_id, palabra, onda, ronda=ronda)
            hechas += 1
    print(f"   (grabación simulada [{ronda}]: {hechas}/{len(palabras)} palabras desde '{sesion}')")
    return hechas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alias", default="Ana")
    ap.add_argument("--edad", type=int, default=5)
    ap.add_argument("--sesion", default="diego_6", help="carpeta de audios para simular la grabación")
    ap.add_argument("--idiomas", default="es")
    ap.add_argument("--email", default="logopeda@clinica.es")
    args = ap.parse_args()

    print("=" * 64)
    print(f"  CHATBOT FAMILIA (Lumi) — {'LLM Groq' if config.hay_llm() else 'modo respaldo (sin GROQ_API_KEY)'}")
    print("=" * 64)
    nino_id = safe_id(f"{args.alias.lower()}_{args.edad}")
    print("(Escribe para hablar con Lumi. Comandos: /salir)")

    pendiente = "Hola"     # primer mensaje
    while True:
        turno = responder(nino_id, pendiente, None)
        accion, datos = _mostrar(turno)

        # acciones que el CLI resuelve automáticamente y continúa el flujo
        if accion == "pedir_registro":
            _autorrellenar_registro(nino_id, args)
            pendiente = "Ya he rellenado los datos."
            continue
        if accion == "iniciar_grabacion":
            ronda = datos.get("ronda", "principal")
            _simular_grabacion(nino_id, datos.get("palabras", []), args.sesion, ronda=ronda)
            pendiente = ("Hemos terminado la ronda extra." if ronda == "repeticion"
                         else "He terminado de grabar.")
            continue

        # turno normal: espera a que el usuario escriba
        try:
            pendiente = input("\n🧑 Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n¡Hasta luego!"); break
        if pendiente.lower() in ("/salir", "salir", "/exit"):
            print("¡Hasta luego!"); break
        if not pendiente:
            pendiente = "(continúa)"


if __name__ == "__main__":
    main()
