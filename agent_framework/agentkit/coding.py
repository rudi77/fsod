"""Coding-Tools — was ein Coding-Agent braucht: Dateien lesen/schreiben/ändern,
Verzeichnisse listen und Shell-Befehle ausführen. Mit zwei Sicherheitsnetzen
aus dem Notebook:

1. **Sandbox**: Alle Pfade werden in einen Workspace-Ordner eingesperrt.
2. **Approval**: Vor jeder Shell-Ausführung wird (per Callback) um Erlaubnis gefragt.

`run_shell` ist plattformübergreifend: PowerShell auf Windows, sonst bash.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable, Optional, Sequence

# Read-only-Teilmenge der Coding-Tools (kein write/edit/run_shell). Praktisch für
# Sub-Agenten-Rollen, die nur erkunden oder begutachten dürfen (siehe roles.py).
READ_ONLY_TOOLS = ("list_files", "glob_files", "grep", "read_file")

CODING_SYSTEM = (
    "Du bist ein Coding-Agent und arbeitest im aktuellen Projektverzeichnis "
    "(deine Sandbox; Pfade außerhalb sind gesperrt). Verschaffe dir zuerst mit "
    "list_files/glob_files/grep/read_file einen Überblick über den vorhandenen Code, "
    "bevor du ihn änderst (glob_files findet Dateien, grep durchsucht Inhalte — beide "
    "read-only). Plane deine Arbeit mit update_plan. Schreibe Code mit write_file/edit_file, "
    "führe ihn mit run_shell aus und teste mit pytest. Schlägt ein Test fehl, lies "
    "die Fehlermeldung, korrigiere den Code und versuche es erneut. Erkläre am Ende "
    "kurz, was du gebaut hast."
)


class CodingTools:
    """Registriert Coding-Tools (sandboxed) in einer ToolRegistry."""

    def __init__(self, workspace: str = "./agent_workspace", approval: bool = True,
                 approve: Optional[Callable[[str], bool]] = None, shell_timeout: int = 120):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.approval = approval
        self.shell_timeout = shell_timeout
        self._approve = approve or self._default_approve

    # Ordner, die bei Suche/Glob übersprungen werden (Rauschen statt Code).
    _IGNORE = {".git", "__pycache__", ".venv", "venv", "node_modules",
               ".mypy_cache", ".pytest_cache", ".idea", ".vscode"}

    # --- Sicherheit ---
    def _safe(self, path: str) -> Path:
        """Sperrt einen Pfad in die Sandbox ein."""
        p = (self.workspace / path).resolve()
        if not (p == self.workspace or str(p).startswith(str(self.workspace) + os.sep)):
            raise ValueError(f"Pfad außerhalb der Sandbox: {path}")
        return p

    def _ignored(self, p: Path) -> bool:
        """True, wenn der Pfad in einem Ignore-Ordner liegt."""
        return any(part in self._IGNORE for part in p.relative_to(self.workspace).parts)

    @staticmethod
    def _default_approve(command: str) -> bool:
        ans = input(f"\n⚠️  Shell ausführen?\n  {command}\n[j/N] ")
        return ans.strip().lower() in ("j", "ja", "y", "yes")

    # --- Tool-Implementierungen ---
    def list_files(self, path: str = ".") -> str:
        """Listet die Dateien im (Sandbox-)Verzeichnis auf."""
        return "\n".join(sorted(os.listdir(self._safe(path)))) or "(leer)"

    def glob_files(self, pattern: str = "**/*", path: str = ".", limit: int = 200) -> str:
        """Findet Dateien per Glob-Muster (z. B. '**/*.py') relativ zum Verzeichnis."""
        root = self._safe(path)
        matches = sorted(
            str(p.relative_to(self.workspace)).replace(os.sep, "/")
            for p in root.glob(pattern)
            if p.is_file() and not self._ignored(p)
        )
        if not matches:
            return "(keine Treffer)"
        extra = len(matches) - limit
        shown = matches[:limit]
        return "\n".join(shown) + (f"\n…(+{extra} weitere)" if extra > 0 else "")

    def grep(self, pattern: str, path: str = ".", glob: str = "**/*", limit: int = 200) -> str:
        """Durchsucht Dateiinhalte per Regex; liefert 'pfad:zeile: text' je Treffer."""
        import re
        try:
            rx = re.compile(pattern)
        except re.error as e:
            return f"ERROR: ungültiges Regex: {e}"
        root = self._safe(path)
        hits: list[str] = []
        for p in sorted(root.glob(glob)):
            if not p.is_file() or self._ignored(p):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(p.relative_to(self.workspace)).replace(os.sep, "/")
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{rel}:{i}: {line.strip()[:200]}")
                    if len(hits) >= limit:
                        return "\n".join(hits) + f"\n…(abgeschnitten bei {limit} Treffern)"
        return "\n".join(hits) or "(keine Treffer)"

    def read_file(self, path: str) -> str:
        """Liest eine Datei aus der Sandbox."""
        return self._safe(path).read_text(encoding="utf-8", errors="replace")

    def write_file(self, path: str, content: str) -> str:
        """Schreibt Text in eine Datei (legt Ordner an)."""
        p = self._safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"{len(content)} Zeichen nach {path} geschrieben."

    def edit_file(self, path: str, old: str, new: str) -> str:
        """Ersetzt das (eindeutige) Vorkommen von `old` durch `new` in einer Datei."""
        p = self._safe(path)
        text = p.read_text(encoding="utf-8")
        count = text.count(old)
        if count == 0:
            return f"ERROR: '{old[:50]}…' nicht in {path} gefunden."
        if count > 1:
            return f"ERROR: '{old[:50]}…' kommt {count}× vor — bitte eindeutiger machen."
        p.write_text(text.replace(old, new), encoding="utf-8")
        return f"{path} geändert."

    def run_shell(self, command: str) -> str:
        """Führt einen Shell-Befehl in der Sandbox aus (stdout/stderr zurück)."""
        if self.approval and not self._approve(command):
            return "ABGELEHNT vom Benutzer."
        if os.name == "nt":
            argv = ["powershell", "-NoProfile", "-Command", command]
        else:
            argv = ["bash", "-c", command]
        try:
            r = subprocess.run(argv, cwd=self.workspace, capture_output=True,
                               text=True, timeout=self.shell_timeout)
        except subprocess.TimeoutExpired:
            return f"ERROR: Timeout nach {self.shell_timeout}s."
        out = f"exit={r.returncode}\n--- STDOUT ---\n{r.stdout}\n--- STDERR ---\n{r.stderr}"
        return out[:4000]

    def register(self, registry, only: Optional[Sequence[str]] = None) -> "CodingTools":
        """Registriert die Coding-Tools in `registry`.

        `only` beschränkt auf die genannten Tool-Namen (z. B. `READ_ONLY_TOOLS`
        für eine read-only-Sub-Agenten-Rolle); None = alle Tools.
        """
        def add(name, *args):
            if only is None or name in only:
                registry.add(name, *args)

        add("list_files", "Listet Dateien in einem Verzeichnis der Sandbox.",
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": []},
            self.list_files)
        add("glob_files", "Findet Dateien per Glob-Muster (z. B. '**/*.py'). Read-only, keine Rückfrage.",
            {"type": "object", "properties": {
                "pattern": {"type": "string", "description": "Glob-Muster, z. B. '**/*.py' oder 'src/*.ts'."},
                "path": {"type": "string", "description": "Startverzeichnis (Default '.')."}},
             "required": ["pattern"]},
            self.glob_files)
        add("grep", "Durchsucht Dateiinhalte per Regex und gibt 'pfad:zeile: text' zurück. Read-only.",
            {"type": "object", "properties": {
                "pattern": {"type": "string", "description": "Regex-Suchmuster."},
                "path": {"type": "string", "description": "Startverzeichnis (Default '.')."},
                "glob": {"type": "string", "description": "Auf diese Dateien beschränken, z. B. '**/*.py'."}},
             "required": ["pattern"]},
            self.grep)
        add("read_file", "Liest eine Datei aus der Sandbox.",
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            self.read_file)
        add("write_file", "Schreibt Text in eine Datei in der Sandbox.",
            {"type": "object", "properties": {
                "path": {"type": "string"}, "content": {"type": "string"}},
             "required": ["path", "content"]},
            self.write_file)
        add("edit_file", "Ersetzt einen eindeutigen Textabschnitt in einer Datei.",
            {"type": "object", "properties": {
                "path": {"type": "string"},
                "old": {"type": "string", "description": "Zu ersetzender Text (eindeutig)."},
                "new": {"type": "string", "description": "Neuer Text."}},
             "required": ["path", "old", "new"]},
            self.edit_file)
        add("run_shell", "Führt einen Shell-Befehl in der Sandbox aus (z. B. 'python ...', 'pytest').",
            {"type": "object", "properties": {"command": {"type": "string"}},
             "required": ["command"]},
            self.run_shell)
        return self


def coding_tools(registry=None, workspace: str = "./agent_workspace",
                 approval: bool = True, approve: Optional[Callable[[str], bool]] = None):
    """Bequemer Helfer: registriert die Coding-Tools in einer (neuen) ToolRegistry."""
    from .tools import ToolRegistry
    registry = registry or ToolRegistry()
    CodingTools(workspace=workspace, approval=approval, approve=approve).register(registry)
    return registry
