"""
DEMO de la aplicación — motor de cribado fonológico end-to-end.

Flujo: registro (edad/sexo/origen) -> grabación de las 32 palabras -> reconocimiento
de fonemas + confianza -> clasificación de los 8 errores -> riesgo por edad + informe.

Como no hay audio infantil de las 32 palabras, el demo ENSAMBLA una "sesión"
con un clip por palabra de los audios disponibles (adultos), para mostrar el flujo
completo. Además demuestra el motor de riesgo en los 3 niveles con casos sintéticos.

Ejecutar:  uv run python src/scripts/app_demo.py
"""
from __future__ import annotations

import os
import sys
import json

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd
import librosa

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from pipeline.reconocedor import W2V
from pipeline.clinico import normaliza_clinico, ref_clinico, clasificar_errores, evaluar_riesgo
from pipeline.normas import cargar as cargar_normas

META = os.path.join(RAIZ, "data", "processed", "metadata.csv")
DIR_RES = os.path.join(RAIZ, "results")
EDAD_DEMO = 5


def sesion_demo(df):
    """Un clip por palabra (primer disponible) -> simula una sesión de 32 palabras."""
    return df.sort_values("ruta_proc").groupby("palabra", as_index=False).first()


def procesar_sesion(df_sesion, w2v):
    palabras = []
    for _, r in df_sesion.iterrows():
        wav, _ = librosa.load(os.path.join(RAIZ, r["ruta_proc"]), sr=16000)
        tokens, conf = w2v.reconoce_conf(wav)
        ref = ref_clinico(r["palabra"])
        hyp = normaliza_clinico(tokens)
        cl = clasificar_errores(ref, hyp)
        palabras.append({
            "palabra": r["palabra"], "esperado": " ".join(ref), "detectado": " ".join(hyp),
            "confianza": round(conf, 3), "pcc": cl["pcc"],
            "eventos": cl["eventos"],
        })
    return palabras


def main():
    df = pd.read_csv(META)
    df = df[df["ruta_proc"].notna() & (df["ruta_proc"] != "")].reset_index(drop=True)
    tabla = cargar_normas(RAIZ)

    print("### 1) Registro (en la app real: edad manual; sexo/origen autosugeridos por T3/T2) ###")
    registro = {"id": "demo", "edad": EDAD_DEMO, "sexo": "(T3)", "origen": "(T2)"}
    print(f"   {registro}")

    print("\n### 2-4) 32 palabras -> fonemas + confianza -> errores ###")
    print("Cargando reconocedor...")
    w2v = W2V()
    sesion = sesion_demo(df)
    palabras = procesar_sesion(sesion, w2v)
    resumen = evaluar_riesgo(palabras, EDAD_DEMO, tabla)

    informe = {"registro": registro, "resumen_riesgo": resumen, "palabras": palabras}
    os.makedirs(DIR_RES, exist_ok=True)
    with open(os.path.join(DIR_RES, "informe_demo.json"), "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)

    print(f"\n--- INFORME (sesión de {len(palabras)} palabras adultas) ---")
    print(f"  Inteligibilidad media: {resumen['inteligibilidad_media']}")
    print(f"  Errores detectados por tipo: {resumen['errores_por_tipo']}")
    print("  Riesgo según la EDAD declarada (muestra la sensibilidad por edad):")
    for e in (3, 4, 5, 6):
        r = evaluar_riesgo(palabras, e, tabla)
        print(f"     edad {e}: {r['riesgo'].upper():6s} (impropios={r['n_errores_impropios']})")
    print("  NOTA honesta: el ~18% de error del reconocedor en adultos inyecta falsos "
          "errores; a edades altas se cuentan como 'alerta' y sobre-marca. A los 3 años "
          "(casi todo 'normal') sale BAJO. Confirma que hay que adaptar el reconocedor a "
          "voz infantil y calibrar umbrales sobre el suelo de ruido.")

    # ---- Demostración del motor de riesgo en los 3 niveles (casos sintéticos, edad 5) ----
    print("\n### Demostración del motor de riesgo (edad 5) ###")
    def caso(eventos, conf=0.8):
        return [{"eventos": eventos, "confianza": conf}]
    casos = {
        "BAJO (1 error alerta)": caso([{"tipo": "reduccion_grupos", "detalle": ""}]),
        "MEDIO (3 errores alerta)": caso([{"tipo": "oclusivizacion", "detalle": ""}] * 3),
        "ALTO (>5 errores alerta)": caso([{"tipo": "omision_silabas", "detalle": ""}] * 6),
        "ALTO (baja inteligibilidad)": caso([{"tipo": "otro", "detalle": ""}], conf=0.35),
    }
    for nombre, pal in casos.items():
        r = evaluar_riesgo(pal, 5, tabla)
        print(f"  {nombre:30s} -> {r['riesgo'].upper()} "
              f"(impropios={r['n_errores_impropios']}, intel={r['inteligibilidad_media']})")

    print("\nGuardado: results/informe_demo.json")


if __name__ == "__main__":
    main()