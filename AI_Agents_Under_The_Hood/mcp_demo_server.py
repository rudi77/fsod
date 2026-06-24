"""Ein echter MCP-Server (offizielles `mcp`-SDK, FastMCP).

Er spricht das echte Model Context Protocol (JSON-RPC 2.0 über stdio) und
stellt drei Tools bereit, die ein LLM allein NICHT zuverlässig kann:

  - current_time : Live-Serverzeit (kann das Modell nicht wissen)
  - add          : deterministische Arithmetik
  - search_kb    : durchsucht eine kleine Wissensdatenbank ("deine Daten via MCP")

Start (von Hand zum Ausprobieren):  uv run python mcp_demo_server.py
Im Notebook wird er als Subprozess über stdio gestartet — wie ein echter Client das tut.
"""
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-knowledge-server", log_level="WARNING")

# Eine winzige "Wissensdatenbank" – steht NUR auf dem Server, nicht im Modell.
KNOWLEDGE_BASE = {
    "mcp": (
        "Das Model Context Protocol (MCP) ist ein offener Standard von Anthropic (2024), "
        "der Tools, Ressourcen und Prompts über JSON-RPC zwischen Client und Server austauscht."
    ),
    "agent": (
        "Ein Agent ist ein LLM in einer Schleife mit Tools: fragen -> Tool ausführen -> "
        "Ergebnis anhängen -> erneut fragen, bis eine finale Antwort steht."
    ),
    "vortrag": (
        "Der Vortrag 'AI Agents under the Hood' baut einen Agenten from scratch und endet "
        "mit echtem MCP-Tool-Zugriff über einen separaten Serverprozess."
    ),
}


@mcp.tool()
def current_time() -> str:
    """Gibt das aktuelle Datum und die Uhrzeit des Servers im ISO-Format zurück."""
    return datetime.now().isoformat(timespec="seconds")


@mcp.tool()
def add(a: float, b: float) -> float:
    """Addiert zwei Zahlen und gibt die Summe zurück."""
    return a + b


@mcp.tool()
def search_kb(query: str) -> str:
    """Durchsucht die Wissensdatenbank des Servers nach einem Stichwort und gibt passende Einträge zurück."""
    q = query.lower()
    hits = [f"- {key}: {text}" for key, text in KNOWLEDGE_BASE.items()
            if q in key or q in text.lower()]
    return "\n".join(hits) if hits else f"Kein Eintrag zu '{query}' gefunden."


if __name__ == "__main__":
    # Standard-Transport von FastMCP ist stdio – genau das, was ein MCP-Client erwartet.
    mcp.run()
