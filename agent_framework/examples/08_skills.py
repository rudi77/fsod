"""Beispiel 8 — Skills: Wissen/Vorgehen als Datei, on demand geladen.

Ein **Skill** ist ein Ordner mit einer `SKILL.md` (offener Agent-Skills-Standard):
Frontmatter (`name`/`description`) + Anleitung. Permanent im Kontext liegt nur der
schlanke Index (die Beschreibungen); die ausführliche Anleitung holt der Agent erst
bei Bedarf — *progressive disclosure*.

Der Agent bekommt zwei Skill-Tools (`list_skills`, `read_skill`) und schreibt das
Ergebnis mit den Coding-Tools in die Sandbox. Beobachte die Spur:
list_skills -> read_skill(changelog) -> write_file.

    python examples/08_skills.py
"""
from pathlib import Path

from dotenv import load_dotenv

from agentkit import (Agent, CodingTools, SKILL_SYSTEM, Skills, ToolRegistry,
                      azure_from_env)
from agentkit.events import STEP, TOOL_CALL

load_dotenv()

SKILLS_DIR = Path(__file__).parent / "skills"

# Progressive Disclosure sichtbar machen: Index (immer) vs. alle SKILL.md (on demand).
skills = Skills(SKILLS_DIR)
index_chars = len(skills.list_skills())
full_chars = sum(len(p.read_text(encoding="utf-8")) for p in SKILLS_DIR.glob("*/SKILL.md"))
print(f"Skills gefunden: {[s['name'] for s in skills.index()]}")
print(f"Index {index_chars} Zeichen  vs  alle SKILL.md {full_chars} Zeichen "
      f"-> nur ~{index_chars * 100 // full_chars}% permanent im Kontext.\n")


def live(ev):
    if ev.type == STEP:
        print(f"\n[Schritt {ev.data['step']}]", flush=True)
    elif ev.type == TOOL_CALL:
        print(f"  🔧 {ev.data['name']}({ev.data['args']})", flush=True)


if __name__ == "__main__":
    tools = ToolRegistry()
    CodingTools(workspace="./agent_workspace", approval=False).register(tools)

    agent = Agent(azure_from_env(), tools=tools, skills=skills,
                  system=SKILL_SYSTEM, strategy="react")

    task = (
        "Erstelle einen CHANGELOG-Eintrag für Version 1.2.0 (Datum 2026-06-20) aus "
        "diesen Commits und schreibe ihn nach CHANGELOG.md:\n"
        "- add skills support (list_skills/read_skill)\n"
        "- fix crash when skills dir is missing\n"
        "- add parallel tool calls\n"
        "- refactor internal token counting"
    )
    answer = agent.run(task, on_event=live)
    print("\n\n=== Antwort ===\n", answer)
    print("\n=== agent_workspace/CHANGELOG.md ===\n",
          (Path("./agent_workspace/CHANGELOG.md").read_text(encoding="utf-8")
           if Path("./agent_workspace/CHANGELOG.md").exists() else "(nicht geschrieben)"))
