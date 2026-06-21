#!/usr/bin/env bash
#
# Baut eine eigenständige agentkit-Executable aus dem Python-Paket (PyInstaller).
# Ergebnis: agent_framework/dist/agentkit  (eine Datei, ohne Python-Installation lauffähig).
#
# Voraussetzung: Python 3.10+ und pip. Das Skript installiert pyinstaller + agentkit
# in die aktuelle (virtuelle) Umgebung.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY_DIR="$REPO_ROOT/agent_framework"

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python

echo "» Installiere PyInstaller + agentkit (Editable)…"
"$PY" -m pip install --quiet --upgrade pyinstaller
"$PY" -m pip install --quiet -e "$PY_DIR"

echo "» Baue eigenständige Executable mit PyInstaller…"
cd "$PY_DIR"
"$PY" -m PyInstaller \
    --onefile \
    --name agentkit \
    --clean \
    --noconfirm \
    pyinstaller_entry.py

echo "✓ Fertig: $PY_DIR/dist/agentkit"
echo "  Test:  $PY_DIR/dist/agentkit --demo \"Was ist 17 + 25?\""
