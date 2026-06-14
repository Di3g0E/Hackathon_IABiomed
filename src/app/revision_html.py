"""
Editor HTML interactivo de revisión para el especialista (extiende revisar_sesion.py).

Por cada palabra grabada genera: reproductor de audio, onda, y una LÍNEA DE TIEMPO de
fonemas EDITABLE — el logopeda arrastra dónde se sitúa cada letra sobre el audio, y
puede AÑADIR / ELIMINAR / RENOMBRAR letras. El botón "Re-puntuar" envía la secuencia
editada a POST /logopeda/reanalizar/{sesion} y actualiza el riesgo en vivo.

La página es auto-contenida (audio embebido en base64, CSS+JS en línea), así que también
abre como fichero; para RE-PUNTUAR necesita el servidor (la clasificación es Python).

Ejecutar:  uv run python src/app/revision_html.py [sesion]
"""
from __future__ import annotations

import base64
import glob
import json
import os
import sys

import librosa
import numpy as np

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from app import herramientas
from app.config import DIR_RESULTS, DIR_SESIONES, DIR_STATIC
from pipeline.clinico import clasificar_errores, ref_clinico

SR = 16_000
N_PEAKS = 360


def _peaks(wav):
    n = len(wav)
    if n == 0:
        return [0.0]
    paso = max(1, n // N_PEAKS)
    env = [float(np.max(np.abs(wav[i:i + paso]))) for i in range(0, n, paso)]
    m = max(env) or 1.0
    return [round(v / m, 3) for v in env]


def _audio_b64(ruta_wav):
    with open(ruta_wav, "rb") as f:
        return "data:audio/wav;base64," + base64.b64encode(f.read()).decode("ascii")


def construir_datos_sesion(ses_id, edad=None):
    """Reprocesa los wav de una sesión con el reconocedor y arma los datos del editor."""
    dir_ses = os.path.join(DIR_SESIONES, ses_id)
    wavs = sorted(glob.glob(os.path.join(dir_ses, "*.wav")))
    if not wavs:
        raise FileNotFoundError(f"Sin audios en {dir_ses}")
    if edad is None:
        try:
            edad = int(ses_id.rsplit("_", 1)[-1])
        except ValueError:
            edad = 5

    palabras_html, palabras_informe = [], []
    for w in wavs:
        palabra = os.path.splitext(os.path.basename(w))[0]
        wav, _ = librosa.load(w, sr=SR, mono=True)
        seg = herramientas.segmentos_alineados(wav)
        fon = [s["label"] for s in seg["segmentos"]]
        ref = ref_clinico(palabra)
        cl = clasificar_errores(ref, fon)
        conf = float(np.mean([s["conf"] for s in seg["segmentos"]])) if seg["segmentos"] else 0.0
        palabras_html.append({
            "palabra": palabra, "esperado": " ".join(ref), "detectado": " ".join(fon),
            "confianza": round(conf, 3), "duracion": seg["duracion"],
            "severidad": herramientas.severidad_pcc(cl["pcc"]),
            "valida": cl["valida"], "motivo_no_valida": cl["motivo_no_valida"],
            "peaks": _peaks(wav), "segmentos": seg["segmentos"],
            "audio_b64": _audio_b64(w), "eventos": cl["eventos"], "pcc": cl["pcc"],
        })
        palabras_informe.append({"palabra": palabra, "esperado": " ".join(ref),
                                 "detectado": " ".join(fon), "confianza": round(conf, 3),
                                 "reintentada": False, "pcc": cl["pcc"], "eventos": cl["eventos"],
                                 "valida": cl["valida"], "motivo_no_valida": cl["motivo_no_valida"]})

    resumen = herramientas.evaluar_sesion(palabras_informe, edad)
    return {"sesion": ses_id, "edad": edad, "resumen": resumen, "palabras": palabras_html}


def _esta_fresco(salida, ses_id):
    """True si el HTML ya existe y es más nuevo que los wav y el JS/CSS del editor."""
    if not os.path.exists(salida):
        return False
    entradas = glob.glob(os.path.join(DIR_SESIONES, ses_id, "*.wav"))
    entradas += [os.path.join(DIR_STATIC, "editor.js"), os.path.join(DIR_STATIC, "editor.css")]
    m_out = os.path.getmtime(salida)
    return all(os.path.getmtime(e) <= m_out for e in entradas if os.path.exists(e))


def generar_html(ses_id, salida=None, api_base="", edad=None, forzar=False):
    salida = salida or os.path.join(DIR_RESULTS, f"editor_{ses_id}.html")
    if not forzar and _esta_fresco(salida, ses_id):
        return salida   # caché: evita recargar el modelo y re-reconocer 32 audios
    datos = construir_datos_sesion(ses_id, edad=edad)
    css = open(os.path.join(DIR_STATIC, "editor.css"), encoding="utf-8").read()
    js = open(os.path.join(DIR_STATIC, "editor.js"), encoding="utf-8").read()
    payload = json.dumps(datos, ensure_ascii=False)
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revisión — {ses_id}</title><style>{css}</style></head>
<body>
<div id="app"></div>
<script>window.DATOS = {payload}; window.API_BASE = {json.dumps(api_base)};</script>
<script>{js}</script>
</body></html>"""
    salida = salida or os.path.join(DIR_RESULTS, f"editor_{ses_id}.html")
    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        f.write(html)
    return salida


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ses = sys.argv[1] if len(sys.argv) > 1 else None
    if ses is None:
        carpetas = [d for d in glob.glob(os.path.join(DIR_SESIONES, "*")) if os.path.isdir(d)]
        if not carpetas:
            print("No hay sesiones en data/raw/sesiones/."); sys.exit(1)
        ses = os.path.basename(max(carpetas, key=os.path.getmtime))
    out = generar_html(ses)
    print(f"Editor HTML: {os.path.relpath(out, RAIZ)}  (ábrelo en el navegador)")
