"""Beispiel 9 — Coding-Agent mit dem `task`-Tool (Sub-Agenten im Claude-Code-Stil).

Der Orchestrator ist ein normaler Coding-Agent, bekommt aber zusätzlich EIN Tool —
`task` —, mit dem er Teilaufgaben an eigenständige Sub-Agenten delegiert. Der
Parameter `subagent_type` wählt die Rolle:

- explorer (read-only): erkundet das Repo und fasst zusammen
- reviewer (read-only): begutachtet Code/Diff kritisch
- tester: führt Tests aus und berichtet
- general: beliebige abgegrenzte Teilaufgabe (voller Coding-Zugriff)

Ruft das Modell mehrere `task`-Tools in EINER Antwort auf, laufen sie parallel —
ihre Trace-Zeilen erscheinen im Konsum verschränkt, getaggt mit ihrer `source`.

    python examples/09_coding_subagents.py
"""
import threading
from pathlib import Path

from dotenv import load_dotenv

from agentkit import (Agent, CodingTools, EventBus, ToolRegistry, add_task_tool,
                      azure_from_env)
from agentkit.coding import CODING_SYSTEM
from agentkit.events import DONE, STEP, TEXT_DELTA, TOOL_CALL, TOOL_RESULT
from agentkit.roles import SUBAGENT_SYSTEM

load_dotenv()

# Workspace = das agentkit-Paket selbst, damit der Explorer echten Code findet.
WORKSPACE = str(Path(__file__).resolve().parent.parent / "agentkit")


def consumer(q):
    """Rendert den verschränkten Event-Strom; pro Zeile die source des Agenten.
    Stoppt erst beim Root-DONE (source == '')."""
    while True:
        ev = q.get()
        who = (ev.source or "ORCH").split(":", 1)[0]
        if ev.type == STEP:
            print(f"[{who}] Schritt {ev.data['step']}", flush=True)
        elif ev.type == TOOL_CALL:
            print(f"[{who}]   🔧 {ev.data['name']}({list(ev.data['args'].values())})"[:120], flush=True)
        elif ev.type == TOOL_RESULT:
            print(f"[{who}]   👁  {ev.data['result'][:80]}", flush=True)
        elif ev.type == TEXT_DELTA and not ev.source:
            print(ev.data, end="", flush=True)  # nur der Orchestrator streamt Text
        elif ev.type == DONE and ev.source == "":
            return


if __name__ == "__main__":
    llm = azure_from_env()
    bus = EventBus()
    q = bus.subscribe()

    # Orchestrator: Coding-Tools (read-only reichen hier) + Sub-Agent-Hinweis im Prompt.
    tools = ToolRegistry()
    CodingTools(workspace=WORKSPACE, approval=False).register(tools)
    orchestrator = Agent(llm, tools=tools,
                         system=CODING_SYSTEM + "\n\n" + SUBAGENT_SYSTEM,
                         strategy="plan", parallel_tools=True)

    # Das `task`-Tool an den Orchestrator hängen (liest dessen Lauf-Bus zur Laufzeit).
    add_task_tool(tools, agent=orchestrator, llm=llm, workspace=WORKSPACE, approval=False)

    ui = threading.Thread(target=consumer, args=(q,), daemon=True)
    ui.start()

    auftrag = (
        "Verschaffe dir einen Überblick über das agentkit-Paket: Delegiere parallel "
        "(in DERSELBEN Antwort) einen 'explorer'-Auftrag (Architektur/Module) und einen "
        "'reviewer'-Auftrag (begutachte agent.py). Fasse beides danach zu einem kurzen "
        "Architektur- und Qualitätsbericht zusammen."
    )
    bericht = orchestrator.run_on_bus(auftrag, bus, source="")
    ui.join()
    print("\n\n=== Abschlussbericht ===\n")
    print(bericht)
