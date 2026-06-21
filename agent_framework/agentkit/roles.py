"""Sub-Agenten-Rollen — ein `task`-Tool im Stil von Claude Code.

Der Coding-Agent bekommt EIN Tool — `task` — mit dem er eine Teilaufgabe an einen
eigenständigen Sub-Agenten delegiert (eigener Kontext, eigene Tool-Teilmenge). Der
Parameter `subagent_type` wählt die Rolle:

- ``general``  — voller Coding-Zugriff, für beliebige abgegrenzte Teilaufgaben.
- ``explorer`` — read-only Repo-Erkundung (list/glob/grep/read).
- ``reviewer`` — read-only Code-/Diff-Begutachtung.
- ``tester``   — read-only + run_shell: führt Tests aus und berichtet.

Eine Rolle ist reine Daten (`AgentRole`): ein System-Prompt + eine Tool-Teilmenge.
Eine neue Rolle = ein Eintrag in `ROLES` — kein neuer Code, kein neues Tool. Oder als
**Markdown-Datei** (`load_roles_from_dir`, im CLI `--agents <ordner>`): je `.md` ein
Custom-Agent, Frontmatter = Metadaten, Body = System-Prompt — genau wie ein Skill.

**Live-Trace:** Läuft der Orchestrator über einen EventBus (CLI), leitet das
`task`-Tool ALLE Events des Sub-Agenten in denselben Bus weiter — getaggt mit der
Rolle als `source`. Mehrere `task`-Aufrufe aus EINER Antwort laufen parallel
(`parallel_tools=True`), ihre Trace-Zeilen erscheinen verschränkt.

**Grenzen / Caveats:**
- Sub-Agenten bekommen NUR ihre Coding-Tools (kein `task`-Tool) → genau eine Ebene
  tief, keine Rekursion.
- Schreibfähige Sub-Agenten (``general``) teilen sich den EINEN Workspace —
  parallele Schreiber können kollidieren. Faustregel: read-only-Rollen (explore/
  review) parallelisieren, Schreibvorgänge seriell halten.
- `run_shell` bleibt hinter dem Approval-Callback; parallele Approvals können sich
  im Terminal verschränken (mit ``--yes`` entfällt die Rückfrage).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from .coding import READ_ONLY_TOOLS, CodingTools
from .skills import body_after_frontmatter, parse_frontmatter
from .tools import ToolRegistry


@dataclass(frozen=True)
class AgentRole:
    """Ein vordefinierter Sub-Agent: System-Prompt + erlaubte Tool-Teilmenge."""
    name: str
    description: str                      # WANN diese Rolle nutzen (fürs Orchestrator-LLM)
    system: str                          # System-Prompt des Sub-Agenten
    tools: Optional[Tuple[str, ...]] = None  # Coding-Tool-Namen; None = alle
    strategy: str = "react"


# --------------------------------------------------------------- Rollen-Presets
_EXPLORER_SYS = (
    "Du bist ein Explorer-Sub-Agent. Erkunde das Projekt mit list_files/glob_files/"
    "grep/read_file, finde die für den Auftrag relevanten Dateien und Stellen und "
    "gib eine KOMPAKTE Zusammenfassung zurück: relevante Pfade (mit Zeilen), "
    "Kernfunktionen/-klassen und wie sie zusammenhängen. Du änderst NICHTS."
)
_REVIEWER_SYS = (
    "Du bist ein Reviewer-Sub-Agent. Lies den genannten Code/Diff und begutachte ihn "
    "kritisch: Bugs, Grenzfälle, Risiken, Stil/Qualität. Liefere konkrete Findings mit "
    "Datei:Zeile und je einem kurzen Verbesserungsvorschlag. Du änderst NICHTS."
)
_TESTER_SYS = (
    "Du bist ein Tester-Sub-Agent. Finde und führe die relevanten Tests/Befehle aus "
    "(z. B. 'pytest …') mit run_shell und berichte das Ergebnis: was lief, Pass/Fail "
    "und bei Fehlern die entscheidenden Fehlermeldungen. Du änderst KEINEN Code."
)
GENERAL_SUBAGENT_SYSTEM = (
    "Du bist ein fokussierter Sub-Agent. Erledige GENAU den übergebenen Auftrag "
    "eigenständig mit deinen Tools und gib am Ende ein knappes, in sich geschlossenes "
    "Ergebnis zurück — dein Aufrufer sieht nur diese finale Antwort, nicht deinen Verlauf."
)

ROLES: Dict[str, AgentRole] = {
    "explorer": AgentRole(
        "explorer",
        "Read-only Repo-Erkundung: relevante Dateien/Stellen finden und zusammenfassen.",
        _EXPLORER_SYS, READ_ONLY_TOOLS),
    "reviewer": AgentRole(
        "reviewer",
        "Read-only Code-/Diff-Begutachtung: Bugs, Risiken, Qualität mit konkreten Findings.",
        _REVIEWER_SYS, READ_ONLY_TOOLS),
    "tester": AgentRole(
        "tester",
        "Führt Tests/Befehle aus und berichtet Pass/Fail samt Fehlermeldungen (kein Code-Edit).",
        _TESTER_SYS, READ_ONLY_TOOLS + ("run_shell",)),
}

# Hinweis für den Orchestrator-System-Prompt (wird vom CLI angehängt, wenn das
# task-Tool aktiv ist).
SUBAGENT_SYSTEM = (
    "Du kannst Teilaufgaben an eigenständige Sub-Agenten delegieren — mit dem Tool "
    "'task'. Gib einen klaren 'prompt' (die Mission) und einen 'subagent_type' mit:\n"
    "- general: beliebige abgegrenzte Teilaufgabe (voller Coding-Zugriff)\n"
    "- explorer: Repo erkunden / relevante Stellen finden (read-only)\n"
    "- reviewer: Code oder Diff kritisch begutachten (read-only)\n"
    "- tester: Tests ausführen und Ergebnis berichten\n"
    "Optional kannst du mit 'system' einen eigenen System-Prompt für einen Ad-hoc-Agenten "
    "vorgeben. Nutze Sub-Agenten für gut abgegrenzte, parallelisierbare Arbeit und um "
    "deinen eigenen Kontext klein zu halten — für mehrere unabhängige Teilaufgaben rufe "
    "'task' MEHRFACH in DERSELBEN Antwort auf (sie laufen dann parallel). Triviales und "
    "den finalen Zusammenbau erledigst du selbst. Sub-Agenten teilen sich den Workspace: "
    "lass nicht mehrere gleichzeitig dieselben Dateien schreiben."
)


# ----------------------------------------------- Custom-Rollen aus Markdown
# Eine Rolle ist reine Daten — also lässt sie sich auch als Datei beschreiben,
# genau wie ein Skill. Konvention (analog zum Agent-Skills-Standard): ein Ordner
# mit je einer `.md`-Datei pro Agent. Das YAML-Frontmatter liefert die Metadaten,
# der Body IST der System-Prompt:
#
#     agents/
#       security-reviewer.md
#         ---
#         name: security-reviewer
#         description: Read-only Security-Review (Injection, Secrets, AuthZ).
#         tools: read_only          # oder: "grep, read_file"  — fehlt = alle Tools
#         strategy: react
#         ---
#         Du bist ein Security-Reviewer. Prüfe den Code auf …  (der System-Prompt)

def _parse_tools_field(field: Optional[str]) -> Optional[Tuple[str, ...]]:
    """`tools:`-Feld -> Tool-Teilmenge. Fehlt/leer = None (alle Tools); 'read_only'
    = die read-only-Teilmenge; sonst eine Komma-/Leerzeichen-Liste von Tool-Namen."""
    field = (field or "").strip()
    if not field:
        return None
    if field.lower() in ("read_only", "readonly", "read-only"):
        return READ_ONLY_TOOLS
    return tuple(filter(None, re.split(r"[,\s]+", field))) or None


def load_roles_from_dir(path: str) -> Dict[str, AgentRole]:
    """Lädt Custom-Rollen aus `*.md`-Dateien eines Verzeichnisses (siehe oben).

    Liefert ein Dict ``{name: AgentRole}`` (leer, wenn der Ordner fehlt). Gedacht
    zum Mergen über die eingebauten `ROLES`: ``{**ROLES, **load_roles_from_dir(d)}``
    — gleichnamige Dateien überschreiben die Defaults.
    """
    d = Path(path)
    if not d.exists():
        return {}
    out: Dict[str, AgentRole] = {}
    for p in sorted(d.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        name = fm.get("name") or p.stem
        system = body_after_frontmatter(text).strip()
        out[name] = AgentRole(
            name=name,
            description=fm.get("description", ""),
            system=system,
            tools=_parse_tools_field(fm.get("tools")),
            strategy=fm.get("strategy") or "react",
        )
    return out


def add_task_tool(registry: ToolRegistry, *, agent, llm,
                  workspace: str = ".", approval: bool = True,
                  approve: Optional[Callable[[str], bool]] = None,
                  roles: Dict[str, AgentRole] = ROLES) -> ToolRegistry:
    """Registriert das `task`-Tool im `registry` des Orchestrators.

    Jeder Aufruf erzeugt einen FRISCHEN Sub-Agenten (eigenes Kurzzeitgedächtnis,
    eigene Coding-Tool-Teilmenge gemäß Rolle) und gibt dessen finale Antwort als
    Tool-Ergebnis zurück. `agent` ist der Orchestrator-Agent — sein aktiver
    Lauf-Kontext (`agent._bus`/`agent._cancel`, von `run_on_bus` gesetzt) wird zur
    Laufzeit gelesen, um die Sub-Agent-Events live in denselben Bus weiterzuleiten.
    """
    from .agent import Agent  # spät -> kein Zirkelimport

    # Tool-Registries je Rolle EINMAL bauen (CodingTools legt den Workspace an und die
    # Schemas sind unveränderlich) — frische Sub-Agenten teilen sie sich nur lesend.
    coding = CodingTools(workspace=workspace, approval=approval, approve=approve)

    def _registry(only) -> ToolRegistry:
        reg = ToolRegistry()
        coding.register(reg, only=only)
        return reg

    sub_tools = {kind: _registry(role.tools) for kind, role in roles.items()}
    sub_tools.setdefault("general", _registry(None))  # voller Zugriff (außer eine Datei überschreibt 'general')

    # 'general' immer als letzten Typ; Beschreibungen wandern selbst-dokumentierend ins
    # Schema, damit das Modell auch Custom-Rollen (aus Dateien) sieht.
    types = [k for k in roles if k != "general"] + ["general"]
    descs = {k: r.description for k, r in roles.items()}
    descs.setdefault("general", "beliebige Teilaufgabe (voller Zugriff)")
    type_doc = "; ".join(f"{k}: {descs[k]}" for k in types)

    def _task(**kwargs) -> str:
        prompt = (kwargs.get("prompt") or "").strip()
        if not prompt:
            return "ERROR: 'prompt' (die Mission) fehlt."
        kind = kwargs.get("subagent_type") or "general"
        if kind not in sub_tools:
            kind = "general"
        role = roles.get(kind)  # None bei eingebautem 'general'

        # System-Prompt: expliziter 'system'-Override > Rolle > general.
        system = kwargs.get("system") or (role.system if role is not None else GENERAL_SUBAGENT_SYSTEM)
        strategy = role.strategy if role is not None else "react"
        sub = Agent(llm, tools=sub_tools[kind], system=system, strategy=strategy)

        if agent._bus is None:
            return sub.run(prompt)  # ohne Bus (z. B. Library-Nutzung): nur Ergebnis
        source = f"{kind}:{' '.join(prompt.split())[:24]}"
        return sub.run_on_bus(prompt, agent._bus, cancel=agent._cancel, source=source)

    registry.add(
        "task",
        "Delegiert eine Teilaufgabe an einen eigenständigen Sub-Agenten und gibt dessen "
        "Ergebnis zurück. Für mehrere unabhängige Aufgaben mehrfach in DERSELBEN Antwort "
        "aufrufen (laufen parallel).",
        {"type": "object",
         "properties": {
             "prompt": {"type": "string",
                        "description": "Die Mission/Teilaufgabe für den Sub-Agenten, in Worten."},
             "subagent_type": {"type": "string", "enum": types, "default": "general",
                               "description": "Welche Rolle. Verfügbar — " + type_doc},
             "system": {"type": "string",
                        "description": "Optional: eigener System-Prompt für einen Ad-hoc-Agenten "
                                       "(überschreibt die Rolle)."}},
         "required": ["prompt"]},
        _task,
    )
    return registry
