"""
Persistencia longitudinal (SQLite) de la app TDL.

Guarda, por niño (seudonimizado), una línea temporal de EVENTOS: screening, pruebas
de audio, ejercicios asignados/realizados y revisiones del logopeda. Permite calcular la
EVOLUCIÓN entre la 1ª y la 2ª prueba (deltas + tiempos), que alimenta el informe PDF.

Privacidad (RGPD, voz infantil = dato sensible): se guarda un alias seudónimo, NUNCA
audio en la base (el audio queda en data/raw/sesiones/<id>/). DB en data/tdl.sqlite.

Ejecutar:  uv run python src/app/almacen.py   ->  autotest con datos sintéticos
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

TIPOS = {"screening", "prueba_audio", "ejercicios_asignados", "ejercicio_realizado",
         "revision_logopeda"}
# nombres antiguos aceptados en LECTURA (datos creados antes del renombrado)
_EJERCICIO_ASIGNADO = ("ejercicios_asignados", "terapia_asignada")
_EJERCICIO_HECHO = ("ejercicio_realizado", "terapia_realizada")

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS ninos (
    id TEXT PRIMARY KEY,
    alias TEXT,
    edad INTEGER,
    sexo TEXT,
    factores_json TEXT,
    creado TEXT
);
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nino_id TEXT NOT NULL,
    tipo TEXT NOT NULL,
    ts TEXT NOT NULL,
    n_prueba INTEGER,
    payload_json TEXT,
    FOREIGN KEY (nino_id) REFERENCES ninos(id)
);
CREATE INDEX IF NOT EXISTS idx_eventos_nino ON eventos(nino_id, ts);
CREATE TABLE IF NOT EXISTS sesiones (
    sesion_id TEXT PRIMARY KEY,
    estado_json TEXT,
    actualizado TEXT
);
"""


def _ahora():
    return datetime.now(timezone.utc).isoformat()


def ruta_db(raiz):
    return os.path.join(raiz, "data", "tdl.sqlite")


def conectar(raiz):
    """Abre (o crea) la base y garantiza el esquema. Devuelve la conexión."""
    os.makedirs(os.path.join(raiz, "data"), exist_ok=True)
    conn = sqlite3.connect(ruta_db(raiz))
    conn.row_factory = sqlite3.Row
    conn.executescript(_ESQUEMA)
    conn.commit()
    return conn


def registrar_nino(conn, nino_id, alias=None, edad=None, sexo=None, factores=None):
    """Crea o actualiza el registro del niño (upsert)."""
    conn.execute(
        """INSERT INTO ninos (id, alias, edad, sexo, factores_json, creado)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             alias=COALESCE(excluded.alias, ninos.alias),
             edad=COALESCE(excluded.edad, ninos.edad),
             sexo=COALESCE(excluded.sexo, ninos.sexo),
             factores_json=COALESCE(excluded.factores_json, ninos.factores_json)""",
        (nino_id, alias or nino_id, edad, sexo,
         json.dumps(factores or {}, ensure_ascii=False), _ahora()),
    )
    conn.commit()
    return nino_id


def _fila_nino(r):
    return {"id": r["id"], "alias": r["alias"], "edad": r["edad"], "sexo": r["sexo"],
            "factores": json.loads(r["factores_json"] or "{}"), "creado": r["creado"]}


def listar_ninos(conn):
    """Todos los perfiles registrados (más reciente primero), con factores deserializados."""
    rows = conn.execute("SELECT * FROM ninos ORDER BY creado DESC, id ASC").fetchall()
    return [_fila_nino(r) for r in rows]


def obtener_nino(conn, nino_id):
    """Perfil de un niño, o None si no existe."""
    r = conn.execute("SELECT * FROM ninos WHERE id=?", (nino_id,)).fetchone()
    return _fila_nino(r) if r else None


def eliminar_nino(conn, nino_id):
    """Borra de la BD el perfil, sus eventos y el estado de chat. (Los audios/JSON en
    disco los borra la capa de servicio.)"""
    conn.execute("DELETE FROM eventos WHERE nino_id=?", (nino_id,))
    conn.execute("DELETE FROM ninos WHERE id=?", (nino_id,))
    conn.execute("DELETE FROM sesiones WHERE sesion_id=?", (nino_id,))
    conn.commit()


def añadir_evento(conn, nino_id, tipo, payload=None, ts=None, n_prueba=None):
    """Inserta un evento. Para 'prueba_audio' autonumera n_prueba si no se pasa."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo desconocido: {tipo} (válidos: {sorted(TIPOS)})")
    if tipo == "prueba_audio" and n_prueba is None:
        cur = conn.execute(
            "SELECT COUNT(*) FROM eventos WHERE nino_id=? AND tipo='prueba_audio'", (nino_id,))
        n_prueba = cur.fetchone()[0] + 1
    cur = conn.execute(
        "INSERT INTO eventos (nino_id, tipo, ts, n_prueba, payload_json) VALUES (?,?,?,?,?)",
        (nino_id, tipo, ts or _ahora(), n_prueba,
         json.dumps(payload or {}, ensure_ascii=False)),
    )
    conn.commit()
    return cur.lastrowid


def eliminar_ejercicio_realizado(conn, nino_id, titulo):
    """Borra el último evento de 'ejercicio realizado' con ese título (desmarcar en la
    UI). Devuelve True si había algo que borrar."""
    rows = conn.execute(
        f"SELECT id, payload_json FROM eventos WHERE nino_id=? AND tipo IN "
        f"({','.join('?' * len(_EJERCICIO_HECHO))}) ORDER BY id DESC",
        (nino_id, *_EJERCICIO_HECHO)).fetchall()
    for r in rows:
        if json.loads(r["payload_json"] or "{}").get("titulo") == titulo:
            conn.execute("DELETE FROM eventos WHERE id=?", (r["id"],))
            conn.commit()
            return True
    return False


def actualizar_evento_prueba(conn, nino_id, n_prueba, payload):
    """Sustituye el payload de la prueba n_prueba (p.ej. tras la ronda de repetición)."""
    conn.execute(
        """UPDATE eventos SET payload_json=? WHERE id = (
             SELECT id FROM eventos WHERE nino_id=? AND tipo='prueba_audio' AND n_prueba=?
             ORDER BY id DESC LIMIT 1)""",
        (json.dumps(payload, ensure_ascii=False, default=str), nino_id, n_prueba))
    conn.commit()


def guardar_estado(conn, sesion_id, estado):
    """Persiste el estado de una conversación/sesión (memoria de chat en servidor)."""
    conn.execute(
        """INSERT INTO sesiones (sesion_id, estado_json, actualizado) VALUES (?,?,?)
           ON CONFLICT(sesion_id) DO UPDATE SET
             estado_json=excluded.estado_json, actualizado=excluded.actualizado""",
        (sesion_id, json.dumps(estado, ensure_ascii=False, default=str), _ahora()))
    conn.commit()


def cargar_estado(conn, sesion_id):
    """Devuelve el estado guardado de la sesión, o None si no existe."""
    r = conn.execute("SELECT estado_json FROM sesiones WHERE sesion_id=?", (sesion_id,)).fetchone()
    return json.loads(r["estado_json"]) if r and r["estado_json"] else None


def timeline(conn, nino_id):
    """Lista de eventos del niño ordenada por fecha (con payload deserializado)."""
    rows = conn.execute(
        "SELECT * FROM eventos WHERE nino_id=? ORDER BY ts ASC, id ASC", (nino_id,)).fetchall()
    out = []
    for r in rows:
        out.append({"id": r["id"], "tipo": r["tipo"], "ts": r["ts"], "n_prueba": r["n_prueba"],
                    "payload": json.loads(r["payload_json"] or "{}")})
    return out


def n_pruebas(conn, nino_id):
    """Número de pruebas de audio ya realizadas por el niño."""
    return conn.execute(
        "SELECT COUNT(*) FROM eventos WHERE nino_id=? AND tipo='prueba_audio'", (nino_id,)).fetchone()[0]


def palabras_falladas(conn, nino_id):
    """Palabras con algún error clínico (evento != 'otro') en cualquier prueba previa."""
    rows = conn.execute(
        "SELECT payload_json FROM eventos WHERE nino_id=? AND tipo='prueba_audio'", (nino_id,)).fetchall()
    fallos = set()
    for r in rows:
        inf = json.loads(r["payload_json"] or "{}")
        for p in inf.get("palabras", []):
            if any(e.get("tipo") != "otro" for e in p.get("eventos", [])):
                fallos.add(p["palabra"])
    return sorted(fallos)


def _dias(ts_a, ts_b):
    try:
        a = datetime.fromisoformat(ts_a)
        b = datetime.fromisoformat(ts_b)
        return round((b - a).total_seconds() / 86400.0, 1)
    except Exception:
        return None


def _pcc_medio(informe):
    pal = informe.get("palabras", [])
    pccs = [p["pcc"] for p in pal if isinstance(p.get("pcc"), (int, float))]
    return round(sum(pccs) / len(pccs), 1) if pccs else None


def _resumen_prueba(ev):
    inf = ev["payload"]
    rr = inf.get("resumen_riesgo", {})
    return {
        "n_prueba": ev["n_prueba"], "ts": ev["ts"], "riesgo": rr.get("riesgo"),
        "n_errores_impropios": rr.get("n_errores_impropios"),
        "palabras_correctas": rr.get("palabras_correctas"),
        "inteligibilidad_media": rr.get("inteligibilidad_media"),
        "pcc_medio": _pcc_medio(inf),
    }


def evolucion(conn, nino_id):
    """Compara la 1ª y la última prueba de audio: deltas + tiempos entre pruebas y ejercicios."""
    eventos = timeline(conn, nino_id)
    pruebas = [e for e in eventos if e["tipo"] == "prueba_audio"]
    resumenes = [_resumen_prueba(e) for e in pruebas]
    if len(pruebas) < 2:
        return {"nino_id": nino_id, "tiene_evolucion": False, "pruebas": resumenes,
                "nota": "Aún no hay segunda prueba para comparar la evolución."}

    a, b = pruebas[0], pruebas[-1]
    ra, rb = _resumen_prueba(a), _resumen_prueba(b)

    def delta(k):
        va, vb = ra.get(k), rb.get(k)
        return round(vb - va, 3) if isinstance(va, (int, float)) and isinstance(vb, (int, float)) else None

    # ejercicios entre la 1ª y la última prueba (acepta nombres antiguos en lectura)
    ejercicios = [e for e in eventos
                  if e["tipo"] in _EJERCICIO_ASIGNADO + _EJERCICIO_HECHO
                  and a["ts"] <= e["ts"] <= b["ts"]]
    dias_ej_a_prueba = _dias(ejercicios[-1]["ts"], b["ts"]) if ejercicios else None

    return {
        "nino_id": nino_id, "tiene_evolucion": True,
        "pruebas": resumenes,
        "dias_entre_pruebas": _dias(a["ts"], b["ts"]),
        "n_ejercicios_entre_pruebas": len(ejercicios),
        "dias_ultimo_ejercicio_a_prueba": dias_ej_a_prueba,
        "delta": {
            "n_errores_impropios": delta("n_errores_impropios"),
            "palabras_correctas": delta("palabras_correctas"),
            "inteligibilidad_media": delta("inteligibilidad_media"),
            "pcc_medio": delta("pcc_medio"),
            "riesgo": f"{ra.get('riesgo')} -> {rb.get('riesgo')}",
        },
    }


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    # Autotest con DB temporal en memoria.
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_ESQUEMA)
    registrar_nino(conn, "test_4", alias="Peque", edad=4, sexo="m",
                   factores={"bilingue": True})
    añadir_evento(conn, "test_4", "screening", {"riesgo_preliminar": "medio"},
                  ts="2026-01-10T10:00:00+00:00")
    añadir_evento(conn, "test_4", "prueba_audio",
                  {"resumen_riesgo": {"riesgo": "alto", "n_errores_impropios": 6,
                                      "palabras_correctas": 10, "inteligibilidad_media": 0.6},
                   "palabras": [{"pcc": 70.0}, {"pcc": 80.0}]},
                  ts="2026-01-10T10:10:00+00:00")
    añadir_evento(conn, "test_4", "ejercicios_asignados", {"n_ejercicios": 3},
                  ts="2026-01-12T10:00:00+00:00")
    añadir_evento(conn, "test_4", "prueba_audio",
                  {"resumen_riesgo": {"riesgo": "medio", "n_errores_impropios": 3,
                                      "palabras_correctas": 14, "inteligibilidad_media": 0.72},
                   "palabras": [{"pcc": 85.0}, {"pcc": 90.0}]},
                  ts="2026-02-15T10:00:00+00:00")

    ev = evolucion(conn, "test_4")
    print("Evolución test_4:")
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    assert ev["tiene_evolucion"] is True
    assert ev["dias_entre_pruebas"] == 36.0
    assert ev["delta"]["n_errores_impropios"] == -3
    assert ev["delta"]["riesgo"] == "alto -> medio"
    print("\nOK: autotest de evolución longitudinal pasado.")
