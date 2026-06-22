---
feature: cli
status: shipped
since: 2026-06-21
last_verified: 2026-06-22
owner:
adr:
---

# CLI — Terminal-Frontend im Stil von Claude Code

Ein Konsolen-Frontend um denselben Agent-Loop. Es läuft als fortlaufende Session
(REPL, das Kurzzeitgedächtnis bleibt über Eingaben erhalten) oder one-shot
(Aufgabe als Argument bzw. `--print`). Der Lauf wird live über den Event-Bus
gerendert: gestreamter Text, Tool-Aufrufe, gekürzte Tool-Ergebnisse und der
mitgeführte Plan. Ctrl-C bricht die laufende Aufgabe kooperativ ab, statt das
Programm zu beenden. Ohne API-Key fällt die CLI auf einen netzfreien Demo-Modus
zurück, sodass die installierte Executable sofort läuft.

## Fähigkeiten (was der Nutzer tun kann)

- Eine interaktive Session führen oder eine Aufgabe one-shot abarbeiten
- Den Lauf live verfolgen: Streaming-Text, Tool-Calls, Ergebnisse, Plan
- Eine laufende Aufgabe mit Ctrl-C abbrechen (zweites Ctrl-C beendet das Programm)
- Slash-Befehle nutzen: `/help`, `/clear`, `/reset`, `/plan`, `/tools`, `/skills`, `/agents`, `/exit`
- Provider, Strategie, Workspace, Skills, Custom-Agenten und Langzeitgedächtnis per Flags wählen
- Shell-Approvals einzeln bestätigen oder mit `--yes` global überspringen

## Invarianten (was immer gelten muss)

- In der interaktiven Session bleibt das Kurzzeitgedächtnis über Eingaben hinweg erhalten; `/reset` startet es neu, behält aber die System-Nachricht.
- Das erste Ctrl-C während einer Aufgabe setzt den Stop-Knopf (kooperativer Abbruch); erst das zweite beendet das Programm.
- Nur das Wurzel-`DONE` (leeres `source`) beendet die UI-Schleife; `DONE`-Events von Sub-Agenten werden ignoriert.
- Sub-Agenten werden nicht Token-für-Token gestreamt; ihre selteneren Events sind über ein `source`-Tag der Rolle zugeordnet.
- Im `--print`-Modus erscheint kein Live-Trace, nur die finale Antwort auf stdout.
- Fehlt ein API-Key (oder bei `--demo`), läuft der netzfreie Demo-Agent; mit echtem Provider der volle Coding-Agent inkl. `task`-Tool (außer `--no-subagents`).
- Hübsche Unicode-Glyphen und ANSI-Farben werden automatisch zurückgestuft/abgeschaltet, wenn Konsole oder `NO_COLOR` sie nicht zulassen.
- One-shot ohne Aufgabe und ohne weiteren Modus endet mit Fehlercode statt leerem Lauf.

## Konfigurationsfläche (Schalter/Parameter)

- `-w/--workspace` (Default `.`) — Sandbox-Verzeichnis der Coding-Tools
- `-s/--strategy` (Default `react`) — `react` / `plan` / `plain`
- `--skills <DIR>` — Skills aktivieren; `--agents <DIR>` — Custom-Rollen laden
- `--memory <FILE>` — Langzeitgedächtnis (JSONL) für `remember`/`recall`
- `--provider` (Default `auto`) — `auto` / `azure` / `openai` / `demo`; `--demo` erzwingt Demo
- `--max-steps` (Default `160`), `--no-subagents` — `task`-Tool aus
- `-y/--yes` — Shell ohne Rückfrage; `--steps` — Schrittgrenzen anzeigen; `--no-color`
- `-p/--print` — one-shot, nur finale Antwort; `-V/--version`
- Env: `NO_COLOR` schaltet Farben ab; `.env` wird beim Start geladen

## Tests (müssen existieren und bestehen)

- `tests/test_agentkit.py::test_cli_agents_flag_merges_custom_roles` — `--agents` mischt Custom-Rollen in den Agenten

## Bekannte Lücken

- Kein End-to-End-Test der REPL, des one-shot-Pfads oder des Ctrl-C-Abbruchs; nur der Agenten-Aufbau über `--agents` ist abgedeckt.
- Der Demo-Modus (`agentkit/demo.py`) hat keine eigene Spec und keinen dedizierten Test.

## Querverweise

- verwandte Spec: [agentic-loop](agentic-loop.md), [events](events.md), [coding-tools](coding-tools.md), [agent-roles](agent-roles.md), [planning](planning.md)
- Code: agentkit/cli.py
