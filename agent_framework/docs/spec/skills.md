---
feature: skills
status: shipped
since: 2026-06-21
last_verified: 2026-06-22
owner:
adr:
---

# Skills — Vorgehen als Datei, on demand geladen

Tools geben dem Agenten *Fähigkeiten* (was er tun kann); ein **Skill** gibt ihm
das *Vorgehen* (wie er etwas tut): eine vorgefertigte Arbeitsanweisung, die er nur
lädt, wenn er sie braucht. Ein Skill ist — nach dem offenen Agent-Skills-Standard —
ein Ordner mit einer `SKILL.md`: ein YAML-Frontmatter (`name`, `description`) plus
ein Markdown-Body mit der Anleitung. Nur die schlanken Frontmatter-Zeilen liegen
permanent im Kontext (der Index); der ausführliche Body wird erst bei Bedarf
geladen (progressive disclosure), sodass beliebig viele Skills den Prompt nicht
sprengen.

## Fähigkeiten (was der Nutzer tun kann)

- Vorgehensweisen als `SKILL.md`-Dateien ablegen und dem Agenten zugänglich machen
- Den Agenten verfügbare Skills auflisten lassen (`list_skills`, nur Name + Beschreibung)
- Den Agenten die vollständige Anleitung eines Skills bei Bedarf laden lassen (`read_skill`)
- Skills über Frontmatter-`name` **oder** Ordnernamen ansprechen

## Invarianten (was immer gelten muss)

- Ein Skill wird nur erkannt, wenn im Skill-Ordner eine `SKILL.md` liegt; fehlt das Verzeichnis, ist die Skill-Liste leer (kein Fehler).
- `list_skills` liefert ausschließlich die Frontmatter-Felder (`name`, `description`) — niemals den Body; der Index bleibt schlank.
- `read_skill` liefert die komplette Datei und findet den Skill per Frontmatter-`name` oder per Ordnernamen; bei keinem Treffer kommt eine klare Leer-Meldung.
- Fehlt der `name` im Frontmatter, dient der Ordnername als Name.
- Das Frontmatter-Parsing ist bewusst minimal (einzeilige `key: value`-Paare) und erzwingt keine YAML-Abhängigkeit.

## API-/Schnittstellen-Vertrag (worauf sich Aufrufer verlassen)

- `Skills(skills_dir="./skills").index() -> list[{name, description}]`
- `Skills.list_skills() -> str` (JSON) / `Skills.read_skill(name) -> str`
- `Skills.register(registry)` — bietet `list_skills` / `read_skill` als Tools an
- `skills_tools(registry=, skills_dir=)` — Bequem-Helfer, registriert die Skill-Tools
- `parse_frontmatter(text) -> dict` / `body_after_frontmatter(text) -> str` — wiederverwendet von [agent-roles](agent-roles.md)

## Konfigurationsfläche (Schalter/Parameter)

- `skills_dir` (Default `"./skills"`) — Wurzel, unter der `*/SKILL.md` gesucht wird
- CLI: `--skills <DIR>` aktiviert Skills für die Session

## Erweiterungspunkte (für Plugins / externe Nutzung)

- Ein Skill ist reine Datei: ein neuer Ordner mit `SKILL.md` genügt — kein Code.

## Tests (müssen existieren und bestehen)

- `tests/test_agentkit.py::test_skills_index_only_frontmatter` — Index ohne Body
- `tests/test_agentkit.py::test_skills_read_full_body_on_demand` — Body erst bei `read_skill`
- `tests/test_agentkit.py::test_skills_read_by_folder_name_when_frontmatter_differs` — Auflösung per Ordnername
- `tests/test_agentkit.py::test_skills_register_tools_and_missing_dir` — fehlendes Verzeichnis → leer, kein Fehler
- `tests/test_agentkit.py::test_agent_skills_param_registers_tools` — `skills=`-Parameter klinkt Tools ein

## Bekannte Lücken

- Mehrzeilige Frontmatter-Werte (Listen, Blöcke) werden nicht unterstützt — nur einzeilige `key: value`-Paare.

## Querverweise

- verwandte Spec: [tool-registry](tool-registry.md), [agent-roles](agent-roles.md)
- Code: agentkit/skills.py
