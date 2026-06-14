"""
Utilidades LLM compartidas por los grafos.

`rescatar_llamadas_texto`: los modelos llama a veces escriben la llamada a herramienta
COMO TEXTO (p.ej. "<function=iniciar_prueba>{\"nino_id\": \"x\"}</function>") en vez de
usar tool-calling nativo. Este parser detecta esos patrones y los convierte en tool_calls
reales para que el bucle del orquestador no descarrile.
"""
from __future__ import annotations

import json
import re
import uuid

_PATRONES = [
    re.compile(r"<function=(\w+)>\s*(\{.*?\})?\s*</function>", re.DOTALL),
    re.compile(r"<function=(\w+)\s*(\{.*?\})?\s*/?>", re.DOTALL),
]


def rescatar_llamadas_texto(contenido, nombres_validos):
    """Extrae llamadas a herramienta escritas como texto. Devuelve (tool_calls, texto_limpio)."""
    if not contenido or "<function" not in contenido:
        return [], contenido
    calls, texto = [], contenido
    for patron in _PATRONES:
        for m in patron.finditer(contenido):
            nombre = m.group(1)
            if nombre not in nombres_validos:
                continue
            try:
                args = json.loads(m.group(2)) if m.group(2) else {}
            except Exception:
                args = {}
            calls.append({"name": nombre, "args": args, "id": f"rescate_{uuid.uuid4().hex[:8]}",
                          "type": "tool_call"})
        texto = patron.sub("", texto)
        if calls:
            break
    return calls, texto.strip()
