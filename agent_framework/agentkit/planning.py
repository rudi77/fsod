"""Planning — eine mitgeführte Todo-Liste + das `update_plan`-Tool.

Plan-and-Execute wird im Notebook nur über den System-Prompt angestoßen. Damit
der Plan auch *sichtbar* und *mitgeführt* wird (wie die Todo-Liste in Claude Code),
gibt dieses Modul dem Agenten ein `update_plan`-Tool: das Modell schreibt seinen
Plan als Liste von Schritten mit Status, der Agent hält ihn fest und rendert ihn.
"""

from __future__ import annotations

from typing import Callable, List, Optional

_STATUS_MARK = {"pending": "[ ]", "in_progress": "[~]", "done": "[x]"}


class Plan:
    """Hält die aktuelle Todo-Liste des Agenten."""

    def __init__(self, on_update: Optional[Callable[["Plan"], None]] = None):
        self.steps: List[dict] = []   # [{"step": str, "status": "pending|in_progress|done"}]
        self._on_update = on_update

    def update(self, steps: List[dict]) -> str:
        """Ersetzt den Plan komplett (wie TodoWrite) und gibt ihn gerendert zurück."""
        cleaned = []
        for s in steps:
            status = s.get("status", "pending")
            if status not in _STATUS_MARK:
                status = "pending"
            cleaned.append({"step": str(s.get("step", "")).strip(), "status": status})
        self.steps = cleaned
        if self._on_update:
            self._on_update(self)
        return self.render()

    def render(self) -> str:
        if not self.steps:
            return "(noch kein Plan)"
        return "\n".join(f"{_STATUS_MARK[s['status']]} {i}. {s['step']}"
                         for i, s in enumerate(self.steps, 1))

    def register_tool(self, registry) -> "Plan":
        """Bietet dem Agenten das `update_plan`-Tool an."""
        registry.add(
            "update_plan",
            "Legt den Arbeitsplan an oder aktualisiert ihn. Übergib die KOMPLETTE "
            "Schrittliste; markiere den aktuellen Schritt als 'in_progress' und "
            "erledigte als 'done'. Rufe das Tool zu Beginn und nach jedem Fortschritt auf.",
            {"type": "object", "properties": {
                "steps": {"type": "array", "items": {
                    "type": "object", "properties": {
                        "step": {"type": "string", "description": "Beschreibung des Schritts."},
                        "status": {"type": "string",
                                   "enum": ["pending", "in_progress", "done"]},
                    }, "required": ["step", "status"]}}},
             "required": ["steps"]},
            lambda steps: self.update(steps),
        )
        return self
