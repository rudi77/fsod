---
feature: agentic-loop
status: shipped
since: 2026-06-21
last_verified: 2026-06-22
owner:
adr:
---

# Agentic Loop — ein LLM in einer Schleife mit Tools

Der Kern des Frameworks: ein Agent bekommt einen Auftrag und arbeitet ihn ab,
indem er das Modell so lange befragt, wie es Tools aufruft — Tool ausführen,
Ergebnis anhängen, Modell erneut fragen — und sonst final antwortet. Der Lauf
wird gestreamt: statt einer fertigen Antwort liefert der Agent einen Strom
typisierter Ereignisse (siehe [events](events.md)), auf dem UIs, Logger und
Metriken aufsetzen. Strategie, Schrittobergrenze und Abbruch sind von außen
steuerbar.

## Fähigkeiten (was der Nutzer tun kann)

- Einen Auftrag abarbeiten lassen und die finale Antwort als String erhalten
- Denselben Lauf live verfolgen (gestreamte Text-Token, Tool-Aufrufe, -Ergebnisse)
- Zwischen den Strategien ReAct, Plan-and-Execute und „plain“ wählen
- Den Agenten mit eigenem System-Prompt, Tools, Plan, Skills und Langzeitgedächtnis bestücken
- Einen laufenden Auftrag jederzeit kooperativ abbrechen (Stop-Knopf)
- Mehrere Tool-Aufrufe aus einer Modellantwort nebenläufig ausführen lassen

## Invarianten (was immer gelten muss)

- Die Schleife endet spätestens nach der konfigurierten Schrittobergrenze; danach kommt eine finale Antwort, kein Hängen.
- Antwortet das Modell ohne Tool-Aufruf, ist der Lauf beendet und die finale Antwort steht.
- Die gewählte Strategie steuert ausschließlich den System-Prompt; eine ungültige Strategie wird abgelehnt.
- Mehrere Tool-Aufrufe behalten ihre Reihenfolge, auch wenn sie nebenläufig ausgeführt werden — jede Tool-Antwort bleibt ihrer Aufruf-ID zugeordnet.
- Ein Tool-Fehler beendet den Lauf nicht: der Fehlertext wird als Ergebnis angehängt, sodass das Modell sich selbst korrigieren kann.
- Wird der Stop-Knopf gesetzt, bricht der Lauf an der nächsten sicheren Stelle ab (Schrittgrenze, Token-Stream, vor jedem Tool) und meldet den Abbruch.
- Übersteigt die Historie das Token-Budget, wird sie vor dem nächsten Schritt verdichtet (siehe [memory](memory.md)).
- Beim Aufbau des Modell-Streams werden transiente Fehler mehrfach wiederholt, bevor aufgegeben wird.

## API-/Schnittstellen-Vertrag (worauf sich Aufrufer verlassen)

- `run(task, cancel=, on_event=) -> str` — arbeitet ab, liefert die finale Antwort; ruft optional pro Event einen Callback
- `run_iter(task, cancel=) -> Iterator[AgentEvent]` — derselbe Lauf als Event-Generator
- `run_on_bus(task, bus, cancel=, source=) -> str` — publiziert jedes Event (mit `source`-Tag) auf einen [EventBus](events.md) und schließt mit `DONE`

## Konfigurationsfläche (Schalter/Parameter)

- `strategy: str` (Default `"react"`) — eine von `react` / `plan` / `plain`
- `max_steps: int` (Default `12`) — Obergrenze der Loop-Schritte pro Auftrag
- `token_budget: int` (Default `8000`) — ab hier wird die Historie verdichtet
- `parallel_tools: bool` (Default `True`) — mehrere Tool-Calls einer Antwort nebenläufig
- `system, tools, plan, skills, long_term, memory` — optionale Bausteine, die der Agent einklinkt

## Event-/Datenvertrag (was Konsumenten behandeln müssen)

- Liefert `STEP`, `TEXT_DELTA`, `TOOL_CALL`, `TOOL_RESULT`, `ERROR`, `FINAL`, `CANCELLED`; über `run_on_bus` zusätzlich `DONE`. Vollständige Definition: [events](events.md).

## Tests (müssen existieren und bestehen)

- `tests/test_agentkit.py::test_agent_runs_tool_then_answers` — Tool-Aufruf, dann finale Antwort
- `tests/test_agentkit.py::test_agent_run_returns_final_string` — `run` gibt finalen String
- `tests/test_agentkit.py::test_agent_strategy_injects_preamble` — Strategie steuert System-Prompt
- `tests/test_agentkit.py::test_agent_cancel_before_start` — Stop-Knopf bricht ab
- `tests/test_agentkit.py::test_agent_run_on_bus_emits_done` — Bus-Lauf endet mit `DONE`
- `tests/test_agentkit.py::test_parallel_tools_preserve_order_and_pairing` — Reihenfolge/Pairing bei parallelen Tools

## Bekannte Lücken

- Kein eigener Test deckt die Token-Budget-getriggerte Compaction im Loop selbst ab (nur `ShortTermMemory.compact` direkt getestet).
- Das Retry beim Stream-Aufbau (`_stream_with_retry`) hat keinen direkten Test.

## Querverweise

- verwandte Spec: [events](events.md), [memory](memory.md), [tool-registry](tool-registry.md), [agent-roles](agent-roles.md)
- Code: agentkit/agent.py
