# fsod

Begleitmaterial zu **„AI Agents under the Hood"** — ein ganz einfaches Agent-Framework
(`agentkit`) in Python plus die Notebooks, aus denen es destilliert ist.

| Ordner | Inhalt |
|---|---|
| [`agent_framework`](agent_framework) | `agentkit` in **Python** — das Original-Framework |
| [`AI_Agents_Under_The_Hood`](AI_Agents_Under_The_Hood) | die Notebooks, aus denen das Framework destilliert ist |
| [`benchmarks`](benchmarks) | Performance-Vergleich Rust vs. Python |

> **Der Rust-Port ist umgezogen:** `agentkit` in Rust (inkl. TUI, `ctxman`-Context-Management
> und Benchmark-Harness) lebt jetzt in
> **[rudi77/agentkit_rs](https://github.com/rudi77/agentkit_rs)** — dort liegen auch die
> Releases mit fertigen Windows-/Linux-Binaries (ab v0.13.1) und die Beispiele
> (accounts_payable, pr_review, coding_swarm, …).

## agentkit (Python) installieren

Voraussetzung: Python 3.10+. Komplette Anleitung: **[INSTALL.md](INSTALL.md)**.

```bash
# Linux/macOS
./scripts/install.sh

# Windows (PowerShell)
.\scripts\install.ps1

# danach:
agentkit --demo "Was ist 17 + 25?"
```

Ohne API-Key läuft ein netzfreier Demo-Modus; für ein echtes Modell `OPENAI_API_KEY`
oder die `AZURE_OPENAI_*`-Variablen setzen (`.env` wird geladen, falls `python-dotenv`
installiert ist — siehe [`agent_framework/.env.example`](agent_framework/.env.example)).

Die fertige **Rust-Executable** (kleiner, schneller, mit TUI und `read-pdf`) gibt es
drüben: [agentkit_rs — INSTALL.md](https://github.com/rudi77/agentkit_rs/blob/main/INSTALL.md).
