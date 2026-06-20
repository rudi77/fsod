"""MCP-Anbindung — Tools über das Model Context Protocol statt aus lokalem Code.

Derselbe Agent-Loop, nur kommen Schema & Ausführung jetzt von einem MCP-Server.
Im Gegensatz zum Notebook (Verbindung pro Aufruf) hält dieser Client EINE Session
offen: ein dedizierter Event-Loop in einem Hintergrund-Thread, in den synchrone
Aufrufe (`call_tool`) per `run_coroutine_threadsafe` eingespeist werden. Das ist
robust unter Jupyter wie im normalen Python und vermeidet wiederholte Handshakes.

Die `mcp`-Abhängigkeit ist optional und wird erst beim `connect()` importiert.
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
from typing import List, Optional


def _mcp_text(result) -> str:
    """MCP-Tool-Ergebnis -> Text fürs Modell."""
    parts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
    return "\n".join(parts) if parts else str(result.content)


def mcp_tools_to_schemas(mcp_tools) -> List[dict]:
    """MCP-Tool-Definitionen -> OpenAI-Tool-Schemas."""
    return [{
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description or "",
            "parameters": t.inputSchema or {"type": "object", "properties": {}},
        },
    } for t in mcp_tools]


class MCPClient:
    """Persistente Verbindung zu EINEM MCP-Server (stdio-Transport)."""

    def __init__(self, command: str, args: Optional[List[str]] = None,
                 env: Optional[dict] = None, name: Optional[str] = None):
        self.command = command
        self.args = args or []
        self.env = env
        self.name = name or command
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._session = None
        self._stdio_cm = None
        self._session_cm = None
        self.tools = []  # rohe MCP-Tool-Definitionen

    # --- Loop-Verwaltung im Hintergrund-Thread ---
    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def connect(self) -> "MCPClient":
        """Startet den Server-Prozess und führt den Protokoll-Handshake aus."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        # ProactorEventLoop auf Windows, damit Subprozesse starten können.
        self._loop = (asyncio.ProactorEventLoop()
                      if sys.platform == "win32" else asyncio.new_event_loop())
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        params = StdioServerParameters(command=self.command, args=self.args, env=self.env)
        errlog = open(os.devnull, "w")

        async def _setup():
            self._stdio_cm = stdio_client(params, errlog=errlog)
            read, write = await self._stdio_cm.__aenter__()
            self._session_cm = ClientSession(read, write)
            session = await self._session_cm.__aenter__()
            await session.initialize()
            self._session = session
            self.tools = (await session.list_tools()).tools

        self._submit(_setup())
        return self

    def schemas(self) -> List[dict]:
        return mcp_tools_to_schemas(self.tools)

    def call_tool(self, name: str, args: dict) -> str:
        result = self._submit(self._session.call_tool(name, args))
        return _mcp_text(result)

    def register(self, registry, prefix: str = "") -> "MCPClient":
        """Klinkt die Server-Tools in eine ToolRegistry ein (optional namespaced)."""
        for t in self.tools:
            registry.add(
                prefix + t.name,
                t.description or "",
                t.inputSchema or {"type": "object", "properties": {}},
                lambda sn=t.name, **kw: self.call_tool(sn, kw),  # sn= bindet den Tool-Namen pro Iteration
            )
        return self

    def close(self) -> None:
        if self._loop is None:
            return

        async def _teardown():
            for cm in (self._session_cm, self._stdio_cm):
                if cm is not None:
                    try:
                        await cm.__aexit__(None, None, None)
                    except Exception:
                        pass

        try:
            self._submit(_teardown())
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)

    def __enter__(self) -> "MCPClient":
        return self.connect()

    def __exit__(self, *exc) -> None:
        self.close()
