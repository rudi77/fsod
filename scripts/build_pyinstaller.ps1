<#
.SYNOPSIS
    Baut eine eigenständige agentkit-Executable aus dem Python-Paket (PyInstaller).

.DESCRIPTION
    Ergebnis: agent_framework\dist\agentkit.exe — eine Datei, ohne Python-Installation
    lauffähig. Voraussetzung: Python 3.10+ und pip.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PyDir    = Join-Path $RepoRoot 'agent_framework'

$Py = if ($env:PYTHON) { $env:PYTHON } else { 'python' }

Write-Host "» Installiere PyInstaller + agentkit (Editable)…" -ForegroundColor Cyan
& $Py -m pip install --quiet --upgrade pyinstaller
& $Py -m pip install --quiet -e $PyDir

Write-Host "» Baue eigenständige Executable mit PyInstaller…" -ForegroundColor Cyan
Push-Location $PyDir
try {
    & $Py -m PyInstaller --onefile --name agentkit --clean --noconfirm pyinstaller_entry.py
} finally {
    Pop-Location
}

Write-Host "✓ Fertig: $PyDir\dist\agentkit.exe" -ForegroundColor Green
Write-Host '  Test:  .\agent_framework\dist\agentkit.exe --demo "Was ist 17 + 25?"'
