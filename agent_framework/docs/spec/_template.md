---
feature: <slug>
status: <shipped|partial|wip|legacy|deprecated>
since: YYYY-MM-DD
last_verified: YYYY-MM-DD
owner: <handle oder leer>
adr: <optional>
---

# <Anzeigename> — <Untertitel>

Ein Absatz Überblick in einfacher Sprache. Was leistet dieses Feature für den
Nutzer? Was muss man minimal wissen, bevor der Rest Sinn ergibt? Unter 6 Zeilen.

## Fähigkeiten (was der Nutzer tun kann)

- Fähigkeit eins (Nutzer-Sicht)
- Fähigkeit zwei

## Invarianten (was immer gelten muss)

- Eigenschaft, die immer gilt
- eine weitere Eigenschaft
- eine Grenzfall-Invariante (Nebenläufigkeit, Fehlerpfad)

## API-/Schnittstellen-Vertrag (worauf sich Aufrufer verlassen)

- `symbol(args) -> rückgabe` — Verhalten [unter Bedingung]

## Konfigurationsfläche (Schalter/Parameter)

- `parameter: <typ>` (Default `<wert>`) — was er bewirkt

## Event-/Datenvertrag (was Konsumenten behandeln müssen)

- `EVENT_NAME` — wann es feuert, was im Payload steht

## Erweiterungspunkte (für Plugins / externe Nutzung)

- `symbol` in `modul` — was es überschreibt und wann es aufgelöst wird

## Tests (müssen existieren und bestehen)

- `tests/test_agentkit.py::<name>` — welche Invariante

## Bekannte Lücken

- Konkrete fehlende/kaputte Sache mit einem Satz Kontext
- (oder `(keine)`, wenn wirklich leer)

## Querverweise

- verwandte Spec: <feature>.md
- Code: agentkit/<datei>.py
