---
feature: events
status: shipped
since: 2026-06-20
last_verified: 2026-06-22
owner:
adr:
---

# Events & Event-Bus — *was passiert* getrennt von *wie es angezeigt wird*

Der Agent-Loop produziert neutrale, typisierte Ereignisse statt direkt zu
rendern. Das ist der ganze Trick hinter „Streaming“ und „Event-basiert“: ein
Producer/Consumer-Muster um denselben Loop. Ein Event trägt Typ, Daten, eine
optionale Auftrags-ID und ein `source`-Tag (leer = Haupt-Agent, sonst das Label
eines Sub-Agenten). Der Event-Bus verteilt jedes Event an beliebig viele
Abonnenten — UI-Renderer, Logger, Metriken — gleichzeitig.

## Fähigkeiten (was der Nutzer tun kann)

- Den Lauf eines Agenten als Strom typisierter Ereignisse konsumieren
- Mehrere unabhängige Konsumenten denselben Ereignisstrom abonnieren lassen
- Ereignisse einzelnen (auch parallel laufenden) Sub-Agenten über das `source`-Tag zuordnen

## Invarianten (was immer gelten muss)

- Jedes publizierte Event erreicht **jeden** zum Zeitpunkt des Publizierens registrierten Abonnenten.
- Jeder Abonnent erhält Events in der Reihenfolge, in der sie publiziert wurden (FIFO-Queue je Abonnent).
- Ein Event vom Haupt-Agenten hat ein leeres `source`; Events eines Sub-Agenten tragen dessen Label als `source`.
- Das Publizieren und das Hinzufügen von Abonnenten sind thread-sicher (gemeinsame Nutzung über Worker-Threads hinweg).
- Die Event-Typen sind ein stabiler, fester Satz von Konstanten; Konsumenten dürfen darauf per Gleichheit prüfen.

## Event-/Datenvertrag (was Konsumenten behandeln müssen)

- `STEP` — neuer Loop-Schritt beginnt; Daten `{"step": int}`
- `TEXT_DELTA` — ein Stück gestreamter Antworttext (Token); Daten = Text
- `TOOL_CALL` — Agent ruft ein Tool auf; Daten `{"name", "args"}`
- `TOOL_RESULT` — Tool-Ergebnis; Daten `{"name", "result"}`
- `PLAN` — der Plan/die Todo-Liste wurde aktualisiert; Daten = das `Plan`-Objekt
- `FINAL` — finale Antwort steht; Daten = Antworttext
- `ERROR` — ein Tool/Call ist fehlgeschlagen; Daten `{"name"?, "error"}`
- `CANCELLED` — Auftrag mittendrin abgebrochen; Daten `{"where": str}`
- `DONE` — Auftrag komplett abgearbeitet (auch nach Abbruch); Daten `None`

## API-/Schnittstellen-Vertrag (worauf sich Aufrufer verlassen)

- `AgentEvent(type, data=None, task_id=-1, source="")` — Datenklasse
- `EventBus().subscribe() -> queue.Queue` — eigene Queue je Konsument
- `EventBus().publish(event) -> None` — verteilt an alle Abonnenten

## Tests (müssen existieren und bestehen)

- `tests/test_agentkit.py::test_eventbus_fans_out_to_all_subscribers` — jedes Event erreicht alle Abonnenten

## Bekannte Lücken

- Kein `unsubscribe`: eine einmal registrierte Queue bleibt bis zum Verwerfen des Bus bestehen (für kurzlebige Läufe unkritisch).
- Queues sind unbeschränkt; ein Konsument, der nicht abholt, lässt seine Queue unbegrenzt wachsen.

## Querverweise

- verwandte Spec: [agentic-loop](agentic-loop.md), [cli](cli.md), [agent-roles](agent-roles.md)
- Code: agentkit/events.py
