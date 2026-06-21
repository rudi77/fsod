"""agentkit — die installierbare Kommandozeilen-Anwendung (Python).

Pendant zur Rust-Executable (`agent_framework_rs/src/bin/agentkit.rs`), als
Console-Script `agentkit` (siehe `[project.scripts]` in `pyproject.toml`) oder via
`python -m agentkit` aufrufbar. Zwei Betriebsarten:

    agentkit "Was ist 17 + 25?"     # One-shot: Auftrag ausführen, Antwort streamen
    agentkit --repl                 # einfacher Zeilen-REPL (Gedächtnis bleibt erhalten)

LLM-Auswahl: ``AZURE_OPENAI_*`` -> Azure, sonst ``OPENAI_API_KEY`` -> OpenAI, sonst
ein eingebauter, netzfreier Demo-LLM. ``--demo`` erzwingt den Demo-Modus.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .agent import Agent
from .demo import build_llm, demo_tools
from .events import ERROR, FINAL, PLAN, TEXT_DELTA, TOOL_CALL, TOOL_RESULT


def _load_dotenv() -> None:
    """Lädt eine `.env`-Datei, falls `python-dotenv` installiert ist (optional)."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def _make_agent(args) -> Agent:
    llm, label = build_llm(force_demo=args.demo)
    print(f"» Modell: {label}", file=sys.stderr)
    return Agent(llm, tools=demo_tools(), strategy=args.strategy)


def _render(ev, state) -> None:
    """Rendert ein Event auf der Konsole. Text-Deltas streamen nach stdout, alles
    andere (Tool-Spur, Fehler) nach stderr — so trägt stdout nur die Antwort."""
    if ev.type == TEXT_DELTA:
        sys.stdout.write(ev.data)
        sys.stdout.flush()
        state["streamed"] = True
    elif ev.type == TOOL_CALL:
        print(f"🔧 {ev.data['name']}({ev.data['args']})", file=sys.stderr)
    elif ev.type == TOOL_RESULT:
        print(f"   ↳ {ev.data['name']}: {ev.data['result']}", file=sys.stderr)
    elif ev.type == PLAN:
        print(f"📋 {ev.data}", file=sys.stderr)
    elif ev.type == ERROR:
        name = ev.data.get("name")
        prefix = f"{name}: " if name else ""
        print(f"⚠ {prefix}{ev.data.get('error')}", file=sys.stderr)


def _run_once(agent: Agent, task: str) -> None:
    state = {"streamed": False}
    final = "(keine Antwort)"
    for ev in agent.run_iter(task):
        _render(ev, state)
        if ev.type == FINAL:
            final = ev.data if isinstance(ev.data, str) else final
    if not state["streamed"] and final:
        sys.stdout.write(final)
    sys.stdout.write("\n")


def _repl(agent: Agent) -> None:
    print("agentkit REPL — leere Zeile oder Ctrl-D beendet.")
    while True:
        try:
            task = input("› ").strip()
        except EOFError:
            print()
            break
        if not task:
            break
        _run_once(agent, task)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentkit",
        description="Ein ganz einfaches Agent-Framework als CLI.",
    )
    parser.add_argument("task", nargs="*", help="Auftrag (mehrere Wörter erlaubt)")
    parser.add_argument("--repl", action="store_true", help="interaktiver Zeilen-REPL")
    parser.add_argument("--demo", action="store_true",
                        help="Demo-Modus erzwingen (eingebauter, netzfreier LLM)")
    parser.add_argument("--strategy", choices=["react", "plan", "plain"], default="react",
                        help="Agent-Strategie (Default: react)")
    parser.add_argument("-V", "--version", action="version",
                        version=f"agentkit {__version__}")
    args = parser.parse_args(argv)

    _load_dotenv()
    agent = _make_agent(args)

    task = " ".join(args.task).strip()
    if task:
        _run_once(agent, task)
    else:
        _repl(agent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
