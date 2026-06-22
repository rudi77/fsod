---
feature: agent-roles
status: shipped
since: 2026-06-21
last_verified: 2026-06-22
owner:
adr:
---

# Agent-Roles — das `task`-Tool und seine Rollen (Claude-Code-Stil)

Der Coding-Agent bekommt **ein** Tool — `task` — mit dem er eine Teilaufgabe an
einen eigenständigen Sub-Agenten delegiert. Der Parameter `subagent_type` wählt
die Rolle, die Prompt und Tool-Teilmenge festlegt: `general` (voller
Coding-Zugriff), `explorer` und `reviewer` (read-only), `tester` (read-only +
Shell). Eine Rolle ist reine Daten — System-Prompt plus erlaubte Tools — und kann
auch als Markdown-Datei mit Frontmatter definiert werden (eine Datei je
Custom-Agent). Läuft der Orchestrator über einen Event-Bus, spiegelt `task` alle
Ereignisse des Sub-Agenten live in denselben Bus, getaggt mit der Rolle.

## Fähigkeiten (was der Nutzer tun kann)

- Teilaufgaben an einen Sub-Agenten delegieren und nur dessen Ergebnis zurückbekommen
- Per `subagent_type` eine Rolle (general/explorer/reviewer/tester) wählen
- Mehrere `task`-Aufrufe aus einer Antwort parallel laufen lassen
- Mit `system` einen Ad-hoc-Sub-Agenten mit eigenem Prompt erzeugen
- Eigene Rollen als `*.md`-Dateien definieren und über `--agents <ordner>` einmischen

## Invarianten (was immer gelten muss)

- Jeder `task`-Aufruf erzeugt einen frischen Sub-Agenten mit eigenem Kurzzeitgedächtnis und der zur Rolle gehörenden Tool-Teilmenge.
- Eine read-only-Rolle (explorer/reviewer) bekommt keine schreibenden oder Shell-Tools; `tester` zusätzlich nur `run_shell`.
- Ein fehlender oder unbekannter `subagent_type` fällt auf `general` zurück; ein leerer `prompt` wird mit Fehlertext abgelehnt.
- Der System-Prompt wird nach Priorität gewählt: expliziter `system`-Override > Rolle > `general`-Default.
- Sub-Agenten erhalten **kein** `task`-Tool: Delegation ist genau eine Ebene tief, keine Rekursion.
- Custom-Rollen aus Dateien überschreiben gleichnamige eingebaute Rollen; ein fehlendes Verzeichnis ergibt keine Custom-Rollen (kein Fehler).
- Das `tools:`-Feld einer Datei-Rolle: leer = alle Tools, `read_only` = die read-only-Teilmenge, sonst eine Komma-/Leerzeichen-Liste von Tool-Namen.
- Läuft der Orchestrator über einen Bus, erbt der Sub-Agent dessen Stop-Knopf und seine Events landen im selben Bus mit Rollen-`source`.

## API-/Schnittstellen-Vertrag (worauf sich Aufrufer verlassen)

- `add_task_tool(registry, *, agent, llm, workspace=".", approval=True, approve=, roles=ROLES)` — registriert das `task`-Tool
- `task(prompt, subagent_type="general", system=) -> str` — liefert die finale Antwort des Sub-Agenten
- `load_roles_from_dir(path) -> {name: AgentRole}` — Custom-Rollen aus `*.md`
- `AgentRole(name, description, system, tools=None, strategy="react")` — eine Rolle als Daten
- `ROLES`, `SUBAGENT_SYSTEM` — eingebaute Rollen und der Orchestrator-Hinweistext

## Konfigurationsfläche (Schalter/Parameter)

- `roles` — Rollen-Dict (eingebaut + per Datei gemischt)
- `workspace`, `approval`, `approve` — an die Coding-Tools der Sub-Agenten durchgereicht
- CLI: `--agents <DIR>` (Custom-Rollen), `--no-subagents` (Tool deaktivieren), `/agents` (Rollen anzeigen)
- Datei-Frontmatter: `name`, `description`, `tools`, `strategy`

## Event-/Datenvertrag (was Konsumenten behandeln müssen)

- Bei aktivem Bus erscheinen die Sub-Agent-Events mit `source = "<rolle>:<prompt-anfang>"` und schließen mit `DONE` (siehe [events](events.md)).

## Erweiterungspunkte (für Plugins / externe Nutzung)

- Eine neue Rolle = ein Eintrag in `ROLES` **oder** eine `*.md`-Datei im `--agents`-Ordner — kein neuer Code.

## Tests (müssen existieren und bestehen)

- `tests/test_agentkit.py::test_roles_presets_have_expected_tool_subsets` — Rollen tragen die erwarteten Tool-Teilmengen
- `tests/test_agentkit.py::test_add_task_tool_registers_and_delegates` — `task` registriert und delegiert
- `tests/test_agentkit.py::test_task_tool_forwards_subagent_events_to_active_bus` — Event-Forwarding in den aktiven Bus
- `tests/test_agentkit.py::test_load_roles_from_dir_parses_frontmatter_and_body` — Datei-Rollen geparst
- `tests/test_agentkit.py::test_load_roles_without_tools_field_means_all_tools` — fehlendes `tools` = alle Tools
- `tests/test_agentkit.py::test_cli_agents_flag_merges_custom_roles` — `--agents` mischt Custom-Rollen ein

## Bekannte Lücken

- (keine)

## Querverweise

- verwandte Spec: [sub-agents](sub-agents.md), [coding-tools](coding-tools.md), [skills](skills.md), [cli](cli.md)
- Code: agentkit/roles.py
