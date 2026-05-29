"""
G2P español ligero (grafema -> fonema) hacia el inventario PLEGADO del proyecto.

Reglas fonémicas del español (variante latinoamericana: seseo, yeísmo, que
coinciden con nuestro plegado θ->s, ʎ/ʝ->ʎ, róticas->r). Pensado para obtener
una referencia fonémica aproximada de transcripciones ortográficas (prueba de
domain gap con voz infantil); ignora resilabificación entre palabras.
"""
from __future__ import annotations
import re
import unicodedata

VOC = set("aeiou")
ACENTO = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u"}


def _limpia(texto: str) -> str:
    t = texto.lower()
    t = re.sub(r"\[[^\]]*\]", " ", t)          # marcas tipo [N]
    t = re.sub(r"[^a-záéíóúüñ ]", " ", t)       # solo letras españolas
    return t


def _palabra(w: str) -> list[str]:
    out, i, n = [], 0, len(w)
    while i < n:
        c = w[i]
        nxt = w[i + 1] if i + 1 < n else ""
        nn = w[i + 2] if i + 2 < n else ""
        par = c + nxt
        if par == "ch":
            out.append("tʃ"); i += 2; continue
        if par == "ll":
            out.append("ʎ"); i += 2; continue
        if par == "rr":
            out.append("r"); i += 2; continue
        if c == "q" and nxt == "u":            # qu(e/i) -> k
            out.append("k"); i += 2; continue
        if c == "g" and nxt == "u" and nn in "ei":  # gu(e/i) -> g
            out.append("g"); i += 2; continue
        c = ACENTO.get(c, c)
        if c in VOC:
            out.append(c)
        elif c == "c":
            out.append("s" if nxt in "eiéí" else "k")
        elif c == "g":
            out.append("x" if nxt in "eiéí" else "g")
        elif c == "z":
            out.append("s")
        elif c == "j":
            out.append("x")
        elif c == "ñ":
            out.append("ɲ")
        elif c == "v":
            out.append("b")
        elif c == "w":
            out.append("u")
        elif c == "x":
            out.extend(["k", "s"])
        elif c == "y":
            out.append("ʎ" if nxt in "aeiouáéíóú" else "i")
        elif c == "r":
            out.append("r")
        elif c == "h":
            pass                                # muda
        elif c in "bdfklmnpst":
            out.append(c)
        i += 1
    return out


def texto_a_fonemas(texto: str) -> list[str]:
    res = []
    for palabra in _limpia(texto).split():
        res.extend(_palabra(palabra))
    return res


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for t in ["Hola, ¿cómo estás vecino?", "La estrella roja", "Buenos días"]:
        print(t, "->", " ".join(texto_a_fonemas(t)))
