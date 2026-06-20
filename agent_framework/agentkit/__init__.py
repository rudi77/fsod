"""agentkit — ein ganz einfaches Agent-Framework aus den Notebook-Beispielen.

Ein Agent ist ein LLM in einer Schleife mit Tools. Dieses Paket bündelt die
Bausteine aus dem Vortrag "AI Agents under the Hood" zu wiederverwendbaren
Teilen — ohne unnötige Abstraktion:

    from agentkit import Agent, ToolRegistry, azure_from_env

    tools = ToolRegistry()

    @tools.tool()
    def add(a: int, b: int) -> int:
        "Addiert zwei Zahlen."
        return a + b

    agent = Agent(azure_from_env(), tools=tools, strategy="react")
    print(agent.run("Was ist 17 + 25?"))
"""

from .agent import Agent, PLAN_PREAMBLE, REACT_PREAMBLE, to_assistant_dict
from .events import (AgentEvent, CANCELLED, DONE, ERROR, EventBus, FINAL, STEP,
                     TEXT_DELTA, TOOL_CALL, TOOL_RESULT)
from .llm import LLM, azure_from_env, openai_from_env
from .memory import LongTermMemory, ShortTermMemory, count_tokens_text, truncate
from .tools import ToolRegistry

__all__ = [
    # Kern
    "Agent", "ToolRegistry", "LLM",
    # LLM-Helfer
    "azure_from_env", "openai_from_env",
    # Memory
    "ShortTermMemory", "LongTermMemory", "count_tokens_text", "truncate",
    # Events
    "AgentEvent", "EventBus",
    "STEP", "TEXT_DELTA", "TOOL_CALL", "TOOL_RESULT", "FINAL", "ERROR",
    "CANCELLED", "DONE",
    # Prompts / Utils
    "REACT_PREAMBLE", "PLAN_PREAMBLE", "to_assistant_dict",
]

# MCP ist optional (Abhängigkeit `mcp`): nur importieren, wenn verfügbar.
try:
    from .mcp import MCPClient  # noqa: F401
    __all__.append("MCPClient")
except Exception:  # pragma: no cover
    pass

__version__ = "0.1.0"
