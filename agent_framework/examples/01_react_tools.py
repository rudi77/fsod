"""Beispiel 1 — ReAct-Agent mit lokalen Tools.

Braucht eine .env mit Azure-OpenAI-Werten (siehe .env.example).
    python examples/01_react_tools.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv

from agentkit import Agent, ToolRegistry, azure_from_env
from agentkit.events import STEP, TEXT_DELTA, TOOL_CALL

load_dotenv()

tools = ToolRegistry()


@tools.tool()
def list_files(path: str = ".") -> str:
    """Listet die Dateien in einem Verzeichnis auf."""
    return "\n".join(sorted(os.listdir(path)))


@tools.tool()
def read_file(path: str) -> str:
    """Liest die ersten 2000 Zeichen einer Textdatei."""
    return Path(path).read_text(encoding="utf-8", errors="replace")[:2000]


def live(ev):
    if ev.type == STEP:
        print(f"\n[Schritt {ev.data['step']}] ", end="", flush=True)
    elif ev.type == TOOL_CALL:
        print(f"\n  🔧 {ev.data['name']}({ev.data['args']})", flush=True)
    elif ev.type == TEXT_DELTA:
        print(ev.data, end="", flush=True)


if __name__ == "__main__":
    agent = Agent(azure_from_env(), tools=tools, strategy="react")
    answer = agent.run(
        "Welche Dateien liegen im aktuellen Verzeichnis, und worum geht es laut README?",
        on_event=live,
    )
    print("\n\n=== Antwort ===\n", answer)
