"""Skills — Wissen/Vorgehen als Datei, on demand geladen (progressive disclosure).

Tools/MCP geben dem Agenten *Fähigkeiten* (was er TUN kann). Ein **Skill** gibt ihm
das *Vorgehen* (WIE er etwas tut): eine vorgefertigte Arbeitsanweisung, die der Agent
nur dann lädt, wenn er sie braucht.

Ein Skill ist — nach dem offenen **Agent-Skills-Standard** — einfach ein Ordner mit
einer `SKILL.md`:

    skills/
      rechnungsrueckfrage/
        SKILL.md          <- YAML-Frontmatter (name, description) + Anleitung

- **Frontmatter** (`---`-Block mit `name` + `description`): kurz, beschreibt *wann*
  der Skill greift. Nur das liegt permanent im Kontext (der schlanke Index).
- **Body**: die ausführliche Schritt-für-Schritt-Anleitung. Wird **on demand** über
  `read_skill` geladen — so skaliert es auf beliebig viele Skills, ohne den Prompt
  zu sprengen.

Zwei Tools, mehr braucht es nicht:

    list_skills()       -> [name + description]   (klein, kann immer im Kontext liegen)
    read_skill(name)    -> ganze SKILL.md         (groß, nur bei Bedarf)

Derselbe Agent-Loop wie sonst — neu ist nur: Der Agent *entdeckt* und *lädt* Skills,
statt alles fest im System-Prompt zu haben.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

SKILL_SYSTEM = (
    "Du hast Zugriff auf Skills — vorgefertigte Arbeitsanweisungen als Dateien. "
    "Arbeitsweise: Rufe ZUERST list_skills auf und wähle den passenden Skill. "
    "Lade ihn dann mit read_skill(name) und folge seiner Anleitung EXAKT. "
    "Passt kein Skill, arbeite normal weiter."
)


def parse_frontmatter(text: str) -> dict:
    """Liest den YAML-Frontmatter-Block zwischen den ersten beiden '---'.

    Bewusst minimal (einzeilige `key: value`-Paare) — das deckt den Skill-Standard
    (`name`, `description`) ab, ohne eine YAML-Abhängigkeit zu erzwingen.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    meta = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("'\"")
    return meta


class Skills:
    """Entdeckt Skills (Ordner mit `SKILL.md`) und bietet sie dem Agenten als Tools an."""

    def __init__(self, skills_dir: str = "./skills"):
        self.dir = Path(skills_dir)

    # --- Discovery ---
    def _skill_files(self) -> List[Path]:
        if not self.dir.exists():
            return []
        return sorted(self.dir.glob("*/SKILL.md"))

    def index(self) -> List[dict]:
        """Nur das Frontmatter jedes Skills: [{"name", "description"}] — der schlanke
        Index, der permanent im Kontext liegen kann."""
        out = []
        for p in self._skill_files():
            fm = parse_frontmatter(p.read_text(encoding="utf-8"))
            out.append({
                "name": fm.get("name", p.parent.name),
                "description": fm.get("description", ""),
            })
        return out

    def _path_for(self, name: str) -> Optional[Path]:
        """Findet die SKILL.md zu einem Skill — über Frontmatter-Name oder Ordnernamen."""
        for p in self._skill_files():
            fm = parse_frontmatter(p.read_text(encoding="utf-8"))
            if name in (fm.get("name"), p.parent.name):
                return p
        return None

    # --- Tool-Implementierungen ---
    def list_skills(self) -> str:
        """Listet verfügbare Skills (Name + Beschreibung)."""
        return json.dumps(self.index(), ensure_ascii=False, indent=2)

    def read_skill(self, name: str) -> str:
        """Lädt die vollständige Anleitung (SKILL.md) eines Skills."""
        p = self._path_for(name)
        return p.read_text(encoding="utf-8") if p else f"(kein Skill '{name}')"

    def register(self, registry) -> "Skills":
        """Bietet dem Agenten `list_skills` / `read_skill` als Tools an."""
        registry.add(
            "list_skills",
            "Listet verfügbare Skills (Name + Beschreibung). ZUERST aufrufen, um das "
            "passende Vorgehen für die Aufgabe zu finden.",
            {"type": "object", "properties": {}, "required": []},
            self.list_skills,
        )
        registry.add(
            "read_skill",
            "Lädt die vollständige Anleitung (SKILL.md) eines Skills und befolgt sie.",
            {"type": "object",
             "properties": {"name": {"type": "string", "description": "Name des Skills (aus list_skills)."}},
             "required": ["name"]},
            self.read_skill,
        )
        return self


def skills_tools(registry=None, skills_dir: str = "./skills"):
    """Bequemer Helfer: registriert die Skill-Tools in einer (neuen) ToolRegistry."""
    from .tools import ToolRegistry
    registry = registry or ToolRegistry()
    Skills(skills_dir).register(registry)
    return registry
