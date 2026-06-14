"""Genera una vista previa del informe clínico HTML (plantilla Habli) con datos de ejemplo.

Ejecutar:  uv run python src/scripts/preview_informe_clinico.py
Salida:    docs/preview_informe_clinico.html  (abrir en navegador; Ctrl+P para PDF)
"""
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("src/app/templates"))
tpl = env.get_template("informe_clinico.html")

datos = {
    "alias": "diego_6", "edad": 5, "fecha": "12/06/2026", "anio": "2026",
    "logo_src": "../src/app/static/brand/habli-logo.png",
    "screening": {
        "riesgo_preliminar": "medio",
        "banderas": ["vocabulario reducido", "frases de 2 palabras"],
        "factores_equidad": ["entorno bilingüe (español/catalán)", "otitis de repetición"],
    },
    "pruebas": [
        {
            "n_prueba": 1, "ts": "2026-05-02T10:30:00",
            "resumen": {
                "riesgo": "medio",
                "recomendacion": "Se recomienda valoración por logopeda en las próximas semanas.",
                "n_errores_impropios": 7, "palabras_correctas": 21,
                "inteligibilidad_media": 0.78,
                "errores_por_tipo": {"fronting": 4, "rotacismo": 2,
                                     "reducción de grupo consonántico": 3},
            },
            "analisis": {
                "pcc_medio": 71.4, "severidad_pcc": "leve-moderada",
                "procesos_atipicos": ["posteriorización"],
                "pcc_por_grupo": [
                    {"proceso": "fronting", "pcc": 64.0, "severidad": "moderada", "n_palabras": 6},
                    {"proceso": "rotacismo", "pcc": 70.5, "severidad": "leve-moderada", "n_palabras": 4},
                ],
                "severidad_por_palabra": [
                    {"palabra": "tren", "pcc": 50.0, "severidad": "moderada-severa"},
                    {"palabra": "globo", "pcc": 60.0, "severidad": "moderada"},
                    {"palabra": "rana", "pcc": 66.7, "severidad": "moderada"},
                ],
            },
            "avisos": ["El reconocedor aún no está adaptado del todo a voz infantil; "
                       "revisar transcripciones."],
        },
        {
            "n_prueba": 2, "ts": "2026-06-06T17:05:00",
            "resumen": {
                "riesgo": "bajo",
                "recomendacion": "Mantener ejercicios de estimulación y reevaluar en 3 meses.",
                "n_errores_impropios": 3, "palabras_correctas": 27,
                "inteligibilidad_media": 0.89,
                "errores_por_tipo": {"rotacismo": 2, "reducción de grupo consonántico": 1},
            },
            "analisis": {"pcc_medio": 84.2, "severidad_pcc": "leve"},
            "persistencia": {"procesos": {
                "persistentes": ["rotacismo"], "nuevos": [],
                "resueltos": ["fronting", "posteriorización"]}},
            "repeticion": {"procesos_corregidos": ["reducción de grupo consonántico"],
                           "procesos_confirmados": ["rotacismo"]},
        },
    ],
    "evolucion": {
        "tiene_evolucion": True,
        "delta": {"riesgo": "medio → bajo", "n_errores_impropios": -4,
                  "palabras_correctas": 6, "inteligibilidad_media": "+11 pts",
                  "pcc_medio": "+12.8"},
        "dias_entre_pruebas": 35, "n_ejercicios_entre_pruebas": 12,
        "dias_ultimo_ejercicio_a_prueba": 2,
    },
    "ejercicios": {
        "mensaje": "Plan de estimulación centrado en el rotacismo y los grupos "
                   "consonánticos, en formato de juego diario de 10 minutos.",
        "ejercicios": [
            {"titulo": "El motorito", "proceso": "rotacismo",
             "actividad": "Imitar el sonido de una moto (rrr) delante del espejo, 5 "
                          "repeticiones, y luego palabras con erre fuerte: rana, rueda, torre."},
            {"titulo": "Palabras que crecen", "proceso": "grupos consonánticos",
             "actividad": "Decir la palabra por partes y unirla: t-ren, tren; g-lobo, globo. "
                          "Celebrar el intento aunque no salga perfecto."},
        ],
        "nota": "Los ejercicios son orientativos; el/la logopeda puede ajustarlos a la "
                "evolución del niño.",
    },
}

html = tpl.render(**datos)
with open("docs/preview_informe_clinico.html", "w", encoding="utf-8") as f:
    f.write(html)
print("OK -> docs/preview_informe_clinico.html")
