"""Beispiel 4 — Tools über MCP statt aus lokalem Code.

Nutzt den Demo-MCP-Server aus den Notebooks. Pfad ggf. anpassen.
Voraussetzung: `pip install mcp` (oder agentkit[mcp]).

    python examples/04_mcp.py
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

from agentkit import Agent, ToolRegistry, azure_from_env
from agentkit.mcp import MCPClient

load_dotenv()

# Der Demo-Server liegt in den Notebook-Beispielen.
SERVER = (Path(__file__).resolve().parents[2]
          / "AI_Agents_Under_The_Hood" / "mcp_demo_server.py")

if __name__ == "__main__":
    tools = ToolRegistry()
    mcp = MCPClient(command=sys.executable, args=[str(SERVER)], name="demo").connect()
    print("MCP-Tools:", [t.name for t in mcp.tools])
    mcp.register(tools)  # Server-Tools in die Registry einklinken

    try:
        agent = Agent(azure_from_env(), tools=tools, strategy="react")
        answer = agent.run(
            "Wie spät ist es laut Server? Rechne außerdem 17+25 und was weiß die "
            "Wissensdatenbank über MCP?"
        )
        print("\n=== Antwort ===\n", answer)
    finally:
        mcp.close()
