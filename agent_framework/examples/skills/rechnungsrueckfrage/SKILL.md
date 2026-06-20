---
name: rechnungsrueckfrage
description: Kundenrückfragen zu Palettenrechnungen, Saldo und Belegen vorbereiten. Klassifiziert die Mail, sammelt Evidenz aus dem Kontext und schreibt IMMER nur einen Antwort-Entwurf (Draft), nie eine gesendete Mail.
---

# Skill: Rechnungsrückfrage

Du bereitest die Antwort auf eine Kundenrückfrage zu einer Palettenrechnung vor.
**Immer nur als Draft** — nie senden, nie buchen, nichts erfinden.

## Vorgehen

1. **Mail lesen** und klassifizieren: Rechnungsfrage, Saldoanfrage oder Sonstiges
   (mit Confidence 0–1).
2. **Kunde zuordnen** über die Absenderadresse im Kundenstamm. Ist die Zuordnung
   nicht eindeutig (z. B. zwei gleichnamige Kunden), **eskaliere** (siehe unten) —
   rate nicht.
3. **Evidenz sammeln**: passendes Palettenkonto, Rechnung und Belege aus dem Kontext.
   Jede Zahl muss durch einen Beleg gedeckt sein (Quelle notieren).
4. **Falldatei schreiben** mit den Abschnitten: Mail, Kunde, Evidenz (Tabelle mit
   Quelle), Saldo-Herleitung, Offene Lücken, Draft-Status (inkl. Confidence).
5. **Draft schreiben**: erste Zeile `Betreff: ...`, dann eine sachliche, freundliche
   Antwort, die die abgerechneten Bewegungen aufschlüsselt.

## Eskalation

Bei unklarer Zuordnung oder fehlenden Belegen: Draft trotzdem schreiben, aber mit
der ersten Zeile `BITTE PRUEFEN: <Grund>` und einer höflichen Rückfrage an den Kunden,
statt zu raten. Im Falldatei-Draft-Status als „eskaliert" markieren.

## Leitplanken

- Nie senden, nie buchen.
- Keine Zahl ohne Beleg; fehlende Belege offen benennen.
- Bei Unklarheit eskalieren statt raten.
