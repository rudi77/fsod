---
feature: coding-tools
status: shipped
since: 2026-06-21
last_verified: 2026-06-22
owner:
adr:
---

# Coding-Tools — Dateien lesen/schreiben/ändern und Shell, mit Sicherheitsnetzen

Was ein Coding-Agent braucht: Verzeichnisse listen, Dateien per Glob finden,
Inhalte per Regex durchsuchen, lesen, schreiben, gezielt ändern und Shell-Befehle
ausführen. Mit zwei Sicherheitsnetzen: Alle Pfade sind in einen Workspace-Ordner
(die Sandbox) eingesperrt, und vor jeder Shell-Ausführung wird per Callback um
Erlaubnis gefragt. `run_shell` läuft plattformübergreifend (PowerShell auf
Windows, sonst bash). Eine read-only-Teilmenge der Tools lässt sich an
eingeschränkte Sub-Agenten-Rollen vergeben.

## Fähigkeiten (was der Nutzer tun kann)

- Dateien in der Sandbox listen, per Glob finden, per Regex durchsuchen und lesen
- Dateien schreiben und einen eindeutigen Textabschnitt gezielt ersetzen
- Shell-Befehle in der Sandbox ausführen — nach Rückfrage und mit Timeout
- Nur eine read-only-Teilmenge registrieren (für erkundende/begutachtende Rollen)

## Invarianten (was immer gelten muss)

- Jeder Pfad wird in die Sandbox aufgelöst; ein Pfad außerhalb des Workspace wird abgelehnt (Fehler statt Zugriff).
- `run_shell` führt nichts aus, solange das Approval aktiv ist und der Callback nicht zustimmt; Ablehnung liefert „ABGELEHNT“, kein Befehl läuft.
- `edit_file` ersetzt nur ein **eindeutiges** Vorkommen: kommt der Text gar nicht oder mehrfach vor, schlägt die Änderung mit Fehlermeldung fehl und die Datei bleibt unverändert.
- Suche und Glob überspringen Rausch-Verzeichnisse (`.git`, `__pycache__`, `.venv`, `node_modules`, …).
- Shell-Befehle laufen im Workspace-Verzeichnis und werden nach einem konfigurierbaren Timeout abgebrochen; die Ausgabe wird gekürzt zurückgegeben.
- `glob_files` und `grep` sind read-only und ohne Rückfrage; Treffer werden bei Erreichen des Limits abgeschnitten (mit Hinweis).
- Ein ungültiges Regex in `grep` liefert einen Fehlertext statt einer Exception.

## API-/Schnittstellen-Vertrag (worauf sich Aufrufer verlassen)

- `list_files(path=".") -> str`, `glob_files(pattern, path=".", limit=200) -> str`
- `grep(pattern, path=".", glob="**/*", limit=200) -> str` — Treffer als `pfad:zeile: text`
- `read_file(path) -> str`, `write_file(path, content) -> str`
- `edit_file(path, old, new) -> str` — nur bei genau einem Vorkommen von `old`
- `run_shell(command) -> str` — `exit=… / STDOUT / STDERR`, oder „ABGELEHNT“ / Timeout-Fehler
- `CodingTools(...).register(registry, only=READ_ONLY_TOOLS)` — Teilmenge registrieren
- `coding_tools(registry=, workspace=, approval=, approve=)` — Bequem-Helfer

## Konfigurationsfläche (Schalter/Parameter)

- `workspace` (Default `"./agent_workspace"`) — die Sandbox-Wurzel
- `approval: bool` (Default `True`) — Rückfrage vor `run_shell`
- `approve: Callable[[str], bool]` — eigener Zustimmungs-Callback (Default: interaktive Konsole)
- `shell_timeout: int` (Default `120`) — Sekunden bis zum Abbruch eines Befehls
- `only` / `READ_ONLY_TOOLS` — auf `list_files`/`glob_files`/`grep`/`read_file` beschränken
- CLI: `-w/--workspace`, `-y/--yes` (Approval aus)

## Tests (müssen existieren und bestehen)

- `tests/test_agentkit.py::test_coding_tools_sandbox_and_io` — Sandbox-Grenze + schreiben/lesen/ändern
- `tests/test_agentkit.py::test_coding_tools_glob_and_grep` — Glob/Regex-Suche
- `tests/test_agentkit.py::test_coding_tools_run_shell_no_approval` — Shell ohne Approval läuft
- `tests/test_agentkit.py::test_coding_register_only_subset` — read-only-Teilmenge registriert

## Bekannte Lücken

- Symlinks innerhalb der Sandbox, die nach außen zeigen, werden nicht gesondert behandelt — der Schutz beruht auf der aufgelösten Pfad-Präfixprüfung.
- Kein Test deckt das Shell-Timeout oder die Approval-Ablehnung direkt ab.

## Querverweise

- verwandte Spec: [agent-roles](agent-roles.md), [tool-registry](tool-registry.md), [cli](cli.md)
- Code: agentkit/coding.py
