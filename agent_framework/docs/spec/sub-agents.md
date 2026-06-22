---
feature: sub-agents
status: shipped
since: 2026-06-20
last_verified: 2026-06-22
owner:
adr:
---

# Sub-Agents — ein Agent als Tool eines anderen

Ein **Orchestrator** bekommt ein Delegations-Tool. Jeder Aufruf startet einen
eigenständigen Agent-Loop mit eigenem Kontext und eigenen Tools und gibt nur das
**Ergebnis** zurück — Kontext-Isolation und Spezialisierung in einem. Zusammen
mit nebenläufigen Tool-Calls laufen mehrere Delegationen aus einer einzigen
Orchestrator-Antwort parallel (Map-Reduce / Supervisor). Wird ein Event-Bus
übergeben, werden alle Ereignisse des Sub-Agenten dorthin weitergeleitet und mit
seinem Label getaggt, sodass parallele Sub-Agenten unterscheidbar bleiben.

## Fähigkeiten (was der Nutzer tun kann)

- Einen Sub-Agenten als benanntes Delegations-Tool im Orchestrator registrieren
- Den Sub-Agenten mit eigenem System-Prompt, Tools, Strategie und Schrittgrenze ausstatten
- Mehrere Delegationen aus einer Antwort nebenläufig abarbeiten lassen
- Die Ereignisse des Sub-Agenten live in einen geteilten Event-Bus spiegeln

## Invarianten (was immer gelten muss)

- Jeder Delegations-Aufruf erzeugt einen **frischen** Agenten mit eigenem Kurzzeitgedächtnis — kein State leckt zwischen Aufrufen.
- Der Aufrufer erhält nur die finale Antwort des Sub-Agenten, nicht dessen Verlauf (Kontext-Isolation).
- Ohne Bus liefert die Delegation schlicht das Ergebnis; mit Bus werden alle Sub-Events weitergeleitet, getaggt mit `source = "<name>:<auftrag-anfang>"`.
- Sub-Agenten sind thread-sicher nebenläufig nutzbar, weil jeder eigenen State hat und der Modell-Client thread-sicher ist.
- Der Auftrag wird über einen konfigurierbaren Parameternamen entgegengenommen (Default `auftrag`), der auch im Tool-Schema als Pflichtfeld erscheint.

## API-/Schnittstellen-Vertrag (worauf sich Aufrufer verlassen)

- `add_subagent(registry, name, description, llm, tools=, system=, strategy="react", max_steps=12, param_name="auftrag", param_desc=, parallel_tools=True, bus=None) -> registry`
- Registriert ein Tool `name`, das `param_name` (string, required) erwartet und die finale Antwort des Sub-Agenten als Text liefert.

## Konfigurationsfläche (Schalter/Parameter)

- `tools` — eigene Tool-Registry des Sub-Agenten (Default: leer)
- `system`, `strategy` (Default `react`), `max_steps` (Default `12`)
- `param_name` (Default `"auftrag"`), `param_desc` — Form des Auftrags-Arguments
- `bus` — optionaler [EventBus](events.md) fürs Event-Forwarding

## Event-/Datenvertrag (was Konsumenten behandeln müssen)

- Bei gesetztem `bus`: alle Sub-Agent-Events erscheinen im geteilten Bus mit `source`-Tag und schließen mit `DONE` (siehe [events](events.md)).

## Tests (müssen existieren und bestehen)

- `tests/test_agentkit.py::test_add_subagent_registers_delegate_tool` — Delegations-Tool registriert und delegiert

## Bekannte Lücken

- Sub-Agenten erhalten kein eigenes Delegations-Tool: keine Rekursion über diese generische Naht (für die rollenbasierte Variante siehe [agent-roles](agent-roles.md)).
- Schreibfähige parallele Sub-Agenten auf demselben Workspace können kollidieren — Parallelität auf read-only-Arbeit beschränken.

## Querverweise

- verwandte Spec: [agent-roles](agent-roles.md), [agentic-loop](agentic-loop.md), [events](events.md)
- Code: agentkit/subagents.py
