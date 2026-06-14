"""
APP interactiva de cribado fonológico — para probarla como usuario (graba tu voz).

Flujo: registro (edad) -> grabas las palabras -> el sistema saca tus fonemas,
los compara con la palabra correcta, detecta los 8 errores y calcula el riesgo.

EJECUTAR EN TU TERMINAL (necesita micrófono; no funciona sin terminal interactiva):
    uv run python src/scripts/app.py            # 32 palabras
    uv run python src/scripts/app.py --rapida    # 8 palabras (prueba rápida)
    uv run python src/scripts/app.py --segundos 3 --edad 5
"""
from __future__ import annotations

import argparse
import os
import sys
import json
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import soundfile as sf

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from pipeline.fonemas_canonicos import REF
from pipeline.preprocessing import SilenceTrimmer, PeakNormalizer
from pipeline.clinico import evaluar_riesgo
from pipeline.normas import cargar as cargar_normas, ERRORES

SR = 16_000
PALABRAS = sorted(REF.keys())
RAPIDA = ["tres", "blanco", "rojo", "gorro", "cielo", "silla", "peine", "autobus"]
DIR_SES = os.path.join(RAIZ, "data", "raw", "sesiones")
DIR_RES = os.path.join(RAIZ, "results")
# top_db alto = recorte de silencio SUAVE (no se come inicios de palabra débiles).
_trim, _norm = SilenceTrimmer(top_db=35), PeakNormalizer()
PREROLL = 0.6      # s grabados ANTES del aviso (captura el inicio aunque hables pronto)
POSTROLL = 0.8     # s grabados DESPUÉS (no corta el final)
PICO_MIN = 0.02    # amplitud de pico (sin normalizar) por debajo de la cual = silencio
DUR_VOZ_MIN = 0.12  # s de audio con voz tras recortar silencio


def grabar(segundos, sr=SR, preroll=PREROLL, postroll=POSTROLL, pico_min=PICO_MIN):
    """Graba y devuelve (onda_procesada, calidad). 'calidad' (puerta VAD) incluye hay_voz y
    el motivo de repetir (no se oyó / ruido / saturado / varias voces)."""
    import sounddevice as sd
    from pipeline import vad
    total = preroll + segundos + postroll
    rec = sd.rec(int(total * sr), samplerate=sr, channels=1, dtype="float32")  # empieza YA
    for c in ("3", "2", "1"):
        print(f"   {c}", end="  ", flush=True); time.sleep(preroll / 3)
    print("🎙  ¡DI LA PALABRA!", flush=True)
    sd.wait()
    cruda = rec.reshape(-1)
    cal = vad.calidad(cruda, sr)                 # SNR/voz/clipping sobre el crudo
    onda = vad.recorta_voz(cruda, sr) if vad.disponible() else _trim.transform([cruda])[0]
    return _norm.transform([onda])[0], cal


def fmt_eventos(eventos, valida=True, motivo=None):
    if not valida:
        return (f"  ⚠ no se ha reconocido la palabra esperada ({motivo}) "
                "→ se marcará para repetir, no puntúa")
    reales = [e for e in eventos if e["tipo"] != "otro"]
    otras = [e for e in eventos if e["tipo"] == "otro" and e.get("detalle")]
    if not reales:
        base = "  ✓ sin procesos clínicos objetivo"
        if otras:
            base += ("  (otras discrepancias anotadas para el especialista: "
                     + "; ".join(e["detalle"] for e in otras) + ")")
        return base
    return "\n".join(f"  • {ERRORES.get(e['tipo'], e['tipo'])}: {e['detalle']}" for e in reales)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapida", action="store_true", help="solo 8 palabras")
    ap.add_argument("--segundos", type=float, default=2.5, help="duración de grabación por palabra")
    ap.add_argument("--edad", type=int, default=None, help="edad del niño (3-6)")
    ap.add_argument("--nombre", type=str, default=None)
    ap.add_argument("--pico-min", type=float, default=PICO_MIN,
                    help=f"umbral de energía para detectar voz (def {PICO_MIN}; menor=más sensible)")
    ap.add_argument("--umbral-confianza", type=float, default=0.50,
                    help="confianza mínima; por debajo se reintenta (def 0.50)")
    args = ap.parse_args()

    print("=" * 60)
    print("  CRIBADO FONOLÓGICO — herramienta de apoyo (NO diagnostica)")
    print("=" * 60)

    # --- Registro ---
    nombre = args.nombre or (input("Nombre/ID (Enter para 'usuario'): ").strip() or "usuario")
    edad = args.edad
    while edad is None:
        try:
            edad = int(input("Edad del niño (3-6): ").strip())
        except (ValueError, EOFError):
            print("  Introduce un número entre 3 y 6."); edad = None
    try:
        consent = input("¿Permites guardar la voz y la edad de forma anónima para mejorar el "
                        "sistema? (s/N): ").strip().lower() in ("s", "si", "sí")
    except EOFError:
        consent = False
    lista = RAPIDA if args.rapida else PALABRAS
    print(f"\nHola {nombre} (edad {edad}). Vas a pronunciar {len(lista)} palabras.")
    print("Para cada una: pulsa ENTER, espera la cuenta atrás y di la palabra UNA vez.\n")

    print("Cargando el modelo de reconocimiento (puede tardar la primera vez)...")
    from app import herramientas
    from app.config import ESTRATEGIA_RECONOCEDOR
    herramientas.get_w2v()                      # precarga (singleton compartido)
    print(f"(estrategia de reconocimiento: {ESTRATEGIA_RECONOCEDOR})")

    ses_id = f"{nombre}_{edad}"
    dir_ses = os.path.join(DIR_SES, ses_id)
    os.makedirs(dir_ses, exist_ok=True)

    UMBRAL = args.umbral_confianza
    print(f"(umbrales: voz≥{args.pico_min}, confianza≥{UMBRAL:.0%})")
    palabras = []
    for n, palabra in enumerate(lista, 1):
        try:
            input(f"[{n}/{len(lista)}] Pulsa ENTER y di:  «{palabra.upper()}»")
        except EOFError:
            print("\n(entrada no interactiva: abortando)"); return
        onda, cal = grabar(args.segundos, pico_min=args.pico_min)
        rec = herramientas.puntuar_palabra(palabra, onda)   # estrategia por defecto (config)
        reintentada = False
        motivo = (cal["motivo"] or                          # puerta de calidad de captura (VAD)
                  (f"baja confianza ({rec['confianza']:.0%})" if rec["confianza"] < UMBRAL else
                   rec["motivo_no_valida"] if not rec["valida"] else None))
        if motivo:
            print(f"   ⚠ {motivo}. Repite la palabra UNA vez.")
            try:
                input(f"   Pulsa ENTER y repite:  «{palabra.upper()}»")
            except EOFError:
                print("\n(abortando)"); return
            onda, cal = grabar(args.segundos, pico_min=args.pico_min)   # 2º intento (único)
            rec = herramientas.puntuar_palabra(palabra, onda)
            reintentada = True                     # cuenta como detección SI es válida
        sf.write(os.path.join(dir_ses, f"{palabra}.wav"), onda, SR)
        if consent:
            try:
                herramientas.guardar_entrenamiento(palabra, onda, edad, ses_id)
            except Exception:
                pass
        rec["reintentada"] = reintentada
        cl = rec                                   # alias para los prints de abajo
        hyp = rec["detectado"].split()
        conf = rec["confianza"]
        palabras.append(rec)
        print(f"   esperado: {rec['esperado']}")
        extra = ("  (reintento aceptado; cuenta como detección)"
                 if reintentada and cl["valida"] else "")
        print(f"   tú dijiste (fonemas): {' '.join(hyp)}   [confianza {conf:.0%}]{extra}")
        if not cl["valida"] and cl.get("transcripcion_libre"):
            print(f"   (se oyó: {cl['transcripcion_libre']})")
        print(fmt_eventos(cl["eventos"], cl["valida"], cl["motivo_no_valida"]), "\n")

    # --- Informe ---
    tabla = cargar_normas(RAIZ)
    resumen = evaluar_riesgo(palabras, edad, tabla, umbral_confianza=args.umbral_confianza)
    informe = {"registro": {"nombre": nombre, "edad": edad}, "resumen_riesgo": resumen,
               "palabras": palabras}
    os.makedirs(DIR_RES, exist_ok=True)
    ruta = os.path.join(DIR_RES, f"informe_{ses_id}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)

    emoji = {"bajo": "🟢", "medio": "🟡", "alto": "🔴"}[resumen["riesgo"]]
    print("=" * 60)
    print(f"  INFORME DE {nombre} (edad {edad})")
    print("=" * 60)
    print(f"  Inteligibilidad media: {resumen['inteligibilidad_media']:.0%}")
    print(f"  Palabras correctas: {resumen['palabras_correctas']}/{len(palabras)}")
    print(f"  Errores impropios para la edad: {resumen['n_errores_impropios']}")
    if resumen["palabras_a_repetir"]:
        print(f"  A repetir (baja confianza): {', '.join(resumen['palabras_a_repetir'])}")
    if resumen["errores_por_tipo"]:
        print("  Procesos detectados:")
        for tipo, n in resumen["errores_por_tipo"].items():
            print(f"     - {tipo}: {n}")
    print(f"\n  {emoji}  RIESGO {resumen['riesgo'].upper()} — {resumen['recomendacion']}")
    print(f"\n  Informe guardado en: {os.path.relpath(ruta, RAIZ)}")
    print("  (Cribado orientativo, no diagnóstico. Apoyo a logopeda/pediatra.)")


if __name__ == "__main__":
    main()