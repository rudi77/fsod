<#
.SYNOPSIS
Startet die ctxman-API auf :5291 mit echtem Azure-OpenAI-Compaction-Backend für das Notebook.

.DESCRIPTION
Liest die Azure-OpenAI-Credentials aus der .env dieses Ordners und setzt sie als
Compaction-Konfiguration (Provider=azure_openai) per Umgebungsvariable — der Key landet
also NICHT in einer eingecheckten Datei. Stoppt eine eventuell laufende Instanz auf Port 5291
und startet die API neu (blockierend, Logs sichtbar — wie ein Service-Fenster).

Voraussetzung: Postgres für ctxman läuft bereits (z. B. Container `ctxman-pg` aus start-dev.ps1)
und das Schema existiert. Dieses Skript verwaltet nur die API.

.EXAMPLE
./start-ctxman-azure-compaction.ps1
#>
param([int]$Port = 5291, [string]$CtxRoot = "C:\Users\rudi\source\ctxman")

$ErrorActionPreference = "Stop"
$envFile = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envFile)) { throw ".env nicht gefunden: $envFile" }

# .env einlesen
$kv = @{}
Get-Content $envFile | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
    $i = $_.IndexOf('='); $kv[$_.Substring(0, $i).Trim()] = $_.Substring($i + 1).Trim()
}
foreach ($k in 'AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_DEPLOYMENT', 'AZURE_OPENAI_API_VERSION') {
    if ([string]::IsNullOrWhiteSpace($kv[$k])) { throw "Fehlt in .env: $k" }
}

# laufende Instanz auf $Port stoppen (inkl. dotnet-run-Elternprozess)
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
        taskkill /PID $_ /T /F *> $null
        Write-Host "  -> bestehende Instanz (PID $_) gestoppt" -ForegroundColor DarkGray
    }
Start-Sleep -Seconds 2

# Compaction-Backend per Env (Key bleibt aus eingecheckten Dateien heraus)
$env:Compaction__Provider                = "azure_openai"
$env:Compaction__AzureOpenAi__Endpoint   = $kv['AZURE_OPENAI_ENDPOINT']
$env:Compaction__AzureOpenAi__ApiKey     = $kv['AZURE_OPENAI_API_KEY']
$env:Compaction__AzureOpenAi__Deployment = $kv['AZURE_OPENAI_DEPLOYMENT']
$env:Compaction__AzureOpenAi__ApiVersion = $kv['AZURE_OPENAI_API_VERSION']

Write-Host "Starte ctxman auf http://localhost:$Port  (Compaction: azure_openai / $($kv['AZURE_OPENAI_DEPLOYMENT']))" -ForegroundColor Cyan
Write-Host "Abbrechen mit Strg+C. (Dieses Fenster ist das Service-Log.)" -ForegroundColor DarkGray
dotnet run --project "$CtxRoot\src\Ctxman.Api" --no-launch-profile --urls "http://localhost:$Port"
