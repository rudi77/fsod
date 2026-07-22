<#
.SYNOPSIS
    agentkit-Installer für Windows (PowerShell) — Python-Paket.

.DESCRIPTION
    Installiert das Python-Paket `agentkit` (Console-Script) via pipx oder pip.
    Siehe ..\INSTALL.md.

    Den nativen Rust-Build gibt es im Repo rudi77/agentkit_rs — dort liegen auch
    fertige Windows-/Linux-Binaries an jedem Release.

.EXAMPLE
    .\scripts\install.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PyDir    = Join-Path $RepoRoot 'agent_framework'

function Write-Info($m) { Write-Host "» $m" -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "✓ $m" -ForegroundColor Green }
function Write-Warn2($m){ Write-Host "! $m" -ForegroundColor Yellow }
function Have($cmd)     { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

if (Have 'pipx') {
    Write-Info "Installiere Python-agentkit via pipx…"
    pipx install --force $PyDir
    Write-Ok "Python-agentkit via pipx installiert (Console-Script 'agentkit')."
} elseif (Have 'pip') {
    Write-Warn2 "pipx nicht gefunden — nutze 'pip install --user'."
    pip install --user $PyDir
    Write-Ok "Python-agentkit via pip --user installiert (Console-Script 'agentkit')."
    Write-Warn2 "Liegt das Python-Scripts-Verzeichnis im PATH?"
} else {
    throw "Weder pipx noch pip gefunden. Python 3.10+ mit pip installieren."
}

Write-Ok 'Fertig. Test:  agentkit --demo "Was ist 17 + 25?"'
