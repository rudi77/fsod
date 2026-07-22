# agentkit installieren (Python)

`agentkit` lässt sich als **Python-Paket** installieren und stellt den Befehl `agentkit`
bereit (One-shot und REPL).

> **Rust-Build gesucht?** Die native Executable (kleiner, schneller, mit Terminal-UI,
> `read-pdf` und `ctxman`-Context-Management) ist in ein eigenes Repo umgezogen:
> **[rudi77/agentkit_rs](https://github.com/rudi77/agentkit_rs)** — fertige
> Windows-/Linux-Binaries hängen dort an jedem Release, das Setup-Skript für Windows
> inklusive. Anleitung:
> [agentkit_rs/INSTALL.md](https://github.com/rudi77/agentkit_rs/blob/main/INSTALL.md).

> Ohne API-Key läuft ein eingebauter, netzfreier **Demo-Modus** — sofort nach der
> Installation nutzbar. Für ein echtes Modell setzt du `OPENAI_API_KEY` (optional
> `OPENAI_MODEL`) oder die `AZURE_OPENAI_*`-Variablen.

```bash
agentkit "Was ist 17 + 25?"     # One-shot: Auftrag ausführen, Antwort streamen
agentkit --repl                 # interaktiver Zeilen-REPL (Gedächtnis bleibt erhalten)
agentkit --demo "3 + 4"         # Demo-Modus erzwingen (kein Netz/Key nötig)
agentkit --help
```

## Install-Skript

**Linux / macOS**

```bash
./scripts/install.sh
```

**Windows (PowerShell)**

```powershell
.\scripts\install.ps1
```

## Manuell: pipx / pip

Voraussetzung: Python 3.10+.

```bash
# Empfohlen: isoliert via pipx
pipx install ./agent_framework

# Alternativ: in die aktuelle Umgebung
pip install ./agent_framework

# Ohne Installation testen
python -m agentkit --demo "Was ist 17 + 25?"
```

## Eigenständige Executable (PyInstaller)

Erzeugt **eine Datei**, die ganz ohne Python-Installation läuft (z. B. zum Weitergeben).

```bash
# Linux/macOS
./scripts/build_pyinstaller.sh          # -> agent_framework/dist/agentkit
```

```powershell
# Windows
.\scripts\build_pyinstaller.ps1         # -> agent_framework\dist\agentkit.exe
```

## Konfiguration

Die Python-CLI liest ihre Zugangsdaten aus Umgebungsvariablen; eine `.env`-Datei im
Arbeitsverzeichnis wird geladen, falls `python-dotenv` installiert ist (Vorlage:
[`agent_framework/.env.example`](agent_framework/.env.example)).

| Variable | Bedeutung |
|---|---|
| `AZURE_OPENAI_API_KEY`      | aktiviert den Azure-Pfad |
| `AZURE_OPENAI_ENDPOINT`     | Azure-Endpoint |
| `AZURE_OPENAI_DEPLOYMENT`   | Azure-Deployment-Name |
| `AZURE_OPENAI_API_VERSION`  | optional (Default `2024-10-21`) |
| `OPENAI_API_KEY`            | aktiviert den OpenAI-Pfad |
| `OPENAI_MODEL`              | Modellname (Default `gpt-4o-mini`) |
