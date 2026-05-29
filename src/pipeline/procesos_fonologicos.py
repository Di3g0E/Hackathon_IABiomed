"""
Fase 4c — Detección de PROCESOS FONOLÓGICOS (output clínico para cribado de TDL).

A partir del alineamiento entre la producción reconocida (hipótesis) y la
referencia canónica, interpreta cada desviación como un proceso fonológico con
nombre clínico — igual que un logopeda al puntuar el test de Bosch:

  - Reducción de grupo consonántico  (tres -> tes, blanco -> banco)
  - Omisión de coda / consonante final
  - Omisión (sílaba/segmento)
  - Oclusivización (stopping): fricativa/africada -> oclusiva (s->t, f->p)
  - Frontalización / Posteriorización (cambio de punto de articulación)
  - Sonorización / Ensordecimiento (cambio de sonoridad)
  - Lateralización (r->l) / Rotacismo (l->r)
  - Inserción / epéntesis

Métrica clínica estándar: PCC (Percentage of Consonants Correct).

Trabaja sobre fonemas YA PLEGADOS (mismo espacio que el reconocedor): no aparecen
θ (->s) ni ɾ (->r). Ejecutar:  uv run python src/pipeline/procesos_fonologicos.py
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.alineamiento import alinear

VOCALES = set("aeiou")

# fonema -> (modo, lugar, sonoridad)   [inventario plegado]
RASGOS = {
    "p": ("oclusiva", "bilabial", "sordo"),
    "b": ("oclusiva", "bilabial", "sonoro"),
    "t": ("oclusiva", "dental", "sordo"),
    "d": ("oclusiva", "dental", "sonoro"),
    "k": ("oclusiva", "velar", "sordo"),
    "g": ("oclusiva", "velar", "sonoro"),
    "f": ("fricativa", "labiodental", "sordo"),
    "s": ("fricativa", "alveolar", "sordo"),
    "x": ("fricativa", "velar", "sordo"),
    "tʃ": ("africada", "palatal", "sordo"),
    "m": ("nasal", "bilabial", "sonoro"),
    "n": ("nasal", "alveolar", "sonoro"),
    "ɲ": ("nasal", "palatal", "sonoro"),
    "l": ("lateral", "alveolar", "sonoro"),
    "ʎ": ("lateral", "palatal", "sonoro"),
    "r": ("rótica", "alveolar", "sonoro"),
}
ORDEN_LUGAR = ["bilabial", "labiodental", "dental", "alveolar", "palatal", "velar"]


def es_consonante(p: str) -> bool:
    return p in RASGOS


def clasifica_sustitucion(ref: str, hip: str) -> str:
    if ref in RASGOS and hip in RASGOS:
        mr, lr, vr = RASGOS[ref]
        mh, lh, vh = RASGOS[hip]
        if mr in ("fricativa", "africada") and mh == "oclusiva":
            return "oclusivización"
        if mr == mh and lr == lh and vr != vh:
            return "sonorización" if vh == "sonoro" else "ensordecimiento"
        if mr == "rótica" and mh == "lateral":
            return "lateralización (r→l)"
        if mr == "lateral" and mh == "rótica":
            return "rotacismo (l→r)"
        if lr in ORDEN_LUGAR and lh in ORDEN_LUGAR:
            if ORDEN_LUGAR.index(lh) < ORDEN_LUGAR.index(lr):
                return "frontalización"
            if ORDEN_LUGAR.index(lh) > ORDEN_LUGAR.index(lr):
                return "posteriorización"
        return "sustitución (otra)"
    if ref in VOCALES and hip in VOCALES:
        return "sustitución vocálica"
    return "sustitución consonante↔vocal"


def detectar_procesos(ref: list[str], hip: list[str]) -> dict:
    """Devuelve PCC y la lista de procesos fonológicos detectados."""
    res = alinear(ref, hip)
    procesos = []
    cons_total = sum(1 for p in ref if es_consonante(p))
    cons_ok = 0
    i = 0  # índice en ref
    for tipo, a, b in res.ops:
        if tipo == "acierto":
            if es_consonante(a):
                cons_ok += 1
            i += 1
        elif tipo == "sustitucion":
            procesos.append(f"{clasifica_sustitucion(a, b)} ({a}→{b})")
            i += 1
        elif tipo == "omision":
            prev_c = i - 1 >= 0 and es_consonante(ref[i - 1])
            next_c = i + 1 < len(ref) and es_consonante(ref[i + 1])
            if es_consonante(a) and (prev_c or next_c):
                proc = "reducción de grupo consonántico"
            elif es_consonante(a) and i == len(ref) - 1:
                proc = "omisión de coda/final"
            else:
                proc = "omisión"
            procesos.append(f"{proc} ({a})")
            i += 1
        else:  # insercion
            procesos.append(f"inserción/epéntesis ({b})")
    pcc = 100.0 * cons_ok / cons_total if cons_total else 100.0
    return {
        "pcc": round(pcc, 1),
        "n_procesos": len(procesos),
        "procesos": procesos,
        "cons_ok": cons_ok,
        "cons_total": cons_total,
    }


def _autotest():
    casos = [
        ("tres (reducción grupo)",   "t r e s",     "t e s"),
        ("blanco (reducción grupo)", "b l a n k o", "b a n k o"),
        ("sopa->topa (oclusiv.)",    "s o p a",     "t o p a"),
        ("casa->kata (front s->t)",  "k a s a",     "k a t a"),
        ("rama->lama (lateraliz.)",  "r a m a",     "l a m a"),
        ("correcto",                 "g o r o",     "g o r o"),
    ]
    print("=== Autotest procesos fonológicos ===")
    for nombre, r, h in casos:
        d = detectar_procesos(r.split(), h.split())
        print(f"\n[{nombre}] ref='{r}' hip='{h}'")
        print(f"  PCC={d['pcc']}%  procesos={d['procesos']}")


if __name__ == "__main__":
    _autotest()
