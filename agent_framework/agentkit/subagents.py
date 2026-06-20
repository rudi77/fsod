"""Sub-Agents — ein Agent als Tool eines anderen.

Muster aus dem Notebook: Ein **Orchestrator** bekommt ein `delegate`-Tool. Jeder
Aufruf startet einen eigenständigen Agent-Loop (eigener Kontext, eigene Tools)
und gibt nur das **Ergebnis** zurück — Kontext-Isolation + Spezialisierung.

Zusammen mit `parallel_tools=True` laufen mehrere `delegate`-Aufrufe aus EINER
Orchestrator-Antwort nebenläufig (Map-Reduce / Supervisor).
"""

from __future__ import annotations

from typing import Optional

from .tools import ToolRegistry


def add_subagent(registry: ToolRegistry, name: str, description: str, llm,
                 tools: Optional[ToolRegistry] = None, system: Optional[str] = None,
                 strategy: str = "react", max_steps: int = 12,
                 param_name: str = "auftrag", param_desc: str = "Der Teilauftrag in Worten.",
                 parallel_tools: bool = True, bus=None) -> ToolRegistry:
    """Registriert einen Sub-Agenten als Tool im `registry` des Orchestrators.

    Jeder Aufruf erzeugt einen FRISCHEN Agent (eigenes Kurzzeitgedächtnis) und
    gibt dessen finale Antwort als Text zurück. Thread-safe, weil der
    OpenAI/Azure-Client thread-safe ist und jeder Sub-Agent eigenen State hat.

    Wird ein `bus` (EventBus) übergeben, werden ALLE Events des Sub-Agenten dorthin
    weitergeleitet — getaggt mit `source="<name>:<auftrag>"`, damit Consumer die
    (auch parallel laufenden) Sub-Agenten auseinanderhalten können.
    """
    # spät importieren -> kein Zirkelimport (agent.py nutzt nichts von hier)
    from .agent import Agent

    def _delegate(**kwargs):
        task = kwargs.get(param_name, "")
        sub = Agent(llm, tools=tools or ToolRegistry(), system=system,
                    strategy=strategy, max_steps=max_steps, parallel_tools=parallel_tools)
        if bus is None:
            return sub.run(task)
        # Event-Forwarding: Sub-Agent-Events laufen in den geteilten Bus.
        source = f"{name}:{' '.join(task.split())[:24]}"
        return sub.run_on_bus(task, bus, source=source)

    registry.add(
        name, description,
        {"type": "object",
         "properties": {param_name: {"type": "string", "description": param_desc}},
         "required": [param_name]},
        _delegate,
    )
    return registry
