---
feature: memory
status: shipped
since: 2026-06-20
last_verified: 2026-06-22
owner:
adr:
---

# Memory — Kurzzeitgedächtnis (Konversation) und Langzeitgedächtnis (über Sessions)

Zwei getrennte Gedächtnisse. Das **Kurzzeitgedächtnis** ist die Nachrichtenliste
des laufenden Auftrags — das Arbeitsgedächtnis. Es misst Tokens und kann alte
Historie zu einer kurzen Notiz zusammenfassen (Compaction), damit der Kontext
klein bleibt. Das **Langzeitgedächtnis** ist ein dateibasierter Notizspeicher,
der Sessions überdauert; der Agent nutzt ihn über die Tools `remember` und
`recall`. Bewusst ohne Embeddings — Abruf per Stichwort-Überlappung.

## Fähigkeiten (was der Nutzer tun kann)

- Die Konversationshistorie eines Auftrags führen und ihre Tokenzahl messen
- Alte Historie automatisch verdichten lassen, wenn der Kontext zu groß wird
- Wichtige Informationen dauerhaft merken (`remember`) und später wiederfinden (`recall`)
- Riesige Tool-Ausgaben gekürzt anhängen statt ungefiltert

## Invarianten (was immer gelten muss)

- Bei der Compaction bleibt die System-Nachricht erhalten und die letzten paar Nachrichten im Original; nur die ältere Historie wird zur Zusammenfassung.
- Der behaltene Schwanz beginnt nie mit einer verwaisten `tool`-Nachricht — das `tool_call`/`tool`-Pairing bleibt intakt.
- Gibt es zu wenig Historie zum Verdichten, passiert nichts (kein Datenverlust, Rückgabe meldet „nicht komprimiert“).
- Langzeit-Einträge werden sofort zeilenweise (JSONL) auf Platte geschrieben und beim nächsten Start vollständig wieder eingelesen.
- `recall` rankt nach Stichwort-Überlappung von Anfrage gegen Text + Tags; ohne Treffer kommt eine klare Leer-Meldung, keine Halluzination.
- Die Token-Zählung nutzt `tiktoken`, wenn verfügbar, sonst eine grobe Schätzung — ohne harte Abhängigkeit.

## API-/Schnittstellen-Vertrag (worauf sich Aufrufer verlassen)

- `ShortTermMemory(system=).add/add_user/tokens()` — Historie führen und messen
- `ShortTermMemory.compact(llm, keep_last=4) -> bool` — alte Historie verdichten, `True` wenn komprimiert
- `LongTermMemory(path).remember(text, tags=) -> str` / `.recall(query, k=3) -> str`
- `LongTermMemory.register_tools(registry)` — bietet `remember`/`recall` als Tools an
- `truncate(text, limit=2000) -> str` — kürzt überlange Texte mit Hinweis auf gekürzte Zeichen

## Konfigurationsfläche (Schalter/Parameter)

- `ShortTermMemory.compact(keep_last=4)` — wie viele jüngste Nachrichten unkomprimiert bleiben
- `LongTermMemory(path="agent_memory.jsonl")` — Speicherort der Notizen
- `recall(k=3)` — Anzahl zurückgegebener Treffer
- `truncate(limit=2000)` — Zeichengrenze für Tool-Ausgaben

## Event-/Datenvertrag (was Konsumenten behandeln müssen)

- `remember` liefert `"gespeichert."`; `recall` liefert eine Trefferliste oder `"(nichts zu '<query>' gefunden)"`.

## Tests (müssen existieren und bestehen)

- `tests/test_agentkit.py::test_short_term_compaction_keeps_system_and_tail` — System + Schwanz bleiben, Pairing intakt
- `tests/test_agentkit.py::test_long_term_memory_roundtrip` — schreiben, neu laden, wiederfinden

## Bekannte Lücken

- Der Stichwort-Abruf kennt weder Synonyme noch Stemming; semantisch ähnliche, aber wörtlich verschiedene Anfragen finden nichts.
- Das Langzeitgedächtnis wächst unbegrenzt; es gibt keine Größenbegrenzung oder Verfallslogik.

## Querverweise

- verwandte Spec: [agentic-loop](agentic-loop.md), [tool-registry](tool-registry.md)
- Code: agentkit/memory.py
