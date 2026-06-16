# AI Agents under the Hood — Vortrags-Notebook

Ein Agent *from scratch* in einem Jupyter-Notebook — als roter Faden für einen 60-Min-Vortrag.
Derselbe Agentic Loop wächst kapitelweise bis zu einem lauffähigen **Coding-Agent** (schreiben → ausführen → testen → committen).

## Schnellstart

Das Projekt nutzt **[uv](https://docs.astral.sh/uv/)** und `pyproject.toml`. Ein einziges Skript richtet alles ein:

```powershell
.\setup.ps1
```

Das Skript installiert bei Bedarf uv, erstellt die `.venv`, synchronisiert alle Abhängigkeiten (`uv sync`), registriert einen Jupyter-Kernel und legt eine `.env` aus der Vorlage an.

Danach:

```powershell
# .env mit deinen Azure-OpenAI-Werten füllen, dann:
uv run jupyter lab
```

Notebook: **`AI_Agents_under_the_Hood.ipynb`** — von oben nach unten ausführen.
In VS Code als Kernel **„AI Agents under the Hood (.venv)"** wählen.

### Manuell (ohne setup.ps1)

```powershell
uv sync                       # erstellt .venv + installiert Abhängigkeiten
Copy-Item .env.example .env   # dann mit Azure-OpenAI-Werten füllen
uv run jupyter lab
```

## Konfiguration (`.env`)

| Variable | Bedeutung |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | z. B. `https://<ressource>.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | API-Key der Azure-OpenAI-Ressource |
| `AZURE_OPENAI_DEPLOYMENT` | Name deines Deployments (nicht der Modellname) |
| `AZURE_OPENAI_API_VERSION` | Default `2024-10-21` |

## Notebook-Struktur (= Vortrags-Kapitel)

| Kap. | Thema | Was live passiert |
|---|---|---|
| 0 | Setup | Client steht |
| 1 | Das nackte LLM | Text rein/raus, Halluzination |
| 2 | Memory | `messages[]` als Gedächtnis |
| 3 | Tools | `tool_call` statt Text, manuelle Runde |
| 4 | Agentic Loop | `run_agent()` — *das* ist der Agent |
| 5 | ReAct & Planning | Reasoning + Plan-and-Execute |
| 6 | Coding-Tools | Sandbox + Approval, write/run/test |
| 7 | Context Engineering | Tokens zählen, truncation, compaction |
| 8 | Harness Engineering | `run_agent_v2`: max_steps, retries, fehlertolerant |
| 9 | MCP | Tools als Protokoll (Mini-Stub) |
| 10 | Finale | Coding-Agent baut + testet FizzBuzz, git commit |

## Demo-Hinweise für den Vortrag

- **Approval:** `run_shell` fragt vor jeder Ausführung per `input()` (`j/N`). Für Tempo in der Live-Demo in Kapitel 6 `APPROVAL = False` setzen — aber kurz erklären, *warum* die Schranke existiert (Harness!).
- **Sandbox:** Alles landet in `./agent_workspace` (in `.gitignore`). Vor einer frischen Demo einfach löschen.
- **Nichtdeterminismus:** Das Modell wählt Tools selbst; Schritte können variieren. Das ist ein Feature, kein Bug — gut, um „der Agent entscheidet" zu zeigen.
- **`push`** ist in Kapitel 10 bewusst auskommentiert (braucht Remote + Auth).
- **Zeitbudget:** Kapitel 3–4 sind der Aha-Moment — dort Ruhe lassen. Kapitel 7–9 notfalls straffen.

## Notebook neu bauen

Inhalt liegt editierbar in `notebook_source.txt` (Zell-Marker `<<<MD>>>` / `<<<CODE>>>`).
Nach Änderungen:

```powershell
uv run python build_notebook.py   # erzeugt das .ipynb neu + prüft Syntax aller Code-Zellen
```
