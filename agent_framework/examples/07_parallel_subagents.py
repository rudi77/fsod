"""Beispiel 7 — Parallele Tool-Calls, Sub-Agents und Event-Forwarding.

- Parallele Tools: Liefert das Modell mehrere Tool-Calls in EINER Antwort, führt
  der Agent sie nebenläufig aus (parallel_tools=True).
- Sub-Agents: Der Orchestrator hat ein `delegate`-Tool. Jeder Aufruf startet
  einen eigenständigen Recherche-Agenten (eigener Kontext). Mehrere delegate-Calls
  aus einer Antwort laufen parallel (Map-Reduce).
- Event-Forwarding: Alle Sub-Agent-Events laufen in DENSELBEN EventBus, getaggt
  mit ihrer `source` (z. B. 'delegate:Wien'). Der Consumer zeigt die verschränkten
  Trace-Zeilen — der sichtbare Beweis der Nebenläufigkeit.

    python examples/07_parallel_subagents.py
"""
import threading
import time

from dotenv import load_dotenv

from agentkit import Agent, EventBus, ToolRegistry, add_subagent, azure_from_env
from agentkit.events import DONE, STEP, TOOL_CALL, TOOL_RESULT

load_dotenv()

# Drei "langsame" Tools (simulierte Latenz) für den Recherche-Sub-Agenten.
city_tools = ToolRegistry()
DB = {
    "wien": ("18°C bewölkt", "2.0 Mio", "CET"),
    "berlin": ("15°C Regen", "3.7 Mio", "CET"),
    "tokio": ("26°C sonnig", "14.0 Mio", "JST"),
}


@city_tools.tool()
def wetter(stadt: str) -> str:
    """Aktuelles Wetter einer Stadt."""
    time.sleep(0.8)
    return DB.get(stadt.lower(), ("?", "?", "?"))[0]


@city_tools.tool()
def einwohner(stadt: str) -> str:
    """Einwohnerzahl einer Stadt."""
    time.sleep(0.8)
    return DB.get(stadt.lower(), ("?", "?", "?"))[1]


@city_tools.tool()
def zeitzone(stadt: str) -> str:
    """Zeitzone einer Stadt."""
    time.sleep(0.8)
    return DB.get(stadt.lower(), ("?", "?", "?"))[2]


RECHERCHE_SYS = (
    "Du recherchierst GENAU EINE Stadt. Hole Wetter, Einwohner und Zeitzone (ruhig "
    "alle in einer Runde) und gib einen kompakten Steckbrief zurück."
)
ORCH_SYS = (
    "Du bist Koordinator. Rufe für JEDE Stadt 'delegate' auf — alle in DERSELBEN "
    "Antwort, damit die Sub-Agenten parallel arbeiten. Fasse die Steckbriefe danach "
    "als Markdown-Tabelle zusammen (Stadt, Wetter, Einwohner, Zeitzone)."
)

def consumer(q):
    """Rendert den verschränkten Event-Strom — pro Zeile die source des Agenten.
    Stoppt erst beim Root-DONE (source == ''); Sub-Agent-DONEs werden ignoriert."""
    while True:
        ev = q.get()
        who = ev.source or "ORCH"
        if ev.type == STEP:
            print(f"[{who}] Schritt {ev.data['step']}", flush=True)
        elif ev.type == TOOL_CALL:
            print(f"[{who}]   🔧 {ev.data['name']}({list(ev.data['args'].values())})", flush=True)
        elif ev.type == TOOL_RESULT:
            print(f"[{who}]   👁  {ev.data['result'][:60]}", flush=True)
        elif ev.type == DONE:
            if ev.source == "":      # nur der Orchestrator beendet den Consumer
                return


if __name__ == "__main__":
    llm = azure_from_env()
    bus = EventBus()
    q = bus.subscribe()

    # Orchestrator-Registry mit dem delegate-Tool (Sub-Agent = Recherche-Agent).
    # bus= aktiviert das Event-Forwarding der Sub-Agenten.
    orch_tools = ToolRegistry()
    add_subagent(
        orch_tools, "delegate",
        "Delegiert EINEN Rechercheauftrag an einen Sub-Agenten und gibt dessen "
        "Steckbrief zurück. Für mehrere Städte: mehrfach in DERSELBEN Antwort aufrufen.",
        llm, tools=city_tools, system=RECHERCHE_SYS, strategy="react",
        param_name="auftrag", param_desc="z. B. 'Steckbrief für Wien'", bus=bus,
    )

    orchestrator = Agent(llm, tools=orch_tools, system=ORCH_SYS,
                         strategy="plan", parallel_tools=True)

    ui = threading.Thread(target=consumer, args=(q,), daemon=True)
    ui.start()

    t0 = time.perf_counter()
    bericht = orchestrator.run_on_bus("Vergleiche Wien, Berlin und Tokio.", bus, source="")
    ui.join()
    print(f"\n--- fertig in {time.perf_counter() - t0:.1f}s ---\n")
    print(bericht)
