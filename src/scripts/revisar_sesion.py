"""
Revisor de sesión para el usuario MÉDICO.

Genera un informe HTML con, por cada palabra grabada:
  - reproductor de audio (escuchar la grabación),
  - gráfica de la ONDA con cada fonema situado en el TIEMPO (perfil temporal),
  - tabla de tiempos por fonema,
  - fonemas esperados vs detectados, confianza y procesos detectados.
Permite al profesional VER y ESCUCHAR. Para EDITAR los parámetros: corregir el campo
'detectado' en el informe JSON y re-puntuar con reanalizar.py.

Ejecutar:  uv run python src/scripts/revisar_sesion.py [sesion]
           (sesion = carpeta en data/raw/sesiones/, p.ej. diego_6; por defecto la última)
"""
from __future__ import annotations

import os
import sys
import glob
import html

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import librosa
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
RAIZ = os.path.dirname(SRC)

from pipeline.reconocedor import W2V
from pipeline.clinico import normaliza_clinico, ref_clinico, clasificar_errores, evaluar_riesgo
from pipeline.normas import cargar as cargar_normas, ERRORES

DIR_SES = os.path.join(RAIZ, "data", "raw", "sesiones")
DIR_RES = os.path.join(RAIZ, "results")
SR = 16_000


def figura(word, wav, segs, ruta_png):
    t = np.arange(len(wav)) / SR
    fig, ax = plt.subplots(figsize=(9, 2.8))
    ax.plot(t, wav, color="#444", lw=0.6)
    ymax = max(0.01, float(np.max(np.abs(wav))))
    colores = ["#cfe8ff", "#ffe7cf"]
    for idx, s in enumerate(segs):
        ax.axvspan(s["t_ini"], s["t_fin"], color=colores[idx % 2], alpha=0.6)
        ax.text((s["t_ini"] + s["t_fin"]) / 2, ymax * 0.82, s["label"],
                ha="center", fontsize=12, fontweight="bold", color="#c0392b")
    ax.set_xlim(0, t[-1] if len(t) else 1); ax.set_ylim(-ymax * 1.1, ymax * 1.1)
    ax.set_xlabel("tiempo (s)"); ax.set_yticks([]); ax.set_title(word, fontsize=11)
    fig.tight_layout(); fig.savefig(ruta_png, dpi=105); plt.close(fig)


def fmt_eventos(eventos, valida=True, motivo=None):
    if not valida:
        return (f'<span style="color:#b45309">⚠ producción no válida '
                f'({html.escape(motivo or "")}) — a repetir, no puntúa</span>')
    clin = [e for e in eventos if e["tipo"] in ERRORES]
    if not clin:
        return '<span style="color:#27ae60">✓ correcta (sin procesos clínicos)</span>'
    return "<br>".join(f'<span style="color:#c0392b">• {ERRORES[e["tipo"]]}: '
                       f'{html.escape(e["detalle"])}</span>' for e in clin)


def main():
    ses = sys.argv[1] if len(sys.argv) > 1 else None
    if ses is None:
        carpetas = [d for d in glob.glob(os.path.join(DIR_SES, "*")) if os.path.isdir(d)]
        if not carpetas:
            print("No hay sesiones en data/raw/sesiones/. Graba con app.py primero."); return
        ses = os.path.basename(max(carpetas, key=os.path.getmtime))
    dir_ses = os.path.join(DIR_SES, ses)
    wavs = sorted(glob.glob(os.path.join(dir_ses, "*.wav")))
    if not wavs:
        print(f"Sin audios en {dir_ses}"); return
    try:
        edad = int(ses.rsplit("_", 1)[-1])
    except ValueError:
        edad = 5
    print(f"Sesión '{ses}' (edad {edad}) — {len(wavs)} palabras. Cargando modelo...")
    w2v = W2V()
    tabla = cargar_normas(RAIZ)

    dir_png = os.path.join(DIR_RES, f"revision_{ses}")
    os.makedirs(dir_png, exist_ok=True)
    palabras, bloques = [], []
    for w in wavs:
        word = os.path.splitext(os.path.basename(w))[0]
        wav, _ = librosa.load(w, sr=SR, mono=True)
        tokens, conf = w2v.reconoce_conf(wav)
        segs_raw, _dur = w2v.reconoce_alineado(wav)
        segs = []
        for s in segs_raw:
            nz = normaliza_clinico([s["tok"]])
            if nz:
                segs.append({"label": nz[0], "t_ini": s["t_ini"], "t_fin": s["t_fin"],
                             "conf": s["conf"]})
        ref, hyp = ref_clinico(word), normaliza_clinico(tokens)
        cl = clasificar_errores(ref, hyp)
        palabras.append({"palabra": word, "esperado": " ".join(ref), "detectado": " ".join(hyp),
                         "confianza": round(conf, 3), "pcc": cl["pcc"], "eventos": cl["eventos"],
                         "valida": cl["valida"], "motivo_no_valida": cl["motivo_no_valida"]})

        png = os.path.join(dir_png, f"{word}.png")
        figura(word, wav, segs, png)
        rel_png = f"revision_{ses}/{word}.png"
        rel_wav = os.path.relpath(w, DIR_RES).replace("\\", "/")
        filas = "".join(f"<tr><td>{html.escape(s['label'])}</td><td>{s['t_ini']:.2f}</td>"
                        f"<td>{s['t_fin']:.2f}</td><td>{s['conf']:.0%}</td></tr>" for s in segs)
        bloques.append(f"""
        <div class="word">
          <h3>{html.escape(word)} <small>(confianza {conf:.0%})</small></h3>
          <p>Esperado: <code>{html.escape(' '.join(ref))}</code> &nbsp;|&nbsp;
             Detectado: <code>{html.escape(' '.join(hyp))}</code></p>
          <audio controls src="{rel_wav}"></audio>
          <img src="{rel_png}" alt="{word}">
          <p>{fmt_eventos(cl['eventos'], cl['valida'], cl['motivo_no_valida'])}</p>
          <details><summary>tiempos por fonema</summary>
          <table><tr><th>fonema</th><th>t_ini (s)</th><th>t_fin (s)</th><th>conf</th></tr>
          {filas}</table></details>
        </div>""")

    resumen = evaluar_riesgo(palabras, edad, tabla)
    emoji = {"bajo": "🟢", "medio": "🟡", "alto": "🔴"}[resumen["riesgo"]]
    cabecera = f"""
    <div class="resumen">
      <h2>{emoji} Riesgo {resumen['riesgo'].upper()} — {html.escape(resumen['recomendacion'])}</h2>
      <p>Edad {edad} · errores impropios: {resumen['n_errores_impropios']} ·
         correctas: {resumen['palabras_correctas']} ·
         a repetir (baja confianza): {len(resumen['palabras_a_repetir'])} ·
         inteligibilidad media: {resumen['inteligibilidad_media']:.0%}</p>
      <p><small>Cribado orientativo, NO diagnóstico. Para corregir parámetros: edita el campo
         'detectado' en el informe JSON y re-puntúa con reanalizar.py.</small></p>
    </div>"""

    estilo = ("body{font-family:system-ui,Arial;max-width:920px;margin:auto;padding:1em;color:#222}"
              ".word{border:1px solid #ddd;border-radius:8px;padding:.8em 1em;margin:1em 0}"
              "img{max-width:100%}audio{width:100%;margin:.4em 0}"
              "table{border-collapse:collapse;font-size:.85em}td,th{border:1px solid #ccc;padding:2px 8px}"
              "code{background:#f4f4f4;padding:1px 4px;border-radius:3px}"
              ".resumen{background:#f7f9fb;border:1px solid #cdd;border-radius:8px;padding:1em}")
    doc = (f"<!doctype html><html lang=es><head><meta charset=utf-8>"
           f"<title>Revisión {html.escape(ses)}</title><style>{estilo}</style></head><body>"
           f"<h1>Revisión fonológica — {html.escape(ses)}</h1>{cabecera}{''.join(bloques)}</body></html>")
    salida = os.path.join(DIR_RES, f"revision_{ses}.html")
    with open(salida, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"\nRiesgo {resumen['riesgo'].upper()} | correctas {resumen['palabras_correctas']} | "
          f"a repetir {len(resumen['palabras_a_repetir'])} | impropios {resumen['n_errores_impropios']}")
    print(f"Informe HTML: {os.path.relpath(salida, RAIZ)}  (ábrelo en el navegador)")


if __name__ == "__main__":
    main()