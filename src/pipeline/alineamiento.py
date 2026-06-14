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


def canonicaliza_ops(ops):
    """Canonicaliza alineamientos óptimos equivalentes: si un tramo de omisiones (o
    inserciones) va seguido de un ACIERTO cuyo símbolo coincide con el PRIMER elemento
    del tramo, se rota para que el acierto quede antes y la omisión/inserción al final.

    Motivo: con símbolos repetidos hay varios alineamientos de coste mínimo y el
    retroceso elige uno arbitrario; p.ej. ref='r o x o', hip='r o' produce
    [✓r, omite o, omite x, ✓o] ("omite ox", sin sentido silábico) en vez del natural
    [✓r, ✓o, omite x, omite o] ("omite xo", la sílaba final). Preferimos conservar los
    fonemas INICIALES y omitir los FINALES (patrón real de truncamiento infantil).
    No cambia ningún conteo (aciertos/S/D/I idénticos), solo el orden/posición."""
    ops = list(ops)
    cambiado = True
    while cambiado:
        cambiado = False
        i = 0
        while i < len(ops):
            tipo = ops[i][0]
            if tipo not in ("omision", "insercion"):
                i += 1; continue
            j = i
            while j < len(ops) and ops[j][0] == tipo:
                j += 1
            # tramo [i, j); ¿le sigue un acierto con el mismo símbolo que ops[i]?
            if j < len(ops) and ops[j][0] == "acierto":
                simbolo = ops[i][1] if tipo == "omision" else ops[i][2]
                if ops[j][1] == simbolo:
                    nuevo_final = (("omision", simbolo, "∅") if tipo == "omision"
                                   else ("insercion", "∅", simbolo))
                    ops[i:j + 1] = [ops[j]] + ops[i + 1:j] + [nuevo_final]
                    cambiado = True
            i = j
    return ops


_VOCALES = set("aeiou")


def _coste_sustitucion(a: str, b: str) -> float:
    """Coste fonológicamente ponderado: sustituir DENTRO de la misma clase (vocal↔vocal,
    consonante↔consonante) cuesta 1.0; CRUZAR clase (vocal↔consonante) cuesta 1.5.

    Motivo: ante alineamientos de coste igual con la métrica plana, el retroceso podía
    emparejar una vocal de la referencia con una consonante insertada (p.ej. 'gorro'
    g o r o vs 'g u r r o s': elegía o→r 'asimilación' FALSA en vez de o→u + inserción).
    Con la ponderación, el alineador prefiere siempre el emparejamiento con sentido
    fonológico. Sigue siendo < 2.0 (omisión+inserción), así que las sustituciones
    vocal↔consonante GENUINAS (sin alternativa de igual coste) se conservan."""
    if a == b:
        return 0.0
    return 1.0 if ((a in _VOCALES) == (b in _VOCALES)) else 1.5


def alinear(ref: list[str], hip: list[str]) -> Resultado:
    """Alineamiento por distancia de edición ponderada con retroceso de operaciones."""
    n, m = len(ref), len(hip)
    # matriz de costes (float: la sustitución entre clases vale 1.5)
    d = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = float(i)
    for j in range(m + 1):
        d[0][j] = float(j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(
                d[i - 1][j] + 1.0,                                  # omisión (borrar ref)
                d[i][j - 1] + 1.0,                                  # inserción (añadir hip)
                d[i - 1][j - 1] + _coste_sustitucion(ref[i - 1], hip[j - 1]),
            )
    # retroceso (los costes son múltiplos exactos de 0.5: la igualdad float es segura)
    res = Resultado(n_ref=n)
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref[i - 1] == hip[j - 1] and d[i][j] == d[i - 1][j - 1]:
            res.aciertos += 1
            res.ops.append(("acierto", ref[i - 1], hip[j - 1])); i -= 1; j -= 1
        elif (i > 0 and j > 0
              and d[i][j] == d[i - 1][j - 1] + _coste_sustitucion(ref[i - 1], hip[j - 1])):
            res.sustituciones += 1
            res.ops.append(("sustitucion", ref[i - 1], hip[j - 1])); i -= 1; j -= 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1.0:
            res.omisiones += 1
            res.ops.append(("omision", ref[i - 1], "∅")); i -= 1
        else:
            res.inserciones += 1
            res.ops.append(("insercion", "∅", hip[j - 1])); j -= 1
    res.ops.reverse()
    res.ops = canonicaliza_ops(res.ops)
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
