<#
    VORSCHLAG — NICHT AUTOMATISCH AUSGEFÜHRT.

    Erzeugt von einem agentkit-Agenten, der unter --dry-run lief: jedes verändernde
    Werkzeug (run_shell, write_file, edit_file) war für ihn ein No-Op. Dieses Skript ist
    die EINZIGE Art, wie seine Arbeit das System erreichen kann — und nur, wenn ein
    Mensch es liest und freigibt.

    Rechner:   SRV-WWS-01
    Erzeugt:   2026-07-11 18:39:09
    Risiko:    hoch — zuerst wird das 9,7-GB-Absturzabbild von C: nach D: archiviert; danach können PostgreSQL und der WWS-AppServer wieder gestartet werden. Kein Neustart vorgesehen, aber der Storage-/Treiberfehler bleibt als Ursache offen.

    PRÜFEN, DANN AUSFÜHREN:  .\Invoke-WinTriage.ps1 -Apply
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Write-Host 'Schritt 1: Speicherplatz durch Archivieren des Absturzabbilds freigeben'
$dump = 'C:\Windows\MEMORY.DMP'
$zielRoot = 'D:\dumps'
if (Test-Path -LiteralPath $dump) {
    New-Item -ItemType Directory -Force -Path $zielRoot | Out-Null
    $ziel = Join-Path $zielRoot ('MEMORY_{0}.DMP' -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
    if (-not (Test-Path -LiteralPath $ziel)) {
        Move-Item -LiteralPath $dump -Destination $ziel
        Write-Host "  Abbild nach $ziel verschoben."
    } else {
        Write-Host '  Ziel existiert bereits - Vorgang uebersprungen.'
    }
} else {
    Write-Host '  Kein MEMORY.DMP vorhanden - uebersprungen.'
}

Write-Host 'Schritt 2: PostgreSQL starten'
$pg = Get-Service -Name 'postgresql-x64-16' -ErrorAction SilentlyContinue
if ($null -ne $pg) {
    if ($pg.Status -ne 'Running') {
        Start-Service -Name 'postgresql-x64-16'
        Start-Sleep -Seconds 5
        (Get-Service -Name 'postgresql-x64-16').Status | ForEach-Object { Write-Host "  postgresql-x64-16: $_" }
    } else {
        Write-Host '  postgresql-x64-16 laeuft bereits.'
    }
} else {
    Write-Host '  Dienst postgresql-x64-16 nicht gefunden.'
}

Write-Host 'Schritt 3: WWS-AppServer starten'
$app = Get-Service -Name 'WWS-AppServer' -ErrorAction SilentlyContinue
if ($null -ne $app) {
    if ($app.Status -ne 'Running') {
        Start-Service -Name 'WWS-AppServer'
        Start-Sleep -Seconds 5
        (Get-Service -Name 'WWS-AppServer').Status | ForEach-Object { Write-Host "  WWS-AppServer: $_" }
    } else {
        Write-Host '  WWS-AppServer laeuft bereits.'
    }
} else {
    Write-Host '  Dienst WWS-AppServer nicht gefunden.'
}
