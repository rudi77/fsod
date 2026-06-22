---
feature: planning
status: shipped
since: 2026-06-20
last_verified: 2026-06-22
owner:
adr:
---

# Planning — eine mitgeführte, sichtbare Todo-Liste

Plan-and-Execute lässt sich allein über den System-Prompt anstoßen — aber dann
ist der Plan unsichtbar. Dieses Subsystem gibt dem Agenten ein `update_plan`-Tool:
das Modell schreibt seinen Plan als Liste von Schritten mit Status, der Agent
hält ihn fest und kann ihn jederzeit rendern (wie die Todo-Liste in Claude Code).
Jede Aktualisierung ersetzt den Plan komplett und kann einen Callback auslösen,
über den eine UI ihn live anzeigt.

## Fähigkeiten (was der Nutzer tun kann)

- Dem Agenten ein `update_plan`-Tool geben, mit dem er seinen Arbeitsplan führt
- Den aktuellen Plan als lesbare, abgehakte Liste anzeigen
- Auf jede Plan-Aktualisierung mit einem Callback reagieren (z. B. Live-Rendering)

## Invarianten (was immer gelten muss)

- `update_plan` ersetzt den gesamten Plan (kein inkrementelles Patchen) — das Modell übergibt stets die komplette Schrittliste.
- Jeder Schritt hat genau einen Status aus `pending` / `in_progress` / `done`; ein unbekannter oder fehlender Status fällt auf `pending` zurück.
- Das Rendering markiert jeden Schritt sichtbar nach Status (`[ ]` / `[~]` / `[x]`) und nummeriert ihn; ein leerer Plan rendert als „(noch kein Plan)“.
- Ist ein Update-Callback gesetzt, wird er bei jeder Aktualisierung genau einmal mit dem aktuellen Plan aufgerufen.

## API-/Schnittstellen-Vertrag (worauf sich Aufrufer verlassen)

- `Plan(on_update=) ` — optionaler Callback `(Plan) -> None`
- `Plan.update(steps) -> str` — ersetzt den Plan, feuert den Callback, gibt das Rendering zurück
- `Plan.render() -> str` — der aktuelle Plan als mehrzeiliger Text
- `Plan.register_tool(registry)` — bietet dem Agenten das `update_plan`-Tool an

## Event-/Datenvertrag (was Konsumenten behandeln müssen)

- Über den Update-Callback hängt die [CLI](cli.md)/UI ein `PLAN`-Event in den [EventBus](events.md); dessen Daten sind das `Plan`-Objekt selbst.

## Tests (müssen existieren und bestehen)

- `tests/test_agentkit.py::test_plan_update_and_render` — Update ersetzt Plan, Rendering stimmt
- `tests/test_agentkit.py::test_plan_registers_update_plan_tool_and_fires_callback` — Tool registriert, Callback feuert

## Bekannte Lücken

- (keine)

## Querverweise

- verwandte Spec: [agentic-loop](agentic-loop.md), [events](events.md), [cli](cli.md)
- Code: agentkit/planning.py
