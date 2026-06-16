"""Derselbe Demo-Server wie im MCP-Notebook - nur anderer Transport.

Statt stdio sprechen wir hier streamable-http, damit das LiteLLM-Gateway unsere
Tools ueber das Netzwerk erreichen kann. Die Tools selbst (current_time, add,
search_kb) sind voellig unveraendert - wir importieren einfach dieselbe
FastMCP-Instanz.

Laeuft via docker-compose im Service 'demo-mcp' (siehe Dockerfile.mcp).
Start von Hand zum Ausprobieren:  uv run python mcp_http_server.py
"""
from mcp_demo_server import mcp   # <- exakt dieselbe FastMCP-Instanz mit denselben Tools
from mcp.server.transport_security import TransportSecuritySettings

mcp.settings.host = "0.0.0.0"     # an alle Interfaces binden -> im Compose-Netz erreichbar
mcp.settings.port = 8000          # FastMCP exponiert die Tools unter http://<host>:8000/mcp

# WICHTIG (sonst gibt es '421 Misdirected Request'):
# FastMCP hat einen DNS-Rebinding-Schutz und erlaubt per Default NUR localhost als
# Host-Header. Das Gateway verbindet sich aber unter dem Service-/Hostnamen
# ('demo-mcp' im Compose-Netz, sonst 'host.docker.internal') - den erlauben wir hier.
mcp.settings.transport_security = TransportSecuritySettings(
    allowed_hosts=["demo-mcp:*", "host.docker.internal:*", "localhost:*", "127.0.0.1:*", "0.0.0.0:*"],
    allowed_origins=["*"],
)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
