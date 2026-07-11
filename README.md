# fsod

Begleitmaterial zu **„AI Agents under the Hood"** — ein ganz einfaches Agent-Framework
(`agentkit`) in zwei strukturgleichen Implementierungen plus Notebooks und Benchmarks.

| Ordner | Inhalt |
|---|---|
| [`agent_framework`](agent_framework) | `agentkit` in **Python** — das Original-Framework |
| [`agent_framework_rs`](agent_framework_rs) | `agentkit` als **Rust**-Port (1:1, inkl. TUI) |
| [`AI_Agents_Under_The_Hood`](AI_Agents_Under_The_Hood) | die Notebooks, aus denen das Framework destilliert ist |
| [`benchmarks`](benchmarks) | Performance-Vergleich Rust vs. Python |

## agentkit als Executable installieren

`agentkit` lässt sich als Kommandozeilen-/TUI-**Executable unter Windows und Linux**
installieren — als nativer Rust-Build oder als Python-Paket. Komplette Anleitung:
**[INSTALL.md](INSTALL.md)**.

```bash
# Linux/macOS — automatisch die passende Variante
./scripts/install.sh

# Windows (PowerShell)
.\scripts\install.ps1 rust

# danach:
agentkit --demo "Was ist 17 + 25?"
```

Ohne API-Key läuft ein netzfreier Demo-Modus; für ein echtes Modell `OPENAI_API_KEY`
oder die `AZURE_OPENAI_*`-Variablen setzen.

## agentkit als Unix-/PowerShell-Kommando

Die Rust-Executable ist ein vollwertiger, komponierbarer CLI-Filter: stdin = Kontext,
stdout = reines Resultat, stderr = Spur, definierte Exit-Codes — dazu `--flag=value`,
`--`-Separator, **Shell-Completions** (`agentkit completions bash|zsh|fish|powershell`)
und ein tokenfreies **`agentkit read-pdf`** (Feature `pdf`). Details:
**[agent_framework_rs/README.md](agent_framework_rs/README.md#unix-pipe-kompatibilität--agentkit-als-nativer-filter)**.

## Beispiel: Accounts-Payable-Prozess (E-Rechnung, GoBD, DATEV, Dublette)

Ein praxisnaher Eingangsrechnungs-Prozess für deutsche Kleinunternehmer/Freelancer, gebaut
als **komponierte PowerShell-Pipeline** aus einzelnen agentkit-Agenten — je ein Werkzeug pro
Schritt: Papier-PDF/**XRechnung**/**ZUGFeRD** einlesen, bei E-Rechnungen die
**EN-16931-Konformität** über die **xcheck-API** (separates Repo `rudi77/xcheck`) prüfen, §14-UStG-Merkmale
extrahieren, validieren, nach SKR03 verbuchen, **DATEV-Buchungsstapel** exportieren,
**GoBD-konform** (SHA-256-Manifest) ablegen und **Dubletten** erkennen.
Anleitung + Tests: **[examples/accounts_payable/README.md](agent_framework_rs/examples/accounts_payable/README.md)**.
