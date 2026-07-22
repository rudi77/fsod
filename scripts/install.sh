#!/usr/bin/env bash
#
# agentkit-Installer für Linux/macOS — Python-Paket.
#
# Installiert das Python-Paket `agentkit` (Console-Script) via pipx oder pip.
# Siehe ../INSTALL.md.
#
# Den nativen Rust-Build gibt es im Repo rudi77/agentkit_rs — dort liegen auch
# fertige Windows-/Linux-Binaries an jedem Release.
#
# Aufruf:
#   ./scripts/install.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY_DIR="$REPO_ROOT/agent_framework"

info()  { printf '\033[1;34m»\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m! \033[0m%s\n' "$*" >&2; }
err()   { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; }
ok()    { printf '\033[1;32m✓\033[0m %s\n' "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

if have pipx; then
    info "Installiere Python-agentkit via pipx…"
    pipx install --force "$PY_DIR"
    ok "Python-agentkit via pipx installiert (Console-Script 'agentkit')."
elif have pip || have pip3; then
    pip_cmd="$(command -v pip3 || command -v pip)"
    warn "pipx nicht gefunden — nutze '$pip_cmd install --user'."
    "$pip_cmd" install --user "$PY_DIR"
    ok "Python-agentkit via pip --user installiert (Console-Script 'agentkit')."
    warn "Liegt das User-bin-Verzeichnis im PATH (z. B. ~/.local/bin)?"
else
    err "Weder pipx noch pip gefunden. Python 3.10+ mit pip installieren."
    exit 1
fi

ok "Fertig. Test:  agentkit --demo \"Was ist 17 + 25?\""
