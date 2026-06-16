#requires -Version 5.1
<#
.SYNOPSIS
    Erstellt und initialisiert die komplette Entwicklungsumgebung fuer das
    Vortrags-Notebook "AI Agents under the Hood" mit uv.

.DESCRIPTION
    - prueft/installiert uv (Astral)
    - erstellt die virtuelle Umgebung (.venv) und synchronisiert alle Abhaengigkeiten
      aus pyproject.toml (uv sync)
    - registriert einen Jupyter-Kernel fuer dieses Projekt
    - legt eine .env aus .env.example an (falls noch nicht vorhanden)

.EXAMPLE
    .\setup.ps1
#>

[CmdletBinding()]
param(
    [string]$KernelName = "ai-agents-hood",
    [string]$KernelDisplayName = "AI Agents under the Hood (.venv)"
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# 1) uv vorhanden? Sonst installieren.
Write-Step "Pruefe uv ..."
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv nicht gefunden - installiere uv (Astral) ..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    # uv landet in ~\.local\bin - fuer diese Session zum PATH hinzufuegen
    $uvBin = Join-Path $env:USERPROFILE ".local\bin"
    if (Test-Path $uvBin) { $env:Path = "$uvBin;$env:Path" }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv konnte nicht installiert werden. Bitte manuell installieren: https://docs.astral.sh/uv/"
    }
}
Write-Host ("uv: " + (uv --version)) -ForegroundColor Green

# 2) Virtuelle Umgebung + Abhaengigkeiten (erzeugt .venv aus pyproject.toml)
Write-Step "Erstelle .venv und synchronisiere Abhaengigkeiten (uv sync) ..."
uv sync
if ($LASTEXITCODE -ne 0) { throw "uv sync ist fehlgeschlagen." }

# 3) Jupyter-Kernel registrieren (zeigt auf die .venv)
Write-Step "Registriere Jupyter-Kernel '$KernelName' ..."
uv run python -m ipykernel install --user --name $KernelName --display-name "$KernelDisplayName"
if ($LASTEXITCODE -ne 0) { throw "Kernel-Registrierung ist fehlgeschlagen." }

# 4) .env aus Vorlage anlegen (nicht ueberschreiben)
Write-Step "Pruefe .env ..."
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env aus .env.example erstellt - bitte Azure-OpenAI-Werte eintragen!" -ForegroundColor Yellow
} else {
    Write-Host ".env existiert bereits - unveraendert gelassen." -ForegroundColor Green
}

Write-Host "`nFertig." -ForegroundColor Green
Write-Host "Naechste Schritte:" -ForegroundColor Cyan
Write-Host "  1) .env mit deinen Azure-OpenAI-Werten fuellen"
Write-Host "  2) Notebook starten:   uv run jupyter lab"
Write-Host "     (oder in VS Code das Notebook oeffnen und den Kernel '$KernelDisplayName' waehlen)"
