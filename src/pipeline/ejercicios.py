"""
Ejercicios de ESTIMULACIÓN del habla (NO terapia) + plan de seguimiento por riesgo.

IMPORTANTE (encuadre): son ejercicios de estimulación para casa, como juego y sin presión.
NO son una terapia ni responden a un diagnóstico — eso corresponde a un especialista.

Catálogo en 3 NIVELES (validado con criterio logopédico, edades 3-6):
  N1 estimulación general (3-6): lectura compartida dialógica, descripción de imágenes,
     juegos de vocabulario.
  N2 conciencia fonológica: contar sílabas (4-6), rimas (4-6), sonido inicial (5-6).
  N3 personalizado por error detectado: SOLO procesos no-normales para la edad según
     data/normas_edad.csv (no se proponen ejercicios de procesos evolutivamente normales).

Mapeo riesgo→niveles: bajo = 1×N1 · medio = N1+N2 (a los 3 años: 2×N1) · alto = N1+N2(si
edad≥4)+N3. El PLAN DE SEGUIMIENTO global (riesgo×edad → días hasta repetir + nº ejercicios)
lo configura el especialista en data/plan_seguimiento.csv (editable por API).

Todo es editable por la logopeda: data/ejercicios.csv y data/plan_seguimiento.csv.

Ejecutar:  uv run python src/pipeline/ejercicios.py   ->  (re)genera ambos CSV + demo
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/ en path

from pipeline.fonemas_canonicos import REF
from pipeline.normas import ERRORES, cargar as cargar_normas, nivel as nivel_norma

DISCLAIMER = ("Ejercicios de estimulación del habla, como juego y sin presión. NO son una "
              "terapia ni responden a un diagnóstico: esa valoración corresponde a un "
              "especialista. Cribado orientativo.")

# ---------------------------------------------------------------- catálogo (3 niveles)
# Nivel 1 — estimulación general (todos los niños, 3-6)
_N1 = [
    {"titulo": "Lectura compartida", "prioridad": 1, "edad_min": 3, "edad_max": 6,
     "actividad": "Leed un cuento juntos 10 minutos al día: el adulto lee, pregunta "
                  "('¿qué pasará ahora?', '¿quién es este?') y deja que el niño complete "
                  "frases y comente lo que ve.",
     "objetivo": "Estimular vocabulario y lenguaje oral con lectura dialógica."},
    {"titulo": "Describir imágenes", "prioridad": 2, "edad_min": 3, "edad_max": 6,
     "actividad": "Mirad juntos una lámina o foto y preguntad: ¿qué ves?, ¿qué hace?, "
                  "¿de qué color es?, ¿dónde está? Celebrad cada respuesta y ampliadla "
                  "('sí, un perro GRANDE que corre').",
     "objetivo": "Ampliar vocabulario y construcción de frases."},
    {"titulo": "Juegos de vocabulario", "prioridad": 3, "edad_min": 3, "edad_max": 6,
     "actividad": "Jugad a decir nombres por categorías: animales, colores, transportes, "
                  "comidas… ('¿cuántos animales sabes?'). Vale con dibujos o por la calle.",
     "objetivo": "Organizar y ampliar el vocabulario por categorías."},
]
# Nivel 2 — conciencia fonológica (edades según desarrollo)
_N2 = [
    {"titulo": "Palmas a las sílabas", "prioridad": 1, "edad_min": 4, "edad_max": 6,
     "actividad": "Dad una palmada por cada trocito de la palabra: 'pa-lo-ma' (3 palmas). "
                  "Empezad con palabras cortas y subid a largas (ma-ri-po-sa).",
     "objetivo": "Conciencia silábica (separar las palabras en trozos)."},
    {"titulo": "Buscar rimas", "prioridad": 2, "edad_min": 4, "edad_max": 6,
     "actividad": "Decid una palabra y buscad otra que suene igual al final: gato-pato, "
                  "ratón-botón. Que adivine cuál rima entre dos opciones.",
     "objetivo": "Conciencia de rima (sonidos finales)."},
    {"titulo": "El sonido inicial", "prioridad": 3, "edad_min": 5, "edad_max": 6,
     "actividad": "Jugad a buscar palabras que empiecen por un sonido: 'mmm' → mesa, mamá, "
                  "mono. Primero con su nombre y los de la familia.",
     "objetivo": "Conciencia fonémica (detectar el sonido inicial)."},
]
# Nivel 3 — personalizado por proceso detectado (edades mínimas clínicamente razonables)
_N3 = {
    "reduccion_grupos": [
        {"titulo": "El tren de sonidos", "prioridad": 1, "edad_min": 4, "edad_max": 6,
         "actividad": "Decid juntos palabras con dos consonantes seguidas (tren, plato, globo) "
                      "muy despacio, alargando el primer sonido: 'trrr-en'. Que note los dos sonidos.",
         "objetivo": "Producir grupos consonánticos sin comerse una consonante."},
    ],
    "sustitucion_r_l": [
        {"titulo": "El coche y la lámpara", "prioridad": 1, "edad_min": 4, "edad_max": 6,
         "actividad": "Frente a un espejo, jugad a la moto 'rrr' (lengua arriba vibrando) y a la "
                      "'lll' (lengua tocando los dientes). Que vea y sienta la diferencia.",
         "objetivo": "Diferenciar y articular /r/ frente a /l/."},
    ],
    "errores_rr": [
        {"titulo": "La moto que arranca", "prioridad": 1, "edad_min": 5, "edad_max": 6,
         "actividad": "Imitad motores y gatitos ('rrr', 'brrrum') haciendo vibrar la punta de la "
                      "lengua detrás de los dientes de arriba. Empezad con 'tr', 'dr' (tren, dragón).",
         "objetivo": "Estimular la vibrante múltiple /rr/."},
    ],
    "omision_silabas": [
        {"titulo": "Palabras enteras con palmas", "prioridad": 1, "edad_min": 3, "edad_max": 6,
         "actividad": "Dad una palmada por cada trozo de la palabra y decidla entera: "
                      "'pe-lo-ta… ¡pelota!'. Usad palabras largas (mariposa, elefante).",
         "objetivo": "Mantener todas las sílabas de la palabra."},
    ],
    "oclusivizacion": [
        {"titulo": "La serpiente y el viento", "prioridad": 1, "edad_min": 4, "edad_max": 6,
         "actividad": "Jugad a soplar sonidos largos: la serpiente 'sssss', el viento 'fffff'. "
                      "Que el aire salga continuo y no de golpe (no 'tttt').",
         "objetivo": "Mantener los sonidos de soplo (f, s) sin convertirlos en golpes."},
        {"titulo": "Juegos de soplo", "prioridad": 2, "edad_min": 4, "edad_max": 6,
         "actividad": "Soplar matasuegras, pompas o una pelotita de papel sobre la mesa.",
         "objetivo": "Control del soplo para los sonidos continuos."},
    ],
    "simplificacion_diptongos": [
        {"titulo": "Las vocales que se dan la mano", "prioridad": 1, "edad_min": 4, "edad_max": 6,
         "actividad": "Cantad alargando las dos vocales juntas: 'pe-i-ne', 'a-u-to'. "
                      "Que se oigan las dos.",
         "objetivo": "Producir los diptongos completos."},
    ],
    "omision_consonantes_finales": [
        {"titulo": "El sonido que se escapa", "prioridad": 1, "edad_min": 4, "edad_max": 6,
         "actividad": "Exagerad el último sonido de la palabra: 'pa-N', 'so-L', 'relo-J'. "
                      "Jugad al eco repitiendo solo el final.",
         "objetivo": "Mantener la consonante final de la palabra."},
    ],
    "asimilaciones": [
        {"titulo": "Sonidos diferentes en una palabra", "prioridad": 1, "edad_min": 4, "edad_max": 6,
         "actividad": "Decid despacio palabras con dos sonidos distintos ('pato' no 'tato', "
                      "'casa' no 'tata'). Marcad cada sonido con un gesto distinto.",
         "objetivo": "Evitar que un sonido contagie a otro dentro de la palabra."},
    ],
}

NOMBRE_A_SLUG = {nombre: slug for slug, nombre in ERRORES.items()}
CAMPOS = ["nivel", "proceso_slug", "nombre", "edad_min", "edad_max", "titulo",
          "actividad_familia", "objetivo", "prioridad"]


def _ruta(raiz):
    return os.path.join(raiz, "data", "ejercicios.csv")


def escribir_csv(raiz):
    filas = []
    for nivel, lista, slug, nombre in ((1, _N1, "general", "Estimulación general"),
                                       (2, _N2, "fonologica", "Conciencia fonológica")):
        for a in lista:
            filas.append({"nivel": nivel, "proceso_slug": slug, "nombre": nombre,
                          "edad_min": a["edad_min"], "edad_max": a["edad_max"],
                          "titulo": a["titulo"], "actividad_familia": a["actividad"],
                          "objetivo": a["objetivo"], "prioridad": a["prioridad"]})
    for slug, acts in _N3.items():
        for a in acts:
            filas.append({"nivel": 3, "proceso_slug": slug, "nombre": ERRORES[slug],
                          "edad_min": a["edad_min"], "edad_max": a["edad_max"],
                          "titulo": a["titulo"], "actividad_familia": a["actividad"],
                          "objetivo": a["objetivo"], "prioridad": a["prioridad"]})
    with open(_ruta(raiz), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader(); w.writerows(filas)
    return filas


def cargar(raiz):
    """Devuelve la lista de ejercicios (dicts con nivel/slug/edades). Crea el CSV si falta."""
    if not os.path.exists(_ruta(raiz)):
        escribir_csv(raiz)
    out = []
    with open(_ruta(raiz), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append({**r, "nivel": int(r["nivel"]), "edad_min": int(r["edad_min"]),
                        "edad_max": int(r["edad_max"]), "prioridad": int(r["prioridad"])})
    return out


def biblioteca(raiz, edad=None, riesgo=None):
    """Catálogo completo agrupado por nivel (pantalla 'todos los ejercicios' de la UI).
    Filtros opcionales: edad (3-6) y riesgo (limita a los niveles del mapeo)."""
    niveles_por_riesgo = {"bajo": {1}, "medio": {1, 2}, "alto": {1, 2, 3}}
    permitidos = niveles_por_riesgo.get(riesgo) if riesgo else {1, 2, 3}
    grupos = {1: [], 2: [], 3: []}
    for e in cargar(raiz):
        if e["nivel"] not in permitidos:
            continue
        if edad is not None and not (e["edad_min"] <= int(edad) <= e["edad_max"]):
            continue
        grupos[e["nivel"]].append(e)
    etiquetas = {1: "Nivel 1 — Estimulación general", 2: "Nivel 2 — Conciencia fonológica",
                 3: "Nivel 3 — Personalizados por sonido"}
    return {"nota": DISCLAIMER,
            "niveles": [{"nivel": n, "titulo": etiquetas[n], "ejercicios": grupos[n]}
                        for n in (1, 2, 3) if grupos[n]]}


# ---------------------------------------------------------------- plan de seguimiento
EDADES_PLAN = [3, 4, 5, 6]
_PLAN_DEFAULT = {"bajo": (180, 1), "medio": (42, 2), "alto": (21, 3)}  # (días, nº ejercicios)
CAMPOS_PLAN = ["riesgo", "edad", "dias", "n_ejercicios"]


def formatea_plazo(dias):
    """Expresa el plazo en la unidad mayor que dé un número entero."""
    dias = int(dias)
    if dias % 30 == 0:
        n = dias // 30
        return f"{n} mes" + ("es" if n != 1 else "")
    if dias % 7 == 0:
        n = dias // 7
        return f"{n} semana" + ("s" if n != 1 else "")
    return f"{dias} día" + ("s" if dias != 1 else "")


def _ruta_plan(raiz):
    return os.path.join(raiz, "data", "plan_seguimiento.csv")


def escribir_plan_csv(raiz):
    filas = [{"riesgo": r, "edad": e, "dias": d, "n_ejercicios": n}
             for r, (d, n) in _PLAN_DEFAULT.items() for e in EDADES_PLAN]
    with open(_ruta_plan(raiz), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_PLAN)
        w.writeheader(); w.writerows(filas)
    return filas


def cargar_plan(raiz):
    if not os.path.exists(_ruta_plan(raiz)):
        escribir_plan_csv(raiz)
    plan = {}
    with open(_ruta_plan(raiz), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            plan[(r["riesgo"], int(r["edad"]))] = {"dias": int(r["dias"]),
                                                   "n_ejercicios": int(r["n_ejercicios"])}
    return plan


def cargar_plan_filas(raiz):
    if not os.path.exists(_ruta_plan(raiz)):
        escribir_plan_csv(raiz)
    with open(_ruta_plan(raiz), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def guardar_plan_filas(raiz, filas):
    """MERGE: actualiza solo las celdas (riesgo, edad) dadas y conserva el resto."""
    actuales = {(r["riesgo"], str(r["edad"])): dict(r) for r in cargar_plan_filas(raiz)}
    for r in filas:
        clave = (r["riesgo"], str(r["edad"]))
        actuales[clave] = {k: r.get(k, actuales.get(clave, {}).get(k)) for k in CAMPOS_PLAN}
    orden = {"bajo": 0, "medio": 1, "alto": 2}
    final = sorted(actuales.values(), key=lambda x: (orden.get(x["riesgo"], 9), int(x["edad"])))
    with open(_ruta_plan(raiz), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_PLAN)
        w.writeheader()
        for r in final:
            w.writerow({k: r.get(k) for k in CAMPOS_PLAN})
    return cargar_plan_filas(raiz)


# ---------------------------------------------------------------- propuesta tras la prueba
GENERAL = {
    "bajo": "¡Enhorabuena! El desarrollo del habla es compatible con lo esperado para su edad. "
            "Para seguir estimulándole os proponemos un juego. Si queréis, podéis repetir la "
            "prueba en {plazo} para ver su evolución (es totalmente opcional).",
    "medio": "Algunos sonidos aún están madurando, algo frecuente a estas edades. Os proponemos "
             "estos ejercicios de estimulación, un ratito al día como juego, y repetir la prueba "
             "en {plazo}.",
    "alto": "Os proponemos practicar estos ejercicios a diario, como juego y sin presión, y "
            "repetir la prueba en {plazo}. Si el resultado se mantiene, conviene pedir cita con "
            "un especialista (logopeda).",
}


def _fecha_retest(hoy, dias):
    if not hoy:
        return None
    import datetime
    try:
        return (datetime.date.fromisoformat(hoy) + datetime.timedelta(days=dias)).isoformat()
    except Exception:
        return None


def _aplica_edad(e, edad):
    return e["edad_min"] <= edad <= e["edad_max"]


def proponer_ejercicios(resumen_riesgo, edad, raiz=None, hoy=None):
    """Propone ejercicios según el riesgo (mapeo por niveles) y el plan del especialista.

    bajo = 1×N1 · medio = N1+N2 (a los 3 años: 2×N1) · alto = N1+N2(si edad≥4)+N3.
    N3 SOLO para procesos detectados NO-normales para la edad (gating con normas_edad).
    Devuelve {nivel, mensaje, ejercicios, dias, plazo, fecha_retest, seguimiento_opcional, nota}.
    """
    edad = max(3, min(6, int(edad)))
    riesgo = resumen_riesgo.get("riesgo", "bajo")
    catalogo = cargar(raiz) if raiz else []
    plan = cargar_plan(raiz) if raiz else {}
    cfg = plan.get((riesgo, edad)) or {"dias": _PLAN_DEFAULT[riesgo][0],
                                       "n_ejercicios": _PLAN_DEFAULT[riesgo][1]}
    dias, n_total = cfg["dias"], cfg["n_ejercicios"]

    n1 = sorted([e for e in catalogo if e["nivel"] == 1 and _aplica_edad(e, edad)],
                key=lambda e: e["prioridad"])
    n2 = sorted([e for e in catalogo if e["nivel"] == 2 and _aplica_edad(e, edad)],
                key=lambda e: e["prioridad"])

    # N3: procesos detectados, ordenados por frecuencia, SOLO si no son normales para la edad
    tabla = cargar_normas(raiz) if raiz else {}
    detectados = resumen_riesgo.get("errores_por_tipo", {})
    slugs = [NOMBRE_A_SLUG.get(n, n) for n, _c in
             sorted(detectados.items(), key=lambda kv: kv[1], reverse=True)]
    n3 = []
    for slug in slugs:
        if tabla and nivel_norma(tabla, slug, edad) == "normal":
            continue                       # evolutivamente normal: no se ejercita
        cands = sorted([e for e in catalogo if e["nivel"] == 3 and e["proceso_slug"] == slug
                        and _aplica_edad(e, edad)], key=lambda e: e["prioridad"])
        n3.extend(cands[:1])

    # mapeo por riesgo, con tope ESTRICTO en n_total (lo fija el plan del especialista)
    seleccion = []
    if n1:
        seleccion.append(n1[0])
    if riesgo in ("medio", "alto"):
        if n2:
            seleccion.append(n2[0])
        elif len(n1) > 1:                  # a los 3 años no hay N2: segundo N1
            seleccion.append(n1[1])
    if riesgo == "alto":
        for e in n3:                       # personalizados, hasta llenar el cupo
            if len(seleccion) >= n_total:
                break
            seleccion.append(e)
    for extra in n1[1:] + n2[1:]:          # completar si faltan hasta n_total
        if len(seleccion) >= n_total:
            break
        if extra not in seleccion:
            seleccion.append(extra)
    seleccion = seleccion[:n_total]

    plazo = formatea_plazo(dias)
    return {
        "nivel": riesgo,
        "mensaje": GENERAL[riesgo].format(plazo=plazo),
        "ejercicios": [{"nivel": e["nivel"], "proceso": e["nombre"], "titulo": e["titulo"],
                        "actividad": e["actividad_familia"], "objetivo": e["objetivo"]}
                       for e in seleccion],
        "dias": dias, "plazo": plazo, "fecha_retest": _fecha_retest(hoy, dias),
        "seguimiento_opcional": riesgo == "bajo",
        "nota": DISCLAIMER,
    }


# ---------------------------------------------------------------- palabras por estructura
_VOC = set("aeiou")


def _nucleos(seq):
    """Número de núcleos silábicos (grupos de vocales adyacentes)."""
    n, en_voc = 0, False
    for t in seq:
        if t in _VOC:
            if not en_voc:
                n += 1
            en_voc = True
        else:
            en_voc = False
    return n


# procesos con estructura concreta verificable en una palabra (asimilaciones es universal)
PROCESOS_COBERTURA = ["reduccion_grupos", "sustitucion_r_l", "errores_rr", "omision_silabas",
                      "oclusivizacion", "simplificacion_diptongos", "omision_consonantes_finales"]


def seleccionar_palabras_prueba(n=15, rng=None):
    """Selección ALEATORIA de n palabras que CUBRE todos los procesos de error (al menos
    una palabra que ponga a prueba cada proceso). Cada llamada devuelve una lista distinta;
    el orden también es aleatorio. Pensada para la prueba corta (15 en vez de 32)."""
    import random
    rng = rng or random.Random()
    cobertura = {slug: palabras_para_proceso(slug) for slug in PROCESOS_COBERTURA}
    seleccion = []
    # 1) garantizar ≥1 palabra por proceso (procesos y candidatas en orden aleatorio)
    for slug in rng.sample(PROCESOS_COBERTURA, len(PROCESOS_COBERTURA)):
        cands = cobertura[slug]
        if cands and not any(w in seleccion for w in cands):
            seleccion.append(rng.choice(cands))
    # 2) reforzar con una 2ª palabra por proceso mientras quepan
    for slug in rng.sample(PROCESOS_COBERTURA, len(PROCESOS_COBERTURA)):
        if len(seleccion) >= n:
            break
        cubiertas = sum(1 for w in cobertura[slug] if w in seleccion)
        cands = [w for w in cobertura[slug] if w not in seleccion]
        if cubiertas < 2 and cands:
            seleccion.append(rng.choice(cands))
    # 3) rellenar hasta n con palabras aleatorias del resto del inventario
    resto = [w for w in REF if w not in seleccion]
    rng.shuffle(resto)
    seleccion.extend(resto[:max(0, n - len(seleccion))])
    seleccion = seleccion[:n]
    rng.shuffle(seleccion)
    return seleccion


def palabras_para_proceso(slug):
    """Palabras de las 32 que contienen la estructura que pone a prueba cada proceso
    (para la ronda extra: practicar lo mismo con palabras DISTINTAS)."""
    out = []
    for w, (fon, _n) in REF.items():
        s = fon.split()
        if slug == "errores_rr":
            ok = "r" in s
        elif slug == "sustitucion_r_l":
            ok = "ɾ" in s or "r" in s
        elif slug == "reduccion_grupos":
            ok = any(s[i] not in _VOC and s[i] not in ("l", "ɾ") and s[i + 1] in ("l", "ɾ")
                     for i in range(len(s) - 1))
        elif slug == "simplificacion_diptongos":
            ok = any(s[i] in _VOC and s[i + 1] in _VOC for i in range(len(s) - 1))
        elif slug == "omision_consonantes_finales":
            ok = s[-1] not in _VOC
        elif slug == "omision_silabas":
            ok = _nucleos(s) >= 3
        elif slug == "oclusivizacion":
            ok = any(t in ("f", "s", "x", "θ", "tʃ") for t in s)
        else:                               # asimilaciones u otros: cualquier palabra sirve
            ok = True
        if ok:
            out.append(w)
    return sorted(out)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    filas = escribir_csv(raiz)
    plan = escribir_plan_csv(raiz)
    print(f"Escrito data/ejercicios.csv ({len(filas)} ejercicios) y "
          f"data/plan_seguimiento.csv ({len(plan)} celdas).")
    print(f"Plazos: 180d→{formatea_plazo(180)} · 42d→{formatea_plazo(42)} · "
          f"21d→{formatea_plazo(21)} · 45d→{formatea_plazo(45)}")
    for riesgo, edad in (("bajo", 3), ("medio", 3), ("medio", 5), ("alto", 3), ("alto", 6)):
        demo = {"riesgo": riesgo, "errores_por_tipo": {"Errores en rr": 2,
                                                       "Reducción de grupos consonánticos": 1}}
        p = proponer_ejercicios(demo, edad, raiz=raiz)
        niveles = [e["nivel"] for e in p["ejercicios"]]
        print(f"  {riesgo:5s}/edad{edad}: {len(p['ejercicios'])} ejercicios niveles={niveles} "
              f"plazo={p['plazo']}")
    print("  rr a los 3 años NO debe aparecer (normal para la edad):",
          all(e['proceso'] != 'Errores en rr'
              for e in proponer_ejercicios({'riesgo': 'alto', 'errores_por_tipo':
                                            {'Errores en rr': 3}}, 3, raiz=raiz)['ejercicios']))
    print("  palabras_para_proceso('reduccion_grupos'):",
          palabras_para_proceso("reduccion_grupos"))
