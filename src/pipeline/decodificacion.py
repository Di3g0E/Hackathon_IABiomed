"""
Decodificación RESTRINGIDA + GOP para el cribado fonológico.

En vez de transcribir libre (argmax CTC abierto, ~18% PER de ruido), aprovechamos que YA
sabemos qué palabra se ha pedido: puntuamos la realización CANÓNICA y un conjunto acotado de
realizaciones clínicamente significativas (las que generan los 8 procesos) contra los logits
del modelo, y nos quedamos con la más probable. La detección del proceso sale de qué hipótesis
gana; el GOP (Goodness of Pronunciation) por fonema mide cómo de bien encaja cada sonido esperado.

Robustez dialectal: los logits (vocab espeak crudo) se COLAPSAN a las clases del inventario
clínico reutilizando el plegado de clinico (θ y s caen en la misma clase 's', etc.), así que
seseo/yeísmo no penalizan. Lo no-clínico (pad, símbolos fuera de inventario) se trata como blank.

Funciones núcleo (torch): construir_mapa · colapsa_logprobs · ctc_logprob (forward) · gop_fonemas.
Generación de hipótesis: genera_hipotesis (1 proceso aplicado en 1 posición = espacio acotado).
"""
from __future__ import annotations

import math

import torch

from pipeline.clinico import (CONS, FRIC_AFRIC, VOC, INVENTARIO,
                              normaliza_clinico, ref_clinico)

_NEG = -1e30
_CACHE_MAPA = {}


def construir_mapa(id2tok):
    """Devuelve (clases, idx, BLANK, clase_de_id). Cada vocab id -> índice de clase clínica
    (o BLANK si es pad/especial/fuera de inventario). Cacheado por id del dict."""
    clave = id(id2tok)
    if clave in _CACHE_MAPA:
        return _CACHE_MAPA[clave]
    clases = sorted(INVENTARIO)                 # fonemas del inventario clínico
    idx = {c: i for i, c in enumerate(clases)}
    BLANK = len(clases)                         # todo lo no-clínico cae aquí (se "salta")
    clase_de = {}
    for vid, tok in id2tok.items():
        nz = normaliza_clinico([tok])
        clase_de[vid] = idx[nz[0]] if (nz and nz[0] in idx) else BLANK
    # columnas (vocab ids) agrupadas por clase, para el logsumexp del colapso
    cols = [[] for _ in range(BLANK + 1)]
    for vid, c in clase_de.items():
        cols[c].append(vid)
    res = (clases, idx, BLANK, cols)
    _CACHE_MAPA[clave] = res
    return res


def colapsa_logprobs(logits, cols, BLANK):
    """logits (T×V) -> log-probs por clase clínica (T×(K+1)), agregando con logsumexp las
    columnas del vocab que caen en cada clase. La clase BLANK absorbe pad/especial/no-clínico."""
    logp = torch.log_softmax(logits, dim=-1)    # T×V
    T = logp.shape[0]
    out = torch.full((T, BLANK + 1), _NEG, dtype=logp.dtype, device=logp.device)
    for c, ids in enumerate(cols):
        if ids:
            out[:, c] = torch.logsumexp(logp[:, ids], dim=-1)
    return out


def ctc_logprob(LP, seq, BLANK):
    """Log-probabilidad CTC (forward, en log-espacio) de la secuencia de clases `seq`
    (sin blanks). LP = lista T×(K+1) de log-probs por clase (Python, no tensor)."""
    T = len(LP)
    if not seq:
        return sum(LP[t][BLANK] for t in range(T))   # solo blanks
    ext = [BLANK]                                     # b s0 b s1 ... b
    for s in seq:
        ext += [s, BLANK]
    S = len(ext)
    a = [_NEG] * S                                    # alpha en log
    a[0] = LP[0][BLANK]
    a[1] = LP[0][ext[1]]
    for t in range(1, T):
        prev = a
        a = [_NEG] * S
        row = LP[t]
        for s in range(S):
            v = prev[s]
            if s >= 1:
                v = _logaddexp(v, prev[s - 1])
            if s >= 2 and ext[s] != BLANK and ext[s] != ext[s - 2]:
                v = _logaddexp(v, prev[s - 2])
            a[s] = v + row[ext[s]]
    return _logaddexp(a[S - 1], a[S - 2])


def _logaddexp(x, y):
    if x <= _NEG:
        return y
    if y <= _NEG:
        return x
    m = x if x > y else y
    return m + math.log(math.exp(x - m) + math.exp(y - m))


def gop_fonemas(LP, seq):
    """GOP simple por fonema: log-posterior de cada clase esperada en su MEJOR fotograma
    (proxy de 'cómo de bien encaja ese sonido'). LP = lista T×(K+1)."""
    return [round(max(LP[t][s] for t in range(len(LP))), 3) for s in seq]


# ----------------------------------------------------------------- hipótesis clínicas
_OCLUS_DE = {"f": "p", "s": "t", "x": "k", "tʃ": "t", "θ": "t"}   # fricativa/africada -> oclusiva


def _seq(s):
    return list(s)


def genera_hipotesis(ref):
    """Genera realizaciones de UN solo proceso aplicado en UNA posición sobre la secuencia
    canónica `ref` (lista de fonemas clínicos). Devuelve [(seq, slug, detalle)], incluida la
    canónica como ('correcto', '')."""
    hyps = [(tuple(ref), "correcto", "")]
    n = len(ref)
    vis = {tuple(ref)}

    def add(seq, slug, detalle):
        t = tuple(seq)
        if t and t not in vis:
            vis.add(t); hyps.append((t, slug, detalle))

    for i, p in enumerate(ref):
        # reducción de grupos: C + (l|ɾ) en ataque -> quita el obstruyente O la LÍQUIDA
        # (omitir la líquida es la forma MÁS común en niños: "tes" por tres, "banco" por blanco)
        if p in CONS and p not in ("l", "ɾ", "r") and i + 1 < n and ref[i + 1] in ("l", "ɾ"):
            add(ref[:i] + ref[i + 1:], "reduccion_grupos", f"omite {p} del grupo")
            add(ref[:i + 1] + ref[i + 2:], "reduccion_grupos", f"omite {ref[i + 1]} del grupo")
        # sustitución r/ɾ -> l
        if p in ("ɾ", "r"):
            add(ref[:i] + ["l"] + ref[i + 1:], "sustitucion_r_l", f"{p}→l")
        # errores en rr: r -> ɾ, r -> (omite)
        if p == "r":
            add(ref[:i] + ["ɾ"] + ref[i + 1:], "errores_rr", "r→ɾ (no vibra)")
            add(ref[:i] + ref[i + 1:], "errores_rr", "omite rr")
        # oclusivización: fricativa/africada -> oclusiva
        if p in FRIC_AFRIC or p == "θ":
            add(ref[:i] + [_OCLUS_DE.get(p, "t")] + ref[i + 1:], "oclusivizacion",
                f"{p}→{_OCLUS_DE.get(p, 't')}")
        # simplificación de diptongos: dos vocales seguidas -> quita una
        if p in VOC and i + 1 < n and ref[i + 1] in VOC:
            add(ref[:i] + ref[i + 1:], "simplificacion_diptongos", f"omite {p} del diptongo")
            add(ref[:i + 1] + ref[i + 2:], "simplificacion_diptongos", f"omite {ref[i + 1]} del diptongo")
        # omisión de consonante final
        if i == n - 1 and p in CONS:
            add(ref[:i], "omision_consonantes_finales", f"omite final {p}")
        # asimilación: una consonante se vuelve como una consonante vecina
        if p in CONS:
            for j in (i - 1, i + 1):
                if 0 <= j < n and ref[j] in CONS and ref[j] != p:
                    add(ref[:i] + [ref[j]] + ref[i + 1:], "asimilaciones",
                        f"{p}→{ref[j]} (asimila al vecino)")
        # --- fuera de la taxonomía de 8 (tipo "otro": se muestra, NO cuenta riesgo) ---
        # lateralización ʎ→l ("sila" por "silla")
        if p == "ʎ":
            add(ref[:i] + ["l"] + ref[i + 1:], "otro", "lateralización ʎ→l (no objetivo)")
        # omisión de consonante inicial / media (evita que gane la canónica por falta de opciones)
        if p in CONS and i == 0:
            add(ref[1:], "otro", f"omite consonante inicial {p} (no objetivo)")
        elif p in CONS and 0 < i < n - 1:
            add(ref[:i] + ref[i + 1:], "otro", f"omite consonante media {p} (no objetivo)")

    # omisión de sílaba: quita un NÚCLEO (grupo de vocales adyacentes, p.ej. el diptongo
    # entero "au") y su consonante de ataque (palabras de ≥2 núcleos)
    nucleos, k = [], 0
    while k < n:
        if ref[k] in VOC:
            j = k
            while j + 1 < n and ref[j + 1] in VOC:
                j += 1
            nucleos.append((k, j)); k = j + 1
        else:
            k += 1
    if len(nucleos) >= 2:
        for a, b in nucleos:
            ini = a - 1 if a > 0 and ref[a - 1] in CONS else a
            add(ref[:ini] + ref[b + 1:], "omision_silabas",
                "omite sílaba " + "".join(ref[ini:b + 1]))
    return hyps


_ESPECIALES = {"<pad>", "<s>", "</s>", "<unk>", "|", " ", ""}


def _transcripcion_libre(logits, id2tok):
    """Transcripción libre (argmax CTC) plegada al inventario clínico. Sirve de 'clase de
    rechazo': la restringida clasifica entre hipótesis cerradas y necesita saber si el audio
    contiene material EXTRA (p.ej. 'gorrocóptero' contiene 'gorro' y ganaría la canónica)."""
    ids = logits.argmax(-1).tolist()
    toks, prev = [], None
    for i in ids:
        if i != prev:
            toks.append(i)
        prev = i
    fon = [id2tok[i] for i in toks if id2tok.get(i) not in _ESPECIALES]
    return normaliza_clinico(fon)


def _pcc(ref, hyp):
    """% de consonantes de la referencia conservadas (presentes en la hipótesis, en orden)."""
    cons_ref = [p for p in ref if p in CONS]
    if not cons_ref:
        return 100.0
    h = list(hyp)
    ok = 0
    for c in cons_ref:
        if c in h:
            h.remove(c); ok += 1
    return round(100.0 * ok / len(cons_ref), 1)


def decodifica_restringido(logits, id2tok, palabra, margen_min=0.15, gop_invalida=-6.0):
    """Núcleo de la decodificación restringida.

    logits: T×V (tensor). Devuelve el registro de palabra: esperado/detectado/eventos/pcc/
    confianza/valida + gop + margen + ranking de las mejores hipótesis.
    """
    ref = ref_clinico(palabra)
    clases, idx, BLANK, cols = construir_mapa(id2tok)
    LP = colapsa_logprobs(logits, cols, BLANK).tolist()   # a Python para el forward CTC

    hyps = genera_hipotesis(ref)
    ref_idx = [idx[p] for p in ref if p in idx]
    punt = []
    for seq, slug, det in hyps:
        si = [idx[p] for p in seq if p in idx]
        score = ctc_logprob(LP, si, BLANK)
        # normalizado por longitud (comparable entre hipótesis de distinto largo)
        norm = score / max(1, len(si) + 1)
        punt.append((norm, score, seq, slug, det))
    punt.sort(key=lambda x: x[0], reverse=True)

    canon = next(p for p in punt if p[3] == "correcto")
    # selección del ganador con sesgo FP>FN: entre las hipótesis cercanas a la mejor,
    # preferir un proceso OBJETIVO (cuenta riesgo) sobre uno 'otro' (no cuenta) sobre la
    # canónica. Así un 'otro' no le roba la victoria a un proceso clínico cercano
    # (p.ej. "elo" por cielo: omisión de sílaba > omite-consonante-inicial).
    BANDA = 0.5
    cerca = [p for p in punt if p[0] >= punt[0][0] - BANDA and p[3] != "correcto"]
    objetivos = [p for p in cerca if p[3] not in ("otro",)]
    mejor = objetivos[0] if objetivos else (cerca[0] if cerca else canon)
    norm_mejor, _sc, seq_mejor, slug, det = mejor
    margen = round(norm_mejor - canon[0], 3)        # ventaja del ganador sobre la canónica

    gops = gop_fonemas(LP, ref_idx)
    gop_medio = round(sum(gops) / len(gops), 3) if gops else _NEG

    # VALIDEZ HÍBRIDA: (a) GOP — los fonemas esperados deben encajar en el audio; y
    # (b) guardián sobre la transcripción LIBRE — el audio no debe contener material EXTRA
    # (la restringida clasifica entre hipótesis cerradas y por sí sola no ve los excesos:
    # 'gorrocóptero' contiene 'gorro' y ganaría la canónica con GOP alto).
    from pipeline.alineamiento import alinear
    from pipeline.clinico import evaluar_validez
    hyp_libre = _transcripcion_libre(logits, id2tok)
    val_libre, motivo_libre = evaluar_validez(alinear(ref, hyp_libre), ref, hyp_libre)
    val_gop = gop_medio > gop_invalida
    valida = val_gop and val_libre
    motivo = (motivo_libre if not val_libre else
              None if val_gop else "lo dicho no se parece a la palabra esperada (o no se oyó)")

    # ganador: si la canónica empata o gana por poco, benefício a la canónica salvo margen claro
    if slug == "correcto" or margen < margen_min:
        eventos, detectado = [], list(ref)
    else:
        eventos, detectado = [{"tipo": slug, "detalle": det}], list(seq_mejor)

    # confianza = MEDIA de posteriors por fonema (exp de cada gop), escala comparable al
    # camino libre (media de softmax-máx); evita que el umbral de fiabilidad sobre-marque.
    conf = round(sum(math.exp(min(0.0, g)) for g in gops) / len(gops), 3) if gops else 0.0
    return {
        "palabra": palabra, "esperado": " ".join(ref), "detectado": " ".join(detectado),
        "transcripcion_libre": " ".join(hyp_libre),
        "confianza": conf, "pcc": _pcc(ref, detectado), "eventos": eventos,
        "valida": valida, "motivo_no_valida": motivo,
        "gop": dict(zip(ref, gops)), "gop_medio": gop_medio, "margen": margen,
        "ranking": [{"detectado": " ".join(s), "proceso": sl, "score": round(nm, 3)}
                    for nm, _s, s, sl, _d in punt[:4]],
        "estrategia": "restringida",
    }
