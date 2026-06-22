---
feature: mcp
status: shipped
since: 2026-06-20
last_verified: 2026-06-22
owner:
adr:
---

# MCP — Tools über das Model Context Protocol

Derselbe Agent-Loop, nur kommen Schema und Ausführung der Tools nicht aus
lokalem Code, sondern von einem MCP-Server. Der Client hält **eine** Sitzung
offen: ein dedizierter Event-Loop in einem Hintergrund-Thread, in den synchrone
Aufrufe eingespeist werden. Das ist robust unter Jupyter wie im normalen Python
und vermeidet wiederholte Handshakes. Die Server-Tools lassen sich — optional mit
Namens-Präfix — in dieselbe Tool-Registry einklinken, die der Agent ohnehin nutzt.
Die `mcp`-Abhängigkeit ist optional und wird erst beim Verbinden importiert.

## Fähigkeiten (was der Nutzer tun kann)

- Einen MCP-Server (stdio) starten und eine persistente Sitzung aufbauen
- Die Tools des Servers entdecken und ihre Schemas fürs Modell abrufen
- Server-Tools (optional namespaced) in die Tool-Registry des Agenten einklinken
- Ein Server-Tool synchron aufrufen und das Ergebnis als Text erhalten
- Den Client als Kontextmanager nutzen (`with`) — Verbindung auf, Aufräumen zu

## Invarianten (was immer gelten muss)

- Es bleibt **eine** Sitzung über die Lebensdauer des Clients offen; synchrone Aufrufe werden in den Hintergrund-Loop eingespeist (kein Handshake pro Aufruf).
- MCP-Tool-Definitionen werden verlustfrei in OpenAI-Tool-Schemas übersetzt; fehlt ein Eingabeschema, wird ein leeres Objekt-Schema eingesetzt.
- Ein Tool-Ergebnis wird auf seinen Textanteil reduziert; ohne Textanteil kommt eine String-Repräsentation des Inhalts.
- Beim Einklinken bindet jedes registrierte Tool seinen eigenen Server-Tool-Namen (keine Verwechslung bei mehreren Tools); ein Präfix kann Namenskollisionen mit lokalen Tools vermeiden.
- Auf Windows wird ein ProactorEventLoop genutzt, damit der Server-Subprozess starten kann.
- `close()` ist idempotent genug, um ohne Verbindung gefahrlos aufzurufen; Aufräum-Fehler werden geschluckt.

## API-/Schnittstellen-Vertrag (worauf sich Aufrufer verlassen)

- `MCPClient(command, args=, env=, name=).connect() -> self` — Server starten + Handshake
- `MCPClient.schemas() -> list[dict]` — Server-Tools als OpenAI-Schemas
- `MCPClient.call_tool(name, args) -> str` — synchroner Aufruf, Textergebnis
- `MCPClient.register(registry, prefix="") -> self` — Tools (optional namespaced) einklinken
- `MCPClient.close()` / `with MCPClient(...) as c:` — Sitzung sauber beenden
- `mcp_tools_to_schemas(mcp_tools) -> list[dict]` — freie Übersetzungsfunktion

## Konfigurationsfläche (Schalter/Parameter)

- `command`, `args`, `env`, `name` — wie der Server-Prozess gestartet/benannt wird
- `register(prefix=...)` — Namespace für die Server-Tools in der Registry

## Tests (müssen existieren und bestehen)

- `tests/test_agentkit.py::test_mcp_tools_to_schemas` — MCP-Definitionen → OpenAI-Schemas

## Bekannte Lücken

- Nur stdio-Transport; HTTP/SSE-Server werden nicht unterstützt.
- Der Live-Verbindungspfad (`connect`/`call_tool`/`close`) hat keinen Test — nur die reine Schema-Übersetzung ist abgedeckt (echter Server nötig).
- Pro Client genau ein Server; mehrere Server brauchen mehrere Clients.

## Querverweise

- verwandte Spec: [tool-registry](tool-registry.md), [agentic-loop](agentic-loop.md)
- Code: agentkit/mcp.py
