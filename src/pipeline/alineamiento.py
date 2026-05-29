"""
Fase 4a — Alineamiento de secuencias de fonemas y métricas.

Compara una secuencia RECONOCIDA (hipótesis) con la CANÓNICA (referencia) usando
distancia de edición (Levenshtein) con retroceso, y produce:
  - operaciones: aciertos / sustituciones / omisiones (deleciones) / inserciones
  - métricas por fonema: precision, recall, F1
  - PER (Phoneme Error Rate) = (S + D + I) / N_ref

Definiciones (nivel token/fonema):
  TP = aciertos
  FP = inserciones + sustituciones   (fonemas de la hipótesis sin correspondencia correcta)
  FN = omisiones    + sustituciones   (fonemas de la referencia no reconocidos correctamente)

Las omisiones y sustituciones son justamente los PROCESOS FONOLÓGICOS de interés
clínico (un niño con TDL omite o sustituye fonemas) -> base de la Fase 4c.

Ejecutar:  uv run python src/alineamiento.py   (lanza autotest)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


@dataclass
class Resultado:
    aciertos: int = 0
    sustituciones: int = 0
    omisiones: int = 0       # en la referencia, no reconocidos (deletion)
    inserciones: int = 0     # en la hipótesis, sobrantes (insertion)
    ops: list = field(default_factory=list)   # [(tipo, ref, hip), ...]
    n_ref: int = 0

    @property
    def tp(self): return self.aciertos
    @property
    def fp(self): return self.inserciones + self.sustituciones
    @property
    def fn(self): return self.omisiones + self.sustituciones

    @property
    def precision(self):
        d = self.tp + self.fp
        return self.tp / d if d else 0.0
    @property
    def recall(self):
        d = self.tp + self.fn
        return self.tp / d if d else 0.0
    @property
    def f1(self):
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0
    @property
    def per(self):
        return (self.sustituciones + self.omisiones + self.inserciones) / self.n_ref if self.n_ref else 0.0


def alinear(ref: list[str], hip: list[str]) -> Resultado:
    """Alineamiento por distancia de edición con retroceso de operaciones."""
    n, m = len(ref), len(hip)
    # matriz de costes
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            coste_sub = 0 if ref[i - 1] == hip[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,            # omisión (borrar ref)
                d[i][j - 1] + 1,            # inserción (añadir hip)
                d[i - 1][j - 1] + coste_sub  # acierto/sustitución
            )
    # retroceso
    res = Resultado(n_ref=n)
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref[i - 1] == hip[j - 1] and d[i][j] == d[i - 1][j - 1]:
            res.aciertos += 1
            res.ops.append(("acierto", ref[i - 1], hip[j - 1])); i -= 1; j -= 1
        elif i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + 1:
            res.sustituciones += 1
            res.ops.append(("sustitucion", ref[i - 1], hip[j - 1])); i -= 1; j -= 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            res.omisiones += 1
            res.ops.append(("omision", ref[i - 1], "∅")); i -= 1
        else:
            res.inserciones += 1
            res.ops.append(("insercion", "∅", hip[j - 1])); j -= 1
    res.ops.reverse()
    return res


def agregar(resultados: list[Resultado]) -> Resultado:
    """Suma micro (agrega TP/FP/FN sobre todo el conjunto)."""
    total = Resultado()
    for r in resultados:
        total.aciertos += r.aciertos
        total.sustituciones += r.sustituciones
        total.omisiones += r.omisiones
        total.inserciones += r.inserciones
        total.n_ref += r.n_ref
    return total


def _autotest():
    casos = [
        ("casa correcta",    "k a s a", "k a s a"),
        ("sustitución s->t", "k a s a", "k a t a"),
        ("omisión de r",     "t ɾ e s", "t e s"),
        ("inserción",        "s o l",   "s o l e"),
    ]
    print("=== Autotest de alineamiento ===")
    for nombre, r, h in casos:
        res = alinear(r.split(), h.split())
        print(f"\n[{nombre}] ref='{r}'  hip='{h}'")
        print(f"  aciertos={res.aciertos} sust={res.sustituciones} "
              f"omis={res.omisiones} ins={res.inserciones}")
        print(f"  P={res.precision:.2f} R={res.recall:.2f} F1={res.f1:.2f} PER={res.per:.2f}")
        print("  ops:", [f"{t}:{a}->{b}" for t, a, b in res.ops])


if __name__ == "__main__":
    _autotest()
