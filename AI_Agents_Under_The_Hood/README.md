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

## MCP-Notebooks (Aufbau-Reihenfolge)

Zwei aufeinander aufbauende Notebooks zeigen, wie **derselbe Agentic Loop** seine Tools statt aus lokalem Code über das **Model Context Protocol (MCP)** bezieht — erst direkt, dann über ein **Gateway**.

| # | Notebook | Inhalt | Voraussetzung |
|---|---|---|---|
| 1 | `AI_Agents_MCP.ipynb` | Tools von einem **echten MCP-Server** (eigener Prozess, JSON-RPC über **stdio**) — `list_tools()` / `call_tool()` | nur `.env` (Azure OpenAI) |
| 2 | `AI_Agents_MCP_Gateway.ipynb` | Mehrere Server hinter **einem** Endpoint: **LiteLLM** als MCP-Gateway, Transport **streamable-http**, Auth per API-Key, Tool-**Namespacing** (`demo-add`) | zusätzlich **Docker Desktop** |

Reihenfolge: erst Notebook 1 (MCP-Grundlagen), dann Notebook 2 (Gateway). Beide teilen sich die Tool-Definitionen in **`mcp_demo_server.py`**.

### Gateway-Infrastruktur (Docker Compose)

Notebook 2 startet die Infrastruktur **deklarativ** — kein Prozess-Management mehr im Notebook:

| Datei | Rolle |
|---|---|
| `docker-compose.yml` | startet `demo-mcp` (unser Server) + `litellm` (Gateway) + `db` (Postgres) in einem Netz |
| `Dockerfile.mcp` | Mini-Image: Python + `mcp`-SDK + Server-Dateien |
| `litellm_config.yaml` | registriert den Demo-Server als Upstream (`http://demo-mcp:8000/mcp`), setzt den `master_key` |
| `mcp_http_server.py` | exponiert dieselben Tools über streamable-http |

Im Compose-Netz erreicht LiteLLM den Demo-Server über den **Service-Namen** `demo-mcp` — kein `host.docker.internal`, kein Port-Mapping für den Demo-Server. Nur das Gateway ist auf `localhost:4000` sichtbar.

Die Zellen in Notebook 2 rufen die Compose-Befehle selbst auf; von Hand geht es so:

```powershell
docker compose up -d --build     # db + demo-mcp + litellm hochfahren (erster Start baut/zieht Images)
docker compose ps                # Status
# ... Notebook 2 ausführen: verbindet auf http://localhost:4000/mcp ...
docker compose down              # alle Container stoppen + entfernen, :4000 freigeben
```


**ms365 mpc server login**

```powershell
docker run --rm -it -e MS365_MCP_TENANT_ID=common -e ` 
 MS365_MCP_TOKEN_CACHE_PATH=/data/ms365/.token-cache.json -e `
 MS365_MCP_SELECTED_ACCOUNT_PATH=/data/ms365/.selected-account.json -v `
 ai_agents_under_the_hood_ms365_token:/data/ms365 --entrypoint ms-365-mcp-server `
 ai_agents_under_the_hood-litellm:latest --login --preset mail --org-mode
```

> ⚠️ Dieser `--login` ist nur ein **Single-User-Bootstrap** (ein geteiltes Token im Volume) für die lokale Demo. Für den **Mehrbenutzerbetrieb** in der Firma (jeder mit eigenem Postfach, eigene Entra-App, delegierte Scopes, OAuth/OBO) — inkl. des Szenarios **mehrerer** Entra-gestützter MCP-Server — siehe **[docs/entra-app-registration.md](docs/entra-app-registration.md)**.

**Admin-UI (optional):** http://localhost:4000/ui — Login `admin` / `sk-1234`. Dafür ist der `db`-Service (Postgres) da: Die UI speichert User/Keys/Logs in der DB (sonst `Not connected to DB!` beim Login). Für den reinen MCP-Tool-Zugriff über `x-litellm-api-key` braucht man die UI **nicht** — `db` ist nur fürs UI/Key-Management nötig.

> 🪟 **Windows/Jupyter:** Beide Notebooks führen die MCP-Aufrufe in einem eigenen Thread mit `ProactorEventLoop` aus (`run_async`) — nötig, damit Subprozesse/Streams unabhängig von Jupyters Event-Loop laufen.

## Skills-Notebook (Agent + `SKILL.md`)

`AI_Agents_Skills.ipynb` zeigt das **Agent-Skills-Muster** *from scratch*: Statt alle Anweisungen fest im Prompt zu haben, **entdeckt** und **lädt** der Agent Skills bei Bedarf (*progressive disclosure*).

| Begriff | Bedeutung |
|---|---|
| **Skill** | Ordner mit einer `SKILL.md` — Frontmatter (`name`/`description`) + ausführliche Anleitung |
| **Discovery** | `list_skills()` liefert nur die Beschreibungen (klein, immer im Kontext) |
| **Laden** | `read_skill(name)` holt die ganze Anleitung — nur wenn der Skill passt |
| **`CLAUDE.md`** | immer geladener Einstieg + verbindliche Regeln |

Als Demo läuft das Notebook gegen das **TuttiPaletti**-Repo (BTK-Palettenklärung): der Agent nutzt dieselben Skills wie Claude Code / Cowork, lokal über `test-mails/` statt Gmail, und schreibt `fall-log/`- und `drafts/`-Dateien — **immer nur als Vorschlag**. Voraussetzung: nur `.env` (Azure OpenAI); `ROOT` im Notebook zeigt auf das TuttiPaletti-Repo (anpassbar).

> Tools/MCP = **Fähigkeiten** (was der Agent *tun* kann), Skills = **Wissen/Vorgehen** (*wie* er es tut). Es bleibt **derselbe Agent-Loop** wie in den anderen Notebooks.

## Parallel-&-Sub-Agents-Notebook (`AI_Agents_Parallel_SubAgents.ipynb`)

Zeigt zwei Skalierungsmuster *from scratch* — beide bauen auf **demselben** `run_agent`-Loop auf:

| Muster | Idee |
|---|---|
| **Parallele Tool-Calls** | Das Modell liefert **mehrere** `tool_calls` in *einer* Antwort. Ein `ThreadPoolExecutor` führt die Batch **nebenläufig** aus statt nacheinander. |
| **Sub-Agents als Tool** | Ein **Orchestrator** hat das Tool `delegate(auftrag)`. Jeder Aufruf startet einen eigenständigen Agent-Loop (eigener Kontext, eigene Tools) und gibt nur das **Ergebnis** zurück — Kontext-Isolation + Spezialisierung (Supervisor / Map-Reduce). |

Die Demo (nur `.env` nötig, kein Internet) nutzt drei „langsame" Tools (`wetter`/`einwohner`/`zeitzone`, je simulierte Latenz) und vergleicht **seriell vs. parallel** mit gestoppter Wanduhr. Der Orchestrator delegiert dann drei Städte an drei Sub-Agenten **parallel**, wobei jeder Sub-Agent seine Tools wiederum parallel ruft — die verschränkten `[sub:...]`-Trace-Zeilen sind der sichtbare Beweis der Nebenläufigkeit.

> ⚠️ Nur **nebenläufigkeitssichere** Tools parallel ausführen (Reads/Lookups). Schreibende Tools mit geteiltem Zustand brauchen Locks oder serielle Ausführung. Der `AzureOpenAI`-Client ist thread-safe, daher dürfen mehrere Sub-Agenten gleichzeitig `llm()` rufen.

## Streaming-&-Event-Queue-Notebook (`AI_Agents_Streaming_EventQueue.ipynb`)

Zeigt *from scratch*, wie **derselbe** Agentic Loop in Echtzeit arbeitet — **streamend** und über eine **Event-Queue** entkoppelt. Bisher war der Loop blockierend (man sieht erst nach jedem fertigen Schritt etwas) und verarbeitete genau einen Auftrag pro Aufruf. Zwei Bausteine ändern das:

| Baustein | Idee |
|---|---|
| **Streaming** | `stream=True` liefert die Antwort **Token für Token** statt am Stück → bessere UX (*time-to-first-token*). Der einzige Trick: fragmentierte **Tool-Call-Deltas pro `index` zusammensetzen** (`accumulate_stream`). |
| **Auftrags-Queue** (Input) | Der Agent läuft als **Worker-Thread** und holt sich neue Aufträge **selbst** aus einer `queue.Queue` (skaliert zu mehreren Workern). |
| **Event-Bus** (Output, Pub/Sub) | Der Loop `publish`-t neutrale, typisierte `AgentEvent`s (Token, Tool-Call, Ergebnis, finale Antwort). **Mehrere Consumer** abonnieren denselben Strom: ein **UI-Renderer** (live) + ein **Metrik-Consumer** (zählt parallel). |
| **Stop-Knopf** | Ein laufender Auftrag lässt sich **mittendrin abbrechen** — ein `threading.Event` als Cancel-Signal, das der Loop an sicheren Punkten (Schritt-Grenze, Token-Stream, vor jedem Tool) prüft: **kooperatives Abbrechen** statt Hard-Kill, wie der Stop-Knopf bei ChatGPT/Claude. |

Kernbotschaft: „Streaming" und „Event-Queue" sind keine Framework-Magie, sondern ein **Producer/Consumer-Muster** um denselben Loop — es entkoppelt *was passiert* (der Loop) von *wie es angezeigt wird* (die Consumer). Voraussetzung: nur `.env` (Azure OpenAI), kein Internet.

> 🧵 Nebenläufigkeit über `threading` + `queue.Queue` (wie in den MCP-/Parallel-Notebooks): Der blockierende `stream=True`-Call lebt natürlich im Worker-Thread, mehrere Consumer sind einfach weitere Threads. Thread-sicheres Drucken über `vprint`/Lock.

## Notebook neu bauen

Inhalt liegt editierbar in `notebook_source.txt` (Zell-Marker `<<<MD>>>` / `<<<CODE>>>`).
Nach Änderungen:

```powershell
uv run python build_notebook.py   # erzeugt das .ipynb neu + prüft Syntax aller Code-Zellen
```
