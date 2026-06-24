# -*- coding: utf-8 -*-
"""Baut das kombinierte Notebook AI_Agents_MCP_und_Gateway.ipynb aus
AI_Agents_MCP.ipynb (Teil 1, stdio) + AI_Agents_MCP_Gateway.ipynb (Teil 2, LiteLLM).

Folgt der Dramaturgie der Praesentation 'MCP & MCP Gateway (Infografik Edition)'.
Der MCP-Server-Code wird beim Bauen aus mcp_demo_server.py eingelesen, damit er
1:1 identisch zum bestehenden Setup bleibt.
"""
import io, json

OUT = "AI_Agents_MCP_und_Gateway.ipynb"
SERVER_SRC = io.open("mcp_demo_server.py", encoding="utf-8").read().rstrip("\n")

cells = []

def md(text):
    cells.append(("md", text.strip("\n")))

def code(text):
    cells.append(("code", text.strip("\n")))


# ===================================================================== TITEL
md(r"""
# 🔌 MCP & MCP-Gateway — die Essenz in zwei Beispielen

### Wie kommen KI-Agenten an Tools? — Standardisierung und Skalierung

**Das Problem:** Ein Agent soll Tools nutzen (GitHub, Datenbanken, Dateien, …). Bindet man jede API einzeln an, braucht *jedes* Tool eigene Anbindung, eigene Auth, eigenes SDK, eigene Fehlerbehandlung. **N Tools = N Integrationen** — der Agent wird immer komplexer.

**Die Lösung — MCP:** Das **Model Context Protocol** (offener Standard, Anthropic 2024) ist der „USB-C"-Stecker für KI-Agenten: *ein* Protokoll für alle Tools. Es ist komplett offen, basiert auf **JSON-RPC** und ist **transportunabhängig**.

- **Tool Discovery:** *Was kann ich tun?* (`tools/list`)
- **Tool Execution:** *Mach das für mich!* (`tools/call`)

```
   Agent  →  MCP Client  →  MCP Server  →  Tool / API / DB
                (JSON-RPC)        (API Call)
```

Dieses Notebook zeigt MCP in **zwei kleinen, lauffähigen Beispielen**:

| | Was passiert | Transport |
|---|---|---|
| **Teil 1 · Direktes MCP** | Agent spricht *direkt* mit **einem** MCP-Server | `stdio` (Subprozess) |
| **Teil 2 · MCP-Gateway** | Agent spricht mit **einem** Gateway, das *viele* Server bündelt | `streamable-http` (Netzwerk) |

Der Agent-Loop bleibt in beiden Teilen **derselbe** — es ändert sich nur, **wohin** und **womit** er sich verbindet. Wer das Protokoll im Detail verstehen will (JSON-RPC, Handshake, Transporte): siehe **Appendix** am Ende.
""")


# ================================================================== SETUP (0)
md(r"""
## 0 · Setup

`llm()` ist unser **einziger Draht zum Modell** (Azure OpenAI aus der `.env`). Dazu ein paar Helfer, die **beide Teile** gemeinsam nutzen.

Voraussetzungen:
- das offizielle **`mcp`**-SDK (`uv sync`) — für Teil 1 **und** Teil 2
- **Docker Desktop** — nur für Teil 2 (das Gateway)

> 🪟 **Windows/Jupyter-Trick (`run_async`):** Jupyters Event-Loop kann keine Subprozesse starten. Wir führen die MCP-Arbeit deshalb in einem eigenen Thread mit eigenem `ProactorEventLoop` aus — für stdio wie http.
""")

code(r'''
import os, sys, json, asyncio, threading, subprocess, time, urllib.request
from pathlib import Path
from openai import AzureOpenAI
from dotenv import load_dotenv

# MCP-SDK: beide Transporte – stdio (Teil 1) und streamable-http (Teil 2)
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()

client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
)
DEPLOYMENT = os.environ["AZURE_OPENAI_DEPLOYMENT"]

def llm(messages, tools=None, tool_choice="auto"):
    """Unser einziger Draht zum Modell - identisch in beiden Teilen."""
    kwargs = dict(model=DEPLOYMENT, messages=messages)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice
    return client.chat.completions.create(**kwargs)

def run_async(coro_factory):
    """Async-Funktion in eigenem Event-Loop in eigenem Thread ausfuehren.
    Auf Windows ein ProactorEventLoop, damit Subprozesse (MCP-Server) starten koennen -
    unabhaengig von Jupyters SelectorEventLoop im Hauptthread."""
    box = {}
    def worker():
        loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            box["v"] = loop.run_until_complete(coro_factory())
        except BaseException as e:
            box["e"] = e
        finally:
            loop.close()
    t = threading.Thread(target=worker, daemon=True)
    t.start(); t.join()
    if "e" in box:
        raise box["e"]
    return box["v"]

def to_openai_tools(mcp_tools):
    """MCP-Tool-Schema -> OpenAI-Tool-Format (das inputSchema IST bereits ein JSON-Schema)."""
    return [{"type": "function", "function": {
        "name": t.name,
        "description": t.description or "",
        "parameters": t.inputSchema or {"type": "object", "properties": {}},
    }} for t in mcp_tools]

def _mcp_text(result):
    """MCP-Tool-Ergebnis -> Text fuers Modell."""
    parts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
    return "\n".join(parts) if parts else str(result.content)

# Server-stderr in den Nullspeicher leiten (Jupyters sys.stderr hat kein echtes fileno()).
_ERRLOG = open(os.devnull, "w")

print("Setup bereit. Deployment:", DEPLOYMENT)
''')


# ============================================== TEIL 1 — DIREKTES MCP (stdio)
md(r"""
# Teil 1 · Direktes MCP — die lokale Verbindung

Die einfachste Architektur: Der Agent (als **MCP-Client**) startet **einen** MCP-Server als Subprozess und spricht über `stdio` mit ihm:

```
  Agent
    │  (stdio)
  MCP Server
```

Genau so verbinden sich auch Claude Desktop, Cursor & Co. mit lokalen MCP-Servern. Das Entscheidende: Das Tool ist **kein** Stück Python im Agenten mehr, sondern lebt in einem **separaten Prozess** — sein Schema kommt per `list_tools()` **vom Server**, die Ausführung läuft per `call_tool()` **über das Protokoll**.
""")

md(r"""
## 1.1 · Der MCP-Server — ein echtes Programm in eigenem Prozess

Ein MCP-Server ist ein eigenständiges Programm. Wir schreiben es mit dem offiziellen **`mcp`-SDK** (FastMCP) in die Datei `mcp_demo_server.py`. Es stellt drei Tools bereit, die ein LLM allein *nicht* zuverlässig kann: die **Live-Serverzeit**, **Arithmetik** und eine kleine **Wissensdatenbank** (deine Daten — nur auf dem Server).

> Dieselbe Datei nutzen wir in **Teil 2** unverändert weiter — dort nur über HTTP statt stdio exponiert.
""")

code("%%writefile mcp_demo_server.py\n" + SERVER_SRC)

md(r"""
## 1.2 · Verbinden — der MCP-Lifecycle in drei Schritten

Der Client startet den Server als **Subprozess** und spricht über stdio mit ihm. Der Ablauf ist immer derselbe — genau das sehen wir gleich im Code:

| Schritt | Methode | Bedeutung |
|---|---|---|
| 1. | `initialize()` | **Fähigkeiten aushandeln** (Handshake) |
| 2. | `list_tools()` | **Tool Discovery** — *Was kann ich tun?* |
| 3. | `call_tool(name, args)` | **Tool Execution** — *Mach das für mich!* |

Die Tool-Schemas kommen dabei **nicht** von uns, sondern **vom Server**. (Wie diese Schritte als JSON-RPC-Nachrichten aussehen: siehe Appendix.)
""")

code(r'''
# So startet ein MCP-Client einen Server: ein Befehl + Argumente. Mehr nicht.
SERVER = StdioServerParameters(command=sys.executable, args=["mcp_demo_server.py"])

# Tools vom Server abfragen - die Schemas kommen NICHT von uns, sondern vom Server.
async def _list_tools():
    async with stdio_client(SERVER, errlog=_ERRLOG) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()          # 1. Protokoll-Handshake
            return (await session.list_tools()).tools   # 2. Tool Discovery

server_tools = run_async(_list_tools)
for t in server_tools:
    print(f"🔌 {t.name}: {t.description}")

add_tool = next(t for t in server_tools if t.name == "add")
print("\nBeispiel-Schema (add):", json.dumps(add_tool.inputSchema, ensure_ascii=False))
''')

APPENDIX_MD = r"""
# Appendix · Das Protokoll genauer — JSON-RPC, Handshake & Transportunabhängigkeit

In den beiden Teilen haben wir drei Methoden benutzt (`initialize`, `list_tools`, `call_tool`). Hier der Blick hinter die Kulissen: was MCP eigentlich *ist* — und warum *derselbe* Client-Code mit lokalem Server **und** Gateway funktioniert.

### Das Fundament: JSON-RPC 2.0

MCP definiert **kein** neues Wire-Format — es nutzt das etablierte **JSON-RPC 2.0**. Jede Nachricht ist ein JSON-Objekt eines von drei Typen:

**Request** (erwartet eine Antwort, hat eine `id`):
```json
{ "jsonrpc": "2.0", "id": 1, "method": "tools/call",
  "params": { "name": "add", "arguments": { "a": 17, "b": 25 } } }
```
**Response** (Antwort auf genau diese `id` — entweder `result` oder `error`):
```json
{ "jsonrpc": "2.0", "id": 1,
  "result": { "content": [ { "type": "text", "text": "42.0" } ] } }
```
**Notification** (Einbahn, **keine** `id`, keine Antwort — z. B. „meine Tool-Liste hat sich geändert"):
```json
{ "jsonrpc": "2.0", "method": "notifications/tools/list_changed" }
```

Mehr ist es im Kern nicht: strukturierte Nachrichten mit `method` + `params`, korreliert über die `id`. `session.call_tool("add", {...})` aus unserem Code wird genau zum `tools/call`-Request oben — das SDK verpackt/entpackt nur das JSON für uns.

### Der Handshake: `initialize` + Capability-Negotiation

`initialize()` ist mehr als ein „Hallo" — Client und Server **handeln ihre Fähigkeiten aus**, damit keiner etwas annimmt, das die Gegenseite nicht kann. Dreischritt:

**1. Client → Server (`initialize` Request):** „Ich spreche MCP-Version X, kann *diese* Dinge, heiße *so*."
```json
{ "jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18",
    "capabilities": { "roots": {}, "sampling": {} },
    "clientInfo": { "name": "mcp-demo-client", "version": "1.0" } } }
```
**2. Server → Client (Response):** „Einverstanden, Version X. *Ich* biete an: `tools`, `resources`, `prompts` …"
```json
{ "jsonrpc": "2.0", "id": 0, "result": {
    "protocolVersion": "2025-06-18",
    "capabilities": { "tools": { "listChanged": true }, "resources": {}, "prompts": {} },
    "serverInfo": { "name": "demo-knowledge-server", "version": "1.x" } } }
```
**3. Client → Server (`notifications/initialized` Notification):** „Verstanden, los geht's." — ab jetzt ist die Sitzung in der **Operationsphase**.

Warum dieser Aufwand? **Versions- und Feature-Sicherheit.** Der Client fragt z. B. `tools/list` nur, wenn der Server die `tools`-Capability gemeldet hat. Neue Protokoll-Features brechen alte Implementierungen nicht — man einigt sich auf den kleinsten gemeinsamen Nenner. Das ist der Grund, warum *derselbe* Client-Code (unser `run_async`-Block) mit unserem Demo-Server **und** mit dem Filesystem-Server **und** mit dem LiteLLM-Gateway in Teil 2 funktioniert: alle handeln im `initialize` aus, was sie können.

### Die Lebensphasen einer Sitzung

```
  1. Initialization   initialize  →  ←  Antwort  →  notifications/initialized
  2. Operation        tools/list, tools/call, resources/read, prompts/get, ...
  3. Shutdown         Transport schließen (bei stdio: Subprozess beenden)
```

In der Operationsphase stellt ein Server bis zu drei **Primitive** bereit:
- **Tools** — Aktionen, die der Agent ausführen lässt (`tools/list`, `tools/call`) — *unser* Fall.
- **Resources** — lesbare Daten/Kontext, vom Client adressiert (`resources/list`, `resources/read`).
- **Prompts** — vordefinierte, parametrisierbare Prompt-Vorlagen (`prompts/list`, `prompts/get`).

### Warum „transportunabhängig"?

JSON-RPC beschreibt nur die **Nachrichten** — *nicht*, wie die Bytes von A nach B kommen. Den Bytetransport übernimmt eine austauschbare **Transport-Schicht**. MCP standardisiert dafür zwei:

| Transport | Wie | Wofür | In diesem Notebook |
|---|---|---|---|
| **stdio** | Client startet den Server als Subprozess, schreibt Requests auf `stdin`, liest Responses von `stdout` (eine JSON-Nachricht pro Zeile) | lokal, 1 Server, Desktop-Tools | **Teil 1** |
| **Streamable HTTP** | Requests per HTTP-POST, Server-Antworten/Notifications optional als SSE-Stream | über Netzwerk, mehrere Clients, Gateways | **Teil 2** |

Entscheidend: **Die JSON-RPC-Nachrichten sind in beiden Fällen Byte-für-Byte dieselben.** `initialize`, `tools/list`, `tools/call` sehen identisch aus — nur das Rohr darunter wechselt. Genau deshalb müssen wir beim Sprung zum Gateway in Teil 2 **nur eine Zeile** ändern (`stdio_client(...)` → `streamablehttp_client(...)`); der gesamte restliche Agent-Loop bleibt unberührt.

> **Die Kernidee:** MCP = JSON-RPC-Nachrichten + ausgehandelte Fähigkeiten + austauschbarer Transport. Offen, weil die Spezifikation öffentlich ist; transportunabhängig, weil das Protokoll die Bytes nicht kennt.
"""

md(r"""
## 1.3 · MCP-Schema → OpenAI-Tool-Format

Das `inputSchema` eines MCP-Tools **ist** bereits ein JSON-Schema — es passt direkt in das `parameters`-Feld, das die OpenAI-/Azure-API erwartet. Eine triviale Umwandlung (`to_openai_tools`, oben im Setup), kein Mapping-Aufwand. Genau dafür gibt es einen Standard.
""")

code(r'''
OPENAI_TOOLS = to_openai_tools(server_tools)
print(json.dumps(next(x for x in OPENAI_TOOLS if x["function"]["name"] == "add"),
                 indent=2, ensure_ascii=False))
''')

md(r"""
## 1.4 · Der Agent — der Loop, Tools über MCP

Jetzt der Kern: ein ganz normaler Agentic Loop (fragen → Tool ausführen → Ergebnis anhängen → erneut fragen). Nur zwei Stellen sind MCP-spezifisch — markiert mit `# <- MCP`:
- die Tool-Schemas kommen per `list_tools()` vom Server,
- die Ausführung läuft über `await session.call_tool(name, args)` statt eines lokalen Funktionsaufrufs.

Der ganze Lauf passiert in einer offenen MCP-Session (im `run_async`-Thread) und wird danach sauber geschlossen.
""")

code(r'''
async def _run_mcp_agent(task, max_steps=8, verbose=True):
    async with stdio_client(SERVER, errlog=_ERRLOG) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = to_openai_tools((await session.list_tools()).tools)   # <- MCP: Schemas vom Server

            messages = [{"role": "user", "content": task}]
            for step in range(1, max_steps + 1):
                msg = llm(messages, tools=tools).choices[0].message

                a = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    a["tool_calls"] = [{"id": tc.id, "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls]
                messages.append(a)

                if not msg.tool_calls:
                    if verbose: print(f"[Schritt {step}] ✓ finale Antwort")
                    return msg.content

                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments or "{}")
                    if verbose: print(f"[Schritt {step}] → MCP call_tool {tc.function.name}({args})")
                    result = await session.call_tool(tc.function.name, args)   # <- MCP: Ausfuehrung ueber das Protokoll
                    text = _mcp_text(result)
                    if verbose: print(f"            ⤷ {text[:90]}")
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
            return "(max_steps erreicht)"

def run_mcp_agent(task, **kw):
    """Synchroner Wrapper - startet den Agentenlauf im Proactor-Thread."""
    return run_async(lambda: _run_mcp_agent(task, **kw))

answer = run_mcp_agent(
    "Wie spaet ist es laut Server? Rechne ausserdem 17+25, "
    "und was weiss die Wissensdatenbank ueber MCP?"
)
print("\n=== Ergebnis ===\n", answer)
''')

md(r"""
👉 Drei MCP-Tool-Aufrufe, eine saubere Antwort. **Das ist der ganze Wert von MCP:** ein ganz normaler Agent-Loop, aber die Werkzeuge stecken in einem austauschbaren Server-Prozess.
""")

md(r"""
## 1.5 · Interaktiv (optional) — frag den Agenten selbst, mit Gedächtnis

Jetzt **du**: Die Zelle fragt in einer Schleife nach Eingaben und schickt sie an den MCP-Agenten. Wir führen eine Historie `chat_messages`, die über *alle* Fragen wächst — so funktionieren **Folgefragen** wie *„und addiere 10 dazu"*.

> Probier eine Kette: *„Addiere 128 und 96"* → *„und das mal 2?"* → *„Was weiß die Wissensdatenbank über Agenten?"*
> `reset` löscht das Gedächtnis, leere Eingabe oder `exit` beendet.
""")

code(r'''
chat_messages = []   # <- Gedaechtnis: waechst mit jeder Frage + Antwort

async def _chat_turn(messages, max_steps=8):
    """Beantwortet EINE Nutzerfrage - auf Basis der GESAMTEN bisherigen Historie."""
    async with stdio_client(SERVER, errlog=_ERRLOG) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = to_openai_tools((await session.list_tools()).tools)
            for step in range(1, max_steps + 1):
                msg = llm(messages, tools=tools).choices[0].message
                a = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    a["tool_calls"] = [{"id": tc.id, "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls]
                messages.append(a)
                if not msg.tool_calls:
                    return msg.content
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments or "{}")
                    print(f"   → MCP call_tool {tc.function.name}({args})")
                    result = await session.call_tool(tc.function.name, args)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": _mcp_text(result)})
            return "(max_steps erreicht)"

print("MCP-Agent mit Gedaechtnis bereit. ('reset' loescht, leer/'exit' beendet.)\n")
while True:
    frage = input("🙋 Deine Frage (oder 'exit'): ").strip()
    if not frage or frage.lower() in ("exit", "quit", "ende"):
        print("Beendet."); break
    if frage.lower() == "reset":
        chat_messages.clear(); print("Gedaechtnis geloescht.\n"); continue
    chat_messages.append({"role": "user", "content": frage})
    antwort = run_async(lambda: _chat_turn(chat_messages))
    print("\n🤖", antwort, "\n")
''')


# ===================================== TEIL 2 — MCP-GATEWAY MIT LITELLM (http)
md(r"""
# Teil 2 · Das MCP-Gateway mit LiteLLM — die Produktionsarchitektur

**Wenn ein Server nicht mehr reicht:** In der Praxis hast du schnell *viele* MCP-Server (A, B, C, D) — einen für die Datenbank, einen für GitHub, einen fürs Filesystem … Jeden einzeln zu verbinden und abzusichern bringt erneut Probleme: zu viele Verbindungen, separate Authentifizierungen und fehlende Governance.

**Die Lösung: Gateway-Architektur.** Ein **MCP-Gateway** ist eine zentrale Vermittlungs- und Routing-Schicht zwischen Clients und vielen Servern:

```
  Agent
    │  (HTTP)
  LiteLLM Gateway
    │
    ├── Server A   ├── Server B   └── Server C
```

Es liefert:
- **Routing & Discovery:** zentrale Werkzeug-Verwaltung
- **Authentifizierung:** Single Point of Control
- **Zugriffskontrolle & Governance:** *Wer darf was?*
- **Monitoring & Aggregation:** zentrale Übersicht

Wir setzen das mit dem **[LiteLLM-Proxy](https://docs.litellm.ai/docs/mcp)** als Gateway um. **Der Loop bleibt derselbe** wie in Teil 1 — es wechselt nur **Transport** und **Ziel**:

| Teil 1 (direkt) | Teil 2 (über LiteLLM) |
|---|---|
| Client → **direkt** zum Server | Client → **LiteLLM** → Server |
| Transport: **stdio** (Subprozess) | Transport: **streamable-http** (Netzwerk) |
| Keine Auth | **API-Key** (`x-litellm-api-key`) |
| Tool heißt `add` | Tool heißt `demo-add` (Alias-**Präfix**) |
| 1 Server pro Verbindung | **n Server** hinter *einem* Endpoint |

![image](images/mcp_gateway.png)

```
  Notebook (MCP-Client)
       │  streamable-http  +  x-litellm-api-key
       ▼
  ┌─────────────────── docker compose ───────────────────┐
  │  litellm  (:4000)  ── MCP-Gateway ──►  demo-mcp (:8000)│
  │     /mcp                                 unsere Tools  │
  └───────────────────────────────────────────────────────┘
```
""")

md(r"""
## 2.1 · Die Infrastruktur als Code

Statt im Notebook Prozesse zu starten, beschreiben wir die Infrastruktur **deklarativ** in ein paar kleinen Dateien:

| Datei | Rolle |
|---|---|
| `mcp_http_server.py` | startet **dieselben** Tools wie in Teil 1 über **streamable-http** (nur Transport-Wechsel) |
| `Dockerfile.mcp` | packt Python + `mcp`-SDK + unsere Server-Dateien in ein winziges Image |
| `litellm_config.yaml` | registriert den Demo-Server als Upstream (`url: http://demo-mcp:8000/mcp`) und setzt den `master_key` |
| `docker-compose.yml` | startet die Services `demo-mcp` + `litellm` (+ `db`) in **einem** Netz |

Der Clou: Im Compose-Netz erreicht LiteLLM den Demo-Server einfach über den **Service-Namen** `demo-mcp` — kein `host.docker.internal`, kein Port-Mapping für den Demo-Server nötig. Nur das Gateway (`:4000`) ist vom Host (= Notebook) aus sichtbar.

> 🖥️ **Admin-UI (optional):** Unter **http://localhost:4000/ui** (Login `admin` / `sk-1234`) zeigt LiteLLM eine UI für Keys, Teams, Logs und die registrierten MCP-Server. Für den reinen Tool-Zugriff in diesem Notebook brauchst du sie **nicht**.

Werfen wir kurz einen Blick auf die zentralen Dateien:
""")

code(r'''
print("=== docker-compose.yml ===\n")
print(Path("docker-compose.yml").read_text(encoding="utf-8"))
print("=== litellm_config.yaml (der Upstream) ===\n")
print(Path("litellm_config.yaml").read_text(encoding="utf-8"))
''')

md(r"""
## 2.2 · Gateway starten — `docker compose up`

Eine Zeile fährt **alle** Container hoch (`db`, `demo-mcp`, `litellm`). Die Zelle wartet anschließend, bis das Gateway über `/health/readiness` antwortet.

> ⏳ Der **erste** Start baut das Mini-Image und zieht die LiteLLM-/Postgres-Images (~mehrere hundert MB) — das kann ein paar Minuten dauern. Danach geht es schnell.
""")

code(r'''
GATEWAY_URL     = "http://localhost:4000/mcp"
GATEWAY_HEADERS = {"x-litellm-api-key": "Bearer sk-1234"}   # = master_key aus litellm_config.yaml

def _ready():
    try:
        with urllib.request.urlopen("http://localhost:4000/health/readiness", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False

def _wait(cond, what, timeout=300, every=2):
    start = time.time()
    while time.time() - start < timeout:
        if cond():
            print(f"✓ {what} bereit"); return True
        time.sleep(every)
    print(f"✗ {what} nicht bereit nach {timeout}s"); return False

# Defensive: evtl. alten Standalone-Container entfernen (haelt sonst :4000).
subprocess.run(["docker", "rm", "-f", "litellm-mcp-gateway"],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("Starte das Gateway via docker compose ... (erster Start baut/zieht die Images)")
up = subprocess.run(["docker", "compose", "up", "-d", "--build"], capture_output=True, text=True)
print(up.stdout.strip() or up.stderr.strip())

_wait(_ready, "LiteLLM-Gateway (:4000)", timeout=300)
print("\n--- Status ---")
print(subprocess.run(["docker", "compose", "ps"], capture_output=True, text=True).stdout)
''')

md(r"""
## 2.3 · Verbinden — derselbe Client, neuer Transport

Statt `stdio_client(...)` benutzen wir `streamablehttp_client(url, headers=...)` aus dem **gleichen** `mcp`-SDK. Alles danach — `ClientSession`, `initialize()`, `list_tools()`, `call_tool()` — ist **identisch** zu Teil 1. Den `master_key` schicken wir als `x-litellm-api-key` mit.

Achte auf die **Tool-Namen**: Das Gateway präfixt sie mit dem Server-Alias (`demo-…`). Unser Agent-Loop ist davon **nicht** betroffen, weil er die Namen aus `list_tools()` **entdeckt** statt sie hart zu kodieren.
""")

code(r'''
async def _gw_list():
    async with streamablehttp_client(GATEWAY_URL, headers=GATEWAY_HEADERS) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()                 # gleicher Handshake
            return (await session.list_tools()).tools  # gleiche Discovery - jetzt vom Gateway

gateway_tools = run_async(_gw_list)
print("Tools über das LiteLLM-Gateway (Alias-Präfix 'demo-'):")
for t in gateway_tools:
    print(f"  🔌 {t.name}: {t.description}")

GATEWAY_OPENAI_TOOLS = to_openai_tools(gateway_tools)
print("\nBeispiel-Schema:", json.dumps(GATEWAY_OPENAI_TOOLS[0]["function"], ensure_ascii=False)[:200], "...")
''')

md(r"""
## 2.4 · Der Agent — Zeile für Zeile derselbe Loop, jetzt über das Gateway

**Dieselbe** Schleife wie in Teil 1. Die zwei markierten Stellen sind identisch — nur die Verbindung läuft über `streamablehttp_client` zu LiteLLM. `session.call_tool(name, args)` ruft das Tool über das Gateway auf, LiteLLM reicht es an den `demo`-Upstream weiter.
""")

code(r'''
async def _run_gateway_agent(task, max_steps=8, verbose=True):
    async with streamablehttp_client(GATEWAY_URL, headers=GATEWAY_HEADERS) as (read, write, _):  # <- Gateway statt stdio
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = to_openai_tools((await session.list_tools()).tools)   # <- Gateway: Schemas vom Proxy

            messages = [{"role": "user", "content": task}]
            for step in range(1, max_steps + 1):
                msg = llm(messages, tools=tools).choices[0].message

                a = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    a["tool_calls"] = [{"id": tc.id, "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls]
                messages.append(a)

                if not msg.tool_calls:
                    if verbose: print(f"[Schritt {step}] ✓ finale Antwort")
                    return msg.content

                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments or "{}")
                    if verbose: print(f"[Schritt {step}] → Gateway call_tool {tc.function.name}({args})")
                    result = await session.call_tool(tc.function.name, args)   # <- Gateway: Ausfuehrung ueber LiteLLM
                    text = _mcp_text(result)
                    if verbose: print(f"            ⤷ {text[:90]}")
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
            return "(max_steps erreicht)"

def run_gateway_agent(task, **kw):
    return run_async(lambda: _run_gateway_agent(task, **kw))

answer = run_gateway_agent(
    "Wie spaet ist es laut Server? Rechne ausserdem 17+25, "
    "und was weiss die Wissensdatenbank ueber MCP?"
)
print("\n=== Ergebnis (über das LiteLLM-Gateway) ===\n", answer)
''')

md(r"""
## 2.5 · Interaktiv (optional) — frag den Gateway-Agenten, mit Gedächtnis

Wie in Teil 1: eine Historie, die über alle Fragen wächst — die Tools kommen jetzt über das Gateway. Je nach `litellm_config.yaml` stehen hier auch Tools weiterer Upstream-Server bereit (z. B. `ms365-…`).

> Probier: *„Addiere 128 und 96"* → *„und das mal 2?"* → *„Was weiß die Wissensdatenbank über Agenten?"*
> `reset` löscht das Gedächtnis, leere Eingabe oder `exit` beendet.
""")

code(r'''
chat_messages = []   # <- frisches Gedaechtnis fuer den Gateway-Agenten

async def _gw_chat_turn(messages, max_steps=8):
    async with streamablehttp_client(GATEWAY_URL, headers=GATEWAY_HEADERS) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = to_openai_tools((await session.list_tools()).tools)
            for step in range(1, max_steps + 1):
                msg = llm(messages, tools=tools).choices[0].message
                a = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    a["tool_calls"] = [{"id": tc.id, "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls]
                messages.append(a)
                if not msg.tool_calls:
                    return msg.content
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments or "{}")
                    print(f"   → Gateway call_tool {tc.function.name}({args})")
                    result = await session.call_tool(tc.function.name, args)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": _mcp_text(result)})
            return "(max_steps erreicht)"

print("Gateway-Agent mit Gedaechtnis bereit. ('reset' loescht, leer/'exit' beendet.)\n")
while True:
    frage = input("🙋 Deine Frage (oder 'exit'): ").strip()
    if not frage or frage.lower() in ("exit", "quit", "ende"):
        print("Beendet."); break
    if frage.lower() == "reset":
        chat_messages.clear(); print("Gedaechtnis geloescht.\n"); continue
    chat_messages.append({"role": "user", "content": frage})
    antwort = run_async(lambda: _gw_chat_turn(chat_messages))
    print("\n🤖", antwort, "\n")
''')

md(r"""
## 2.6 · Aufräumen — `docker compose down`

Alle Container (`db`, `demo-mcp`, `litellm`) stoppen und entfernen — Port `:4000` wird wieder frei. (Die DB liegt in einem Named Volume und bleibt erhalten; mit `docker compose down -v` würdest du auch die Daten löschen.)
""")

code(r'''
res = subprocess.run(["docker", "compose", "down"], capture_output=True, text=True)
print(res.stdout.strip() or res.stderr.strip() or "down")
''')


# ===================================================== VERGLEICH & MITNEHMEN
md(r"""
# Vergleich der Ansätze & Fazit

| Kriterium | Direktes MCP (Teil 1) | MCP Gateway (Teil 2) |
|---|---|---|
| **Komplexität** | Einfach | Skalierbar |
| **Tool-Anzahl** | Wenige Tools | Viele Tools |
| **Umgebung** | Lokal / Desktop | Enterprise / Cloud |
| **Sicherheit** | Keine Governance | Zentrale Kontrolle |

> **Fazit:** MCP standardisiert den Zugriff auf **Tools**. MCP-Gateways standardisieren den Zugriff auf **viele MCP-Server**.

## Mitnehmen

1. **MCP ändert nichts am Agenten.** Derselbe Loop — die Tools kommen nur aus einem anderen Prozess. **Discovery statt Hardcoding:** `list_tools()` liefert die Schemas, `call_tool()` führt aus — über JSON-RPC.
2. **Ein Server, viele Clients:** denselben Server nutzen Claude Desktop, Cursor und deine eigene App.
3. **Vom Server zum Gateway:** Wird es mehr als ein Server, wechselt nur **Transport** (stdio → streamable-http) und **Ziel** (Server → LiteLLM). Der Loop bleibt.
4. **Ein Endpoint für n Server.** Neue Server = ein Eintrag in `mcp_servers` der `litellm_config.yaml`, kein Client-Code. Namespacing inklusive (`demo-add`).
5. **Zentrale Governance.** Auth per `x-litellm-api-key`, dazu Zugriff pro Key/Team, Rate-Limits, Logging, Budgets — an *einer* Stelle.
6. **Infrastruktur als Code.** `docker-compose.yml` ersetzt das Prozess-Management: reproduzierbar, ein Befehl rauf/runter.

> **Bonus:** LiteLLM ist primär ein **LLM-Gateway**. In der Praxis liegen damit *LLM-Zugriff* **und** *MCP-Tools* hinter demselben Tor — ein einziger Kontrollpunkt für deine Agenten-Infrastruktur.
""")


# =================================================================== APPENDIX
md(APPENDIX_MD)


# ============================================================ NOTEBOOK BAUEN
nb_cells = []
errors = 0
for i, (ctype, text) in enumerate(cells):
    src_lines = text.splitlines(keepends=True)
    if ctype == "md":
        nb_cells.append({"cell_type": "markdown", "metadata": {}, "source": src_lines})
    else:
        # Syntaxpruefung (ohne %%writefile-Magic)
        if not text.lstrip().startswith("%%"):
            try:
                compile(text, f"<cell {i}>", "exec")
            except SyntaxError as e:
                errors += 1
                print(f"SYNTAXFEHLER in Zelle {i}: {e}")
        nb_cells.append({"cell_type": "code", "metadata": {}, "execution_count": None,
                         "outputs": [], "source": src_lines})

nb = {
    "cells": nb_cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3", "version": "3.13.1"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
json.dump(nb, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

md_n = sum(1 for c in nb_cells if c["cell_type"] == "markdown")
code_n = sum(1 for c in nb_cells if c["cell_type"] == "code")
print(f"OK -> {OUT}: {len(nb_cells)} Zellen ({md_n} Markdown, {code_n} Code), Syntaxfehler: {errors}")
