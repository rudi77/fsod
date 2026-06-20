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
| **Agentic Loop** | `agentkit/agent.py` | streamend & event-basiert; ReAct **und** Plan-and-Execute über `strategy=`; Harness (max_steps, Retries, Fehlertoleranz, Compaction, Stop-Knopf) |
| **Tools** | `agentkit/tools.py` | `@registry.tool()` — Schema automatisch aus Typ-Hints + Docstring (oder explizit) |
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

## Tests

```bash
pytest -q
```

Die Tests laufen **ohne Netz**: ein `FakeLLM` stellt OpenAI-Streaming-Chunks nach
und prüft Tools, Memory, Events, MCP-Konvertierung und den Agent-Loop end-to-end.
