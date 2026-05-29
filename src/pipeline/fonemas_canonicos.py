"""
Fase 4a — Referencia fonémica canónica de las 32 palabras de Bosch.

Es la "verdad de referencia" (ground truth) contra la que se comparan los
fonemas reconocidos en el audio. Transcripción FONÉMICA amplia (IPA), variante
peninsular estándar como primaria; se anotan las variantes dialectales más
habituales (seseo, yeísmo) para que la logopeda/experta las valide y ajuste.

Notación IPA usada (multi-carácter separados por espacio):
  vocales: a e i o u
  oclusivas: p b t d k g
  fricativas: f  θ (c/z en España)  s  x (j, ge/gi)
  africada: tʃ (ch)
  nasales: m n ɲ (ñ)
  líquidas: l  ɾ (r simple/tap)  r (rr / r- inicial, vibrante múltiple)
  palatal lateral/aprox: ʎ (ll en distinción)  ʝ (y/ll en yeísmo)

Ejecutar:  uv run python src/pipeline/fonemas_canonicos.py   ->  data/fonemas_canonicos.csv
"""
from __future__ import annotations

import csv
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# palabra -> (fonemas_primarios (España estándar), nota de variantes dialectales)
REF = {
    "autobus":  ("a u t o b u s",       ""),
    "barco":    ("b a ɾ k o",           ""),
    "blanco":   ("b l a n k o",         "n ante k suena [ŋ] (alófono)"),
    "bolso":    ("b o l s o",           ""),
    "bufanda":  ("b u f a n d a",       ""),
    "cara":     ("k a ɾ a",             ""),
    "chaqueta": ("tʃ a k e t a",        ""),
    "cielo":    ("θ i e l o",           "seseo (Latam): s i e l o"),
    "clase":    ("k l a s e",           ""),
    "cristal":  ("k ɾ i s t a l",       ""),
    "diente":   ("d i e n t e",         ""),
    "espada":   ("e s p a d a",         ""),
    "estrella": ("e s t ɾ e ʎ a",       "yeísmo: e s t ɾ e ʝ a"),
    "flecha":   ("f l e tʃ a",          ""),
    "fruta":    ("f ɾ u t a",           ""),
    "fuego":    ("f u e g o",           "ue puede realizarse [we]: f w e g o"),
    "globo":    ("g l o b o",           ""),
    "gorro":    ("g o r o",             "rr = vibrante múltiple [r]"),
    "jabon":    ("x a b o n",           ""),
    "lapiz":    ("l a p i θ",           "seseo (Latam): l a p i s"),
    "libro":    ("l i b ɾ o",           ""),
    "mosca":    ("m o s k a",           ""),
    "negro":    ("n e g ɾ o",           ""),
    "niño":     ("n i ɲ o",             ""),
    "peine":    ("p e i n e",           "ei diptongo"),
    "piedra":   ("p i e d ɾ a",         ""),
    "plancha":  ("p l a n tʃ a",        ""),
    "rojo":     ("r o x o",             "r- inicial = vibrante múltiple [r]"),
    "silla":    ("s i ʎ a",             "yeísmo: s i ʝ a"),
    "tambor":   ("t a m b o ɾ",         ""),
    "taza":     ("t a θ a",             "seseo (Latam): t a s a"),
    "tres":     ("t ɾ e s",             ""),
}


def main():
    salida = os.path.join(RAIZ, "data", "fonemas_canonicos.csv")
    filas = []
    for palabra, (fonemas, nota) in sorted(REF.items()):
        fon = fonemas.split()
        filas.append({
            "palabra": palabra,
            "fonemas": fonemas,
            "n_fonemas": len(fon),
            "variantes": nota,
        })
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["palabra", "fonemas", "n_fonemas", "variantes"])
        w.writeheader()
        w.writerows(filas)

    total = sum(r["n_fonemas"] for r in filas)
    inventario = sorted({p for r in filas for p in r["fonemas"].split()})
    print(f"Palabras: {len(filas)} | fonemas totales: {total} | "
          f"inventario único ({len(inventario)}): {' '.join(inventario)}")
    print(f"CSV: {os.path.relpath(salida, RAIZ)}")
    print("\nRevisar con la experta las filas con variantes dialectales:")
    for r in filas:
        if r["variantes"]:
            print(f"  {r['palabra']:10s} {r['fonemas']:18s}  ->  {r['variantes']}")


if __name__ == "__main__":
    main()
