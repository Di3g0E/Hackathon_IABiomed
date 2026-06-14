"""
Motor clínico: clasifica los 8 procesos fonológicos del documento y calcula el riesgo.

MODO CLÍNICO (a diferencia del fold de T1 para adultos): conserva las distinciones
necesarias para el cribado infantil —vibrante simple ɾ vs múltiple r (para 'errores
en rr') y las vocales (para 'simplificación de diptongos')— y solo pliega los ejes
puramente dialectales, que NO son ninguno de los 8 errores (seseo θ→s, yeísmo ʝ→ʎ).

Los 8 errores (slug):
  reduccion_grupos · sustitucion_r_l · errores_rr · omision_silabas · oclusivizacion ·
  simplificacion_diptongos · omision_consonantes_finales · asimilaciones   (+ 'otro')
"""
from __future__ import annotations

import unicodedata

from pipeline.alineamiento import alinear
from pipeline.fonemas_canonicos import REF
from pipeline.normas import cuenta_para_riesgo, ERRORES

VOC = set("aeiou")
OCLUSIVAS = set("pbtdkg")
FRIC_AFRIC = {"f", "s", "x", "tʃ"}
CONS = OCLUSIVAS | FRIC_AFRIC | {"m", "n", "ɲ", "l", "ʎ", "ɾ", "r"}

# Plegado CLÍNICO: conserva ɾ/r y vocales; pliega solo ejes dialectales y alófonos.
FOLD = {
    "β": "b", "ð": "d", "ɣ": "g", "ɡ": "g", "ŋ": "n", "ɱ": "m",
    "ɹ": "ɾ", "ʁ": "ɾ", "ʀ": "r",            # róticas extranjeras -> tap por defecto
    "θ": "s", "ʝ": "ʎ", "ɟ": "ʎ", "ʄ": "ʎ",   # seseo / yeísmo (no son errores objetivo)
    "j": "i", "w": "u",
    "ɔ": "o", "ɛ": "e", "ɪ": "i", "ɨ": "i", "ʊ": "u",
    "æ": "a", "ə": "e", "ɐ": "a", "ʌ": "a", "y": "i", "ʏ": "i",
    "c": "k", "q": "k", "χ": "x", "ʃ": "tʃ", "ʧ": "tʃ",
}
INVENTARIO = VOC | CONS
_ALIAS = {"nino": "niño"}


def _norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t.strip().lower())
                if unicodedata.category(c) != "Mn")
    if not t:
        return None
    if "tʃ" in t:
        return "tʃ"
    base = FOLD.get(t[0] if len(t) > 1 else t, t[0] if len(t) > 1 else t)
    return base if base in INVENTARIO else "X"


def normaliza_clinico(tokens):
    return [n for n in (_norm(t) for t in tokens) if n is not None]


def ref_clinico(palabra):
    clave = palabra if palabra in REF else _ALIAS.get(
        "".join(c for c in palabra if c.isascii() and c.isalpha()), palabra)
    return normaliza_clinico(REF[clave][0].split())


def _clasifica_omision(a, idx, ref, n):
    vec_voc = (idx > 0 and ref[idx - 1] in VOC) or (idx < n - 1 and ref[idx + 1] in VOC)
    vec_con = (idx > 0 and ref[idx - 1] in CONS) or (idx < n - 1 and ref[idx + 1] in CONS)
    if a in VOC and vec_voc:
        return {"tipo": "simplificacion_diptongos", "detalle": f"omite {a} del diptongo"}
    if a in CONS and vec_con:
        return {"tipo": "reduccion_grupos", "detalle": f"omite {a} del grupo"}
    if a in CONS and idx == n - 1:
        return {"tipo": "omision_consonantes_finales", "detalle": f"omite final {a}"}
    if a == "r":
        return {"tipo": "errores_rr", "detalle": "omite rr"}
    return {"tipo": "otro", "detalle": f"omite {a}"}


def _clasifica_sustitucion(a, b, idx, ref, n):
    if a == "r":
        return {"tipo": "sustitucion_r_l" if b == "l" else "errores_rr",
                "detalle": f"rr→{b}"}
    if a == "ɾ" and b == "l":
        return {"tipo": "sustitucion_r_l", "detalle": "ɾ→l"}
    if a in FRIC_AFRIC and b in OCLUSIVAS:
        return {"tipo": "oclusivizacion", "detalle": f"{a}→{b}"}
    if (idx > 0 and b == ref[idx - 1]) or (idx < n - 1 and b == ref[idx + 1]):
        return {"tipo": "asimilaciones", "detalle": f"{a}→{b} (asimila al vecino)"}
    return {"tipo": "otro", "detalle": f"{a}→{b}"}


# --- Validez de la producción (guardián anti falso-correcto) ---
# Si el niño dice OTRA COSA (palabra mucho más larga o que no se parece a la esperada),
# la producción NO es evaluable: ni correcta ni error -> re-elicitar ("a repetir").
# Calibrado con las 32 palabras adultas correctas: máx. observado = 1 inserción
# (ratio 0.25×n_ref) y cobertura mínima 0.40 -> umbrales con margen.
INSERCIONES_TOL = 2          # inserciones absolutas siempre toleradas (ruido ASR)
INSERCIONES_RATIO_MAX = 0.5  # ... o hasta 0.5×n_ref si la palabra es larga
COBERTURA_MIN = 1 / 3        # mínimo de fonemas de la referencia presentes


def evaluar_validez(res, ref=None, hyp=None):
    """(valida, motivo) a partir del Resultado de alinear(). Con ref/hyp distingue el
    caso 'palabra dicha más de una vez' (la producción EMPIEZA por la palabra completa)."""
    n = max(1, res.n_ref)
    if res.inserciones > max(INSERCIONES_TOL, INSERCIONES_RATIO_MAX * n):
        if ref and hyp and list(hyp[:len(ref)]) == list(ref):
            return False, ("parece que la palabra se ha dicho más de una vez "
                           "(hay que decirla UNA sola vez)")
        return False, "se ha dicho algo más largo o distinto a la palabra esperada"
    if res.aciertos / n < COBERTURA_MIN:
        return False, "lo dicho no se parece a la palabra esperada (o no se oyó)"
    return True, None


def clasificar_errores(ref, hyp):
    """Devuelve {'pcc', 'eventos', 'valida', 'motivo_no_valida', 'inserciones', 'aciertos', 'n_ref'}."""
    res = alinear(ref, hyp)
    valida, motivo = evaluar_validez(res, ref, hyp)
    items, i = [], 0
    for t, a, b in res.ops:
        if t == "insercion":
            items.append((t, a, b, None))
        else:
            items.append((t, a, b, i)); i += 1
    n = len(ref)
    cons_total = sum(1 for p in ref if p in CONS)
    cons_ok = sum(1 for t, a, b, idx in items if t == "acierto" and a in CONS)
    pcc = 100.0 * cons_ok / cons_total if cons_total else 100.0

    eventos, k = [], 0
    while k < len(items):
        t, a, b, idx = items[k]
        if t == "acierto":
            k += 1; continue
        if t == "omision":
            run = []
            while k < len(items) and items[k][0] == "omision":
                run.append(items[k]); k += 1
            if len(run) >= 2 and any(x[1] in VOC for x in run):
                eventos.append({"tipo": "omision_silabas",
                                "detalle": "omite sílaba " + "".join(x[1] for x in run)})
            else:
                for _, aa, _b, ii in run:
                    eventos.append(_clasifica_omision(aa, ii, ref, n))
            continue
        if t == "sustitucion":
            eventos.append(_clasifica_sustitucion(a, b, idx, ref, n))
        elif t == "insercion":
            eventos.append({"tipo": "otro", "detalle": f"inserción {b}"})
        k += 1
    return {"pcc": round(pcc, 1), "eventos": eventos, "valida": valida,
            "motivo_no_valida": motivo, "inserciones": res.inserciones,
            "aciertos": res.aciertos, "n_ref": res.n_ref}


def anota_palabra(p, umbral_confianza=0.50):
    """Marca cada palabra como 'fiable' (confianza suficiente), 'valida' (la producción
    se corresponde con la palabra esperada) y 'correcta'. Una palabra 'reintentada' SE
    CONTABILIZA aunque su confianza siga baja, pero una producción NO VÁLIDA (dijo otra
    cosa) nunca puntúa: ni correcta ni error -> a repetir."""
    clinicos = [e for e in p["eventos"] if e["tipo"] in ERRORES]
    p["fiable"] = p.get("confianza", 1.0) >= umbral_confianza
    p["valida"] = p.get("valida", True)        # informes antiguos: sin campo = válida
    contabiliza = (p["fiable"] or p.get("reintentada", False)) and p["valida"]
    p["correcta"] = contabiliza and len(clinicos) == 0
    return p


def evaluar_riesgo(palabras, edad, tabla_normas, umbral_confianza=0.50,
                   frac_no_fiable_alta=0.40):
    """Resumen de riesgo. Solo se cuentan errores clínicos en palabras FIABLES y
    VÁLIDAS; las demás se marcan para REPETIR (no se puntúan como errores)."""
    conteo = {slug: 0 for slug in ERRORES}
    otras = 0
    n_alerta = 0
    correctas, no_fiables, no_validas = [], [], []
    for p in palabras:
        anota_palabra(p, umbral_confianza)
        # producción no válida (dijo otra cosa): nunca puntúa, siempre a repetir
        if not p["valida"]:
            no_validas.append(p.get("palabra", "?"))
            no_fiables.append(p.get("palabra", "?")); continue
        # una palabra reintentada se cuenta aunque siga con baja confianza
        if not (p["fiable"] or p.get("reintentada", False)):
            no_fiables.append(p.get("palabra", "?")); continue
        if p["correcta"]:
            correctas.append(p.get("palabra", "?"))
        for ev in p["eventos"]:
            if ev["tipo"] in ERRORES:
                conteo[ev["tipo"]] += 1
                if cuenta_para_riesgo(tabla_normas, ev["tipo"], edad):
                    n_alerta += 1
            else:
                otras += 1
    intel = sum(p["confianza"] for p in palabras) / len(palabras) if palabras else 0.0
    frac_nf = len(no_fiables) / len(palabras) if palabras else 0.0
    baja_intel = frac_nf >= frac_no_fiable_alta
    if n_alerta > 5 or baja_intel:
        riesgo = "alto"
    elif n_alerta >= 3:
        riesgo = "medio"
    else:
        riesgo = "bajo"
    recomendacion = {
        "bajo": "Desarrollo fonológico compatible con la edad.",
        "medio": "Persistencia de algún proceso fonológico; recomendable seguimiento.",
        "alto": "Recomendable valoración logopédica.",
    }[riesgo]
    if baja_intel:
        recomendacion += (f" (Baja fiabilidad: {len(no_fiables)} palabras poco claras; "
                          "conviene repetir la prueba.)")
    return {
        "edad": edad, "riesgo": riesgo, "recomendacion": recomendacion,
        "n_errores_impropios": n_alerta,
        "palabras_correctas": len(correctas),
        "palabras_a_repetir": no_fiables,
        "palabras_no_validas": no_validas,
        "errores_por_tipo": {ERRORES[s]: c for s, c in conteo.items() if c},
        "otras_discrepancias_no_objetivo": otras,
        "inteligibilidad_media": round(intel, 3),
        "baja_inteligibilidad": baja_intel,
        "_nota": "Cribado, NO diagnóstico. Cuenta solo errores clínicos impropios para la "
                 "edad en palabras fiables y VÁLIDAS (si se dice otra cosa distinta a la "
                 "palabra esperada, va a 'a repetir', ni acierto ni error). "
                 "'otras_discrepancias' = no objetivo (ruido/dialecto). Apoyo a profesional.",
    }