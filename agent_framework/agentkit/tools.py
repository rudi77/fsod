"""Tool-Registry — Tools sind nur Funktionen + JSON-Schema.

Wie in den Notebooks: `@registry.tool(...)` legt Schema (fürs Modell) und
Funktion (für die Ausführung) an EINER Stelle ab. Neu hier: das Schema kann
aus Typ-Hints + Docstring automatisch abgeleitet werden — wer mag, gibt es
weiter explizit an. Mehr Abstraktion braucht es nicht.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional

_PY_TO_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _auto_schema(fn: Callable) -> dict:
    """Leitet ein JSON-Schema aus der Funktionssignatur ab."""
    props: Dict[str, dict] = {}
    required: List[str] = []
    for name, p in inspect.signature(fn).parameters.items():
        if name == "self" or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        jtype = _PY_TO_JSON.get(p.annotation, "string")
        props[name] = {"type": jtype}
        if p.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


class ToolRegistry:
    """Hält Schemas (fürs Modell) und Funktionen (für die Ausführung)."""

    def __init__(self):
        self._schemas: List[dict] = []
        self._fns: Dict[str, Callable] = {}

    def tool(self, name: Optional[str] = None, description: Optional[str] = None,
             parameters: Optional[dict] = None):
        """Decorator: registriert eine Funktion als Tool.

        Ohne Argumente werden Name (Funktionsname), Beschreibung (Docstring) und
        Parameter (Typ-Hints) automatisch übernommen.
        """
        def deco(fn: Callable) -> Callable:
            self.add(
                name or fn.__name__,
                description or (fn.__doc__ or "").strip(),
                parameters or _auto_schema(fn),
                fn,
            )
            return fn
        return deco

    def add(self, name: str, description: str, parameters: dict, fn: Callable) -> None:
        """Tool programmatisch registrieren (z. B. aus MCP oder Memory)."""
        self._schemas.append({
            "type": "function",
            "function": {"name": name, "description": description, "parameters": parameters},
        })
        self._fns[name] = fn

    def schemas(self) -> Optional[List[dict]]:
        """Tool-Schemas fürs Modell — oder None, wenn keine Tools da sind."""
        return self._schemas or None

    def has(self, name: str) -> bool:
        return name in self._fns

    def names(self) -> List[str]:
        return list(self._fns)

    def call(self, name: str, args: dict) -> Any:
        """Führt ein Tool aus. Unbekannte Tools werden als Fehlertext gemeldet
        (das Modell kann sich dann selbst korrigieren)."""
        if name not in self._fns:
            return f"ERROR: unbekanntes Tool '{name}'"
        return self._fns[name](**args)
