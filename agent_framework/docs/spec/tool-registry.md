---
feature: tool-registry
status: shipped
since: 2026-06-20
last_verified: 2026-06-22
owner:
adr:
---

# Tool-Registry — Tools sind Funktionen + JSON-Schema

Ein Tool ist eine Funktion, die der Agent aufrufen kann, plus ein JSON-Schema,
das dem Modell sagt, wie es aufgerufen wird. Die Registry hält beides an einer
Stelle. Ein Dekorator registriert eine Funktion als Tool und leitet das Schema
bei Bedarf automatisch aus Typ-Hints und Docstring ab; wer mehr Kontrolle will,
gibt Name, Beschreibung und Parameter explizit an. Andere Bausteine (Memory,
Skills, Planning, MCP) registrieren ihre Tools über dieselbe Registry.

## Fähigkeiten (was der Nutzer tun kann)

- Eine Funktion per Dekorator als Tool registrieren, Schema automatisch abgeleitet
- Name, Beschreibung und Parameter-Schema bei Bedarf explizit überschreiben
- Tools programmatisch (ohne Dekorator) hinzufügen — für generierte Tools aus MCP/Memory
- Die Schema-Liste fürs Modell abrufen und ein Tool per Name ausführen

## Invarianten (was immer gelten muss)

- Ohne explizite Angabe werden Tool-Name aus dem Funktionsnamen, Beschreibung aus dem Docstring und Parameter aus den Typ-Hints abgeleitet.
- Pflicht- vs. optionale Parameter ergeben sich aus dem Vorhandensein eines Default-Werts; `self`, `*args` und `**kwargs` tauchen nicht im Schema auf.
- Python-Typen werden auf JSON-Typen abgebildet; ein unbekannter/fehlender Typ wird als `string` behandelt.
- Der Aufruf eines unbekannten Tools wirft keine Exception, sondern liefert einen Fehlertext — damit das Modell sich selbst korrigieren kann.
- Sind keine Tools registriert, liefert die Schema-Abfrage `None` (statt einer leeren Liste), sodass das Modell tool-frei läuft.

## API-/Schnittstellen-Vertrag (worauf sich Aufrufer verlassen)

- `@registry.tool(name=, description=, parameters=)` — Dekorator; alle Argumente optional
- `registry.add(name, description, parameters, fn)` — programmatische Registrierung
- `registry.call(name, args) -> Any` — führt aus; unbekannt → `"ERROR: unbekanntes Tool '<name>'"`
- `registry.schemas() -> list | None` — Tool-Schemas fürs Modell, `None` wenn leer
- `registry.has(name) -> bool`, `registry.names() -> list[str]`

## Erweiterungspunkte (für Plugins / externe Nutzung)

- `registry.add(...)` ist die generische Naht, über die Memory (`remember`/`recall`), Skills (`list_skills`/`read_skill`), Planning (`update_plan`), Coding-Tools, MCP-Server-Tools und das `task`-Tool dieselbe Registry bestücken.

## Tests (müssen existieren und bestehen)

- `tests/test_agentkit.py::test_tool_auto_schema_and_call` — Auto-Schema aus Signatur + Ausführung
- `tests/test_agentkit.py::test_tool_unknown_is_soft_error` — unbekanntes Tool → Fehlertext statt Exception

## Bekannte Lücken

- Es gibt keine Namens-Kollisionserkennung: `add` mit bereits vergebenem Namen überschreibt die Funktion still, hängt aber ein zweites Schema an.
- Komplexe Typen (Listen-Element-Typen, Enums, verschachtelte Objekte) werden im Auto-Schema nicht erfasst — dafür `parameters` explizit angeben.

## Querverweise

- verwandte Spec: [memory](memory.md), [skills](skills.md), [planning](planning.md), [mcp](mcp.md)
- Code: agentkit/tools.py
