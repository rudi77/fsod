# agentkit — ein ganz einfaches Agent-Framework

Destilliert aus den Notebooks in [`AI_Agents_Under_The_Hood`](../AI_Agents_Under_The_Hood).
Kernidee bleibt: **Ein Agent ist ein LLM in einer Schleife mit Tools.** Dieses Paket
macht die Bausteine aus dem Vortrag wiederverwendbar — **ohne unnötige Abstraktion**.

```
solange das Modell ein Tool aufruft:
    Tool ausführen -> Ergebnis anhängen -> Modell erneut fragen
sonst:
    finale Antwort
```

## Was drin ist

| Baustein | Datei | Inhalt |
|---|---|---|
| **Agentic Loop** | `agentkit/agent.py` | streamend & event-basiert; ReAct **und** Plan-and-Execute über `strategy=`; **parallele Tool-Calls**; Harness (max_steps, Retries, Fehlertoleranz, Compaction, Stop-Knopf) |
| **Tools** | `agentkit/tools.py` | `@registry.tool()` — Schema automatisch aus Typ-Hints + Docstring (oder explizit) |
| **Coding-Tools** | `agentkit/coding.py` | `CodingTools`: `list_files`/`read_file`/`write_file`/`edit_file`/`run_shell` mit Sandbox + Approval |
| **Planning** | `agentkit/planning.py` | `Plan` + `update_plan`-Tool — eine mitgeführte, sichtbare Todo-Liste |
| **Sub-Agents** | `agentkit/subagents.py` | `add_subagent()` — ein Agent als `delegate`-Tool eines Orchestrators (Kontext-Isolation, parallel) |
| **Events** | `agentkit/events.py` | typisierte `AgentEvent`s + `EventBus` (Pub/Sub, mehrere Consumer) |
| **Memory** | `agentkit/memory.py` | `ShortTermMemory` (Historie, Token-Budget, Compaction) + `LongTermMemory` (persistent, als `remember`/`recall`-Tools) |
| **MCP** | `agentkit/mcp.py` | `MCPClient` — persistente stdio-Session, Server-Tools in die Registry |
| **LLM** | `agentkit/llm.py` | dünne Hülle um Azure-OpenAI / OpenAI (`complete` + `stream`) |

Bewusst **keine** eigene Abstraktion über die OpenAI-Chunks: der Loop arbeitet direkt
mit dem Provider-Format. Das hält das Framework klein und kompatibel.

## Installation

```bash
cd agent_framework
pip install -e ".[all]"        # openai, dotenv, tiktoken, mcp, pytest
cp .env.example .env           # mit Azure-OpenAI-Werten füllen
```

Minimal reichen `openai` + `python-dotenv`; `tiktoken` (genaues Token-Zählen) und
`mcp` (MCP-Server) sind optionale Extras.

## In 10 Zeilen

```python
from agentkit import Agent, ToolRegistry, azure_from_env

tools = ToolRegistry()

@tools.tool()
def add(a: int, b: int) -> int:
    "Addiert zwei Zahlen."
    return a + b

agent = Agent(azure_from_env(), tools=tools, strategy="react")
print(agent.run("Was ist 17 + 25?"))
```

## ReAct vs. Plan-and-Execute

Derselbe Loop, nur der System-Prompt unterscheidet sich:

```python
Agent(llm, tools=tools, strategy="react")   # denke -> handle -> beobachte
Agent(llm, tools=tools, strategy="plan")    # erst Plan, dann abarbeiten
Agent(llm, tools=tools, strategy="plain")   # nur dein eigener system=-Prompt
```

Ein eigener `system="..."` wird an das Strategie-Preamble angehängt.

## Streaming & Events

`run_iter()` ist ein Generator, der `AgentEvent`s liefert — alles andere baut darauf auf:

```python
for ev in agent.run_iter("..."):
    if ev.type == "text_delta":
        print(ev.data, end="", flush=True)   # Token für Token
```

Für mehrere Consumer / Worker-Threads / einen Stop-Knopf gibt es den `EventBus`:

```python
import threading
from agentkit import EventBus

bus = EventBus()
ui_q = bus.subscribe()          # beliebig viele Subscriber
cancel = threading.Event()      # der Stop-Knopf
threading.Thread(target=agent.run_on_bus,
                 args=("Lange Aufgabe …",),
                 kwargs={"bus": bus, "cancel": cancel}, daemon=True).start()
# ... cancel.set() bricht kooperativ ab (Schritt-Grenze, Token-Stream, vor Tools)
```

## Memory

```python
from agentkit import Agent, LongTermMemory, azure_from_env

agent = Agent(azure_from_env(), long_term=LongTermMemory("agent_memory.jsonl"))
agent.run("Merke dir: mein Lieblingseditor ist Neovim.")  # nutzt remember-Tool
agent.run("Worum ging es gerade?")                          # Kurzzeit (gleiche Session)
# Langzeit überdauert den Prozess (JSONL-Datei) und ist via recall-Tool abrufbar.
```

`ShortTermMemory` misst das Token-Budget und komprimiert alte Historie automatisch,
wenn `token_budget` überschritten wird.

## Coding-Agent (Tools + Plan + Sandbox)

```python
from agentkit import Agent, CodingTools, Plan, ToolRegistry, CODING_SYSTEM, azure_from_env

tools = ToolRegistry()
CodingTools(workspace="./agent_workspace", approval=True).register(tools)  # write/edit/read/list/run_shell

plan = Plan()  # update_plan-Tool: mitgeführte Todo-Liste
agent = Agent(azure_from_env(), tools=tools, system=CODING_SYSTEM,
              strategy="plan", plan=plan)
agent.run("Schreibe fizzbuzz.py + pytest-Tests und mach sie grün.")
print(plan.render())
```

- **Sandbox**: alle Pfade werden in den Workspace eingesperrt; `run_shell` läuft dort.
- **Approval**: `run_shell` fragt vor jeder Ausführung (`approval=False` für Automatik,
  oder eigenen `approve=callback` übergeben).
- **`update_plan`**: das Modell schreibt seinen Plan als Schrittliste mit Status;
  ein `Plan(on_update=...)`-Callback macht ihn live sichtbar (z. B. als `PLAN`-Event).

## Parallele Tool-Calls & Sub-Agents

Liefert das Modell mehrere Tool-Calls in **einer** Antwort, führt der Agent sie
nebenläufig aus (`parallel_tools=True`, Default). Die Ergebnis-Reihenfolge bleibt
erhalten. Ein **Sub-Agent** ist ein eigenständiger Agent-Loop als Tool:

```python
from agentkit import Agent, ToolRegistry, add_subagent, azure_from_env

llm = azure_from_env()
orch_tools = ToolRegistry()
add_subagent(orch_tools, "delegate", "Delegiert einen Rechercheauftrag.",
             llm, tools=city_tools, system="Recherchiere genau eine Stadt.")

orchestrator = Agent(llm, tools=orch_tools, parallel_tools=True,
                     system="Rufe delegate für JEDE Stadt in DERSELBEN Antwort auf.")
print(orchestrator.run("Vergleiche Wien, Berlin und Tokio."))  # Sub-Agenten laufen parallel
```

### Event-Forwarding der Sub-Agents

Übergibt man `add_subagent(..., bus=bus)` einen `EventBus`, laufen **alle** Events
der Sub-Agenten in denselben Bus — getaggt mit `event.source` (z. B. `"delegate:Wien"`),
damit Consumer die (parallel laufenden) Sub-Agenten auseinanderhalten. So werden die
verschränkten Trace-Zeilen sichtbar:

```python
from agentkit import EventBus
from agentkit.events import DONE

bus = EventBus()
q = bus.subscribe()
add_subagent(orch_tools, "delegate", "...", llm, tools=city_tools,
             system="...", bus=bus)                 # <- Forwarding an
orchestrator = Agent(llm, tools=orch_tools, parallel_tools=True, system="...")

# in einem Consumer-Thread:
ev = q.get()
print(f"[{ev.source or 'ORCH'}] {ev.type}")          # source trennt Orchestrator/Sub-Agenten

orchestrator.run_on_bus("Vergleiche Wien, Berlin und Tokio.", bus, source="")
```

`event.source == ""` ist der Haupt-Agent. Jeder Sub-Agent schließt mit einem eigenen
`DONE` (mit seiner `source`); der Root-`DONE` trägt `source == ""` — daran erkennt ein
Consumer das endgültige Ende.

## MCP

```python
import sys
from agentkit import Agent, ToolRegistry, azure_from_env
from agentkit.mcp import MCPClient

tools = ToolRegistry()
mcp = MCPClient(command=sys.executable, args=["mcp_demo_server.py"]).connect()
mcp.register(tools)                       # Server-Tools in die Registry
agent = Agent(azure_from_env(), tools=tools)
...
mcp.close()
```

## Beispiele

| Datei | Zeigt |
|---|---|
| `examples/01_react_tools.py` | ReAct-Agent mit lokalen Tools, Live-Ausgabe |
| `examples/02_plan_and_execute.py` | dieselbe Aufgabe als Plan-and-Execute |
| `examples/03_streaming_events.py` | EventBus, zwei Consumer, Stop-Knopf |
| `examples/04_mcp.py` | Tools von einem MCP-Server |
| `examples/05_memory.py` | Kurzzeit- + Langzeitgedächtnis |
| `examples/06_coding_agent.py` | Coding-Tools + `update_plan` + Sandbox (FizzBuzz + Tests) |
| `examples/07_parallel_subagents.py` | parallele Tool-Calls + Sub-Agents (Map-Reduce) |

## Tests

```bash
pytest -q
```

Die Tests laufen **ohne Netz**: ein `FakeLLM` stellt OpenAI-Streaming-Chunks nach
und prüft Tools, Memory, Events, MCP-Konvertierung und den Agent-Loop end-to-end.
