"""Beispiel 2 — Dieselbe Aufgabe, aber Plan-and-Execute statt ReAct.

Nur `strategy="plan"` ändert sich — der Loop bleibt identisch.
    python examples/02_plan_and_execute.py
"""
import os

from dotenv import load_dotenv

from agentkit import Agent, ToolRegistry, azure_from_env
from agentkit.events import TEXT_DELTA

load_dotenv()

tools = ToolRegistry()


@tools.tool()
def list_files(path: str = ".") -> str:
    """Listet die Dateien in einem Verzeichnis auf."""
    return "\n".join(sorted(os.listdir(path)))


if __name__ == "__main__":
    agent = Agent(azure_from_env(), tools=tools, strategy="plan")
    # Live-Streaming der Tokens (inkl. des Plans, den das Modell zuerst schreibt).
    agent.run(
        "Erstelle einen Plan, zähle dann die Dateien im aktuellen Ordner und "
        "fasse in zwei Sätzen zusammen, was hier liegt.",
        on_event=lambda ev: print(ev.data, end="", flush=True) if ev.type == TEXT_DELTA else None,
    )
    print()
