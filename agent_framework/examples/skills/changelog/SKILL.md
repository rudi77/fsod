---
name: changelog
description: Aus einer Liste von Git-Commits einen sauberen CHANGELOG-Eintrag im Keep-a-Changelog-Format erstellen. Verwenden, wenn ein Release notiert oder Änderungen zusammengefasst werden sollen.
---

# Skill: Changelog-Eintrag

Du erstellst aus rohen Commit-Zeilen einen lesbaren CHANGELOG-Eintrag.

## Vorgehen

1. Commits nach Typ gruppieren in die Abschnitte **Added**, **Changed**, **Fixed**,
   **Removed**. Leere Abschnitte weglassen.
2. Jede Zeile als kurzen, nutzerverständlichen Stichpunkt umformulieren (kein
   Commit-Hash, keine internen Refactorings, die niemanden interessieren).
3. Format (Keep a Changelog):

   ```
   ## [<version>] - <YYYY-MM-DD>

   ### Added
   - ...

   ### Fixed
   - ...
   ```

4. Wenn keine Version genannt ist, `[Unreleased]` verwenden.

## Leitplanken

- Nichts erfinden — nur zusammenfassen, was in den Commits steht.
- Knapp und in der Vergangenheitsform formulieren.
