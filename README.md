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
