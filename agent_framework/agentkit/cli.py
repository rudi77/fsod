"""agentkit-CLI — ein Terminal-Frontend für den Agenten, im Stil von Claude Code.

Derselbe Agent-Loop wie sonst, nur mit einer Konsolen-Oberfläche drumherum:

- **Interaktive Session** (REPL): eine fortlaufende Unterhaltung — das Kurzzeit-
  gedächtnis bleibt über die Eingaben hinweg erhalten (wie ein Chat).
- **One-shot** (`agentkit "Aufgabe"` oder `--print`): einmal abarbeiten, ausgeben, fertig.
- **Live-Rendering** über den `EventBus`: gestreamter Text, Tool-Aufrufe, Tool-
  Ergebnisse und der mitgeführte Plan werden hübsch angezeigt.
- **Stop-Knopf**: Ctrl-C bricht die *laufende* Aufgabe kooperativ ab (statt das
  Programm zu beenden) — wie Esc in Claude Code.
- **Slash-Befehle**: `/help`, `/clear`, `/reset`, `/plan`, `/tools`, `/skills`, `/exit`.

Bewusst ohne zusätzliche Abhängigkeiten: Farben über ANSI-Codes (auf Windows wird
das Virtual-Terminal-Processing aktiviert), der Rest ist Standardbibliothek.

    python -m agentkit            # interaktive Session
    python -m agentkit "Aufgabe"  # einmal abarbeiten
    agentkit --help               # alle Optionen
"""

from __future__ import annotations

import argparse
import os
import sys
import threading

from .agent import Agent
from .coding import CODING_SYSTEM, CodingTools
from .events import (CANCELLED, DONE, ERROR, EventBus, FINAL, PLAN, STEP,
                     TEXT_DELTA, TOOL_CALL, TOOL_RESULT)
from .memory import LongTermMemory, ShortTermMemory
from .skills import SKILL_SYSTEM, Skills
from .planning import Plan
from .tools import ToolRegistry

# --------------------------------------------------------------------- Farben
class C:
    """ANSI-Farbcodes (leer, wenn Farbe deaktiviert ist)."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

    @classmethod
    def disable(cls) -> None:
        for k in list(vars(cls)):
            if k.isupper():
                setattr(cls, k, "")


class G:
    """Symbole für die Anzeige. Werden auf ASCII zurückgestuft, wenn die Konsole
    (z. B. cp1252 unter Windows) die hübschen Unicode-Glyphen nicht kodieren kann."""
    ascii = False  # True, sobald auf den ASCII-Fallback zurückgestuft wurde
    TOOL = "⏺"
    RESULT = "⎿"
    PLAN = "📋"
    WARN = "⚠"
    ERROR = "✖"
    STOP = "⛔"
    PAUSE = "⏸"
    OK = "✓"
    NL = "↵"
    PROMPT = "›"

    @classmethod
    def to_ascii(cls) -> None:
        cls.ascii = True
        cls.TOOL, cls.RESULT, cls.PLAN = "*", "|_", "[plan]"
        cls.WARN, cls.ERROR, cls.STOP = "!", "x", "[stop]"
        cls.PAUSE, cls.OK, cls.NL, cls.PROMPT = "||", "ok", "\\n", ">"


def _setup_console() -> None:
    """Macht stdout/stdin UTF-8-fähig und stuft die Glyphen auf ASCII zurück, wenn
    die Ausgabe-Kodierung sie nicht darstellen kann (verhindert UnicodeEncodeError)."""
    for stream in (sys.stdout, sys.stdin):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # Python 3.7+
        except Exception:
            pass
    enc = (getattr(sys.stdout, "encoding", None) or "ascii")
    try:
        G.TOOL.encode(enc)
    except (UnicodeEncodeError, LookupError):
        G.to_ascii()


def _enable_colors() -> None:
    """Aktiviert ANSI-Farben (inkl. Virtual Terminal auf Windows) oder schaltet sie
    ab, wenn die Ausgabe kein Terminal ist bzw. NO_COLOR gesetzt ist."""
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        C.disable()
        return
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x4 auf dem stdout-Handle (-11).
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            C.disable()


# ----------------------------------------------------------------- Rendering
def _abbrev(value, limit: int = 60) -> str:
    """Kürzt einen Argumentwert für die einzeilige Tool-Anzeige."""
    s = value if isinstance(value, str) else repr(value)
    s = s.replace("\n", G.NL)
    if len(s) > limit:
        return f"{s[:limit]}… ({len(s)} Z.)"
    return s


def _fmt_args(args: dict) -> str:
    return ", ".join(f"{k}={_abbrev(v)}" for k, v in args.items())


class Renderer:
    """Übersetzt `AgentEvent`s in hübsche Terminal-Ausgabe (Claude-Code-Stil)."""

    def __init__(self, show_steps: bool = False, quiet: bool = False):
        self.show_steps = show_steps
        self.quiet = quiet  # im --print-Modus: nichts live anzeigen, nur finale Antwort
        self._streaming = False  # gerade fließt Modell-Text?

    def _end_stream(self) -> None:
        if self._streaming:
            print()
            self._streaming = False

    def handle(self, ev) -> None:
        if self.quiet:
            return
        if ev.type == STEP:
            if self.show_steps:
                self._end_stream()
                print(f"{C.GRAY}— Schritt {ev.data['step']} —{C.RESET}")

        elif ev.type == TEXT_DELTA:
            if not self._streaming:
                self._streaming = True
            print(ev.data, end="", flush=True)

        elif ev.type == TOOL_CALL:
            self._end_stream()
            print(f"{C.CYAN}{G.TOOL} {C.BOLD}{ev.data['name']}{C.RESET}"
                  f"{C.GRAY}({_fmt_args(ev.data['args'])}){C.RESET}", flush=True)

        elif ev.type == TOOL_RESULT:
            self._print_result(ev.data["result"])

        elif ev.type == PLAN:
            self._end_stream()
            print(f"{C.MAGENTA}{G.PLAN} Plan{C.RESET}")
            for line in ev.data.render().splitlines():
                print(f"{C.MAGENTA}   {line}{C.RESET}")

        elif ev.type == ERROR:
            self._end_stream()
            name = ev.data.get("name", "?")
            print(f"{C.RED}{G.ERROR} Fehler in {name}: {ev.data.get('error')}{C.RESET}", flush=True)

        elif ev.type == CANCELLED:
            self._end_stream()
            print(f"{C.YELLOW}{G.STOP} abgebrochen ({ev.data['where']}){C.RESET}", flush=True)

        elif ev.type == FINAL:
            self._end_stream()

    def _print_result(self, result: str, max_lines: int = 6) -> None:
        """Tool-Ergebnis eingerückt und auf wenige Zeilen gekürzt anzeigen."""
        lines = (result or "").splitlines() or ["(leer)"]
        shown = lines[:max_lines]
        for line in shown:
            print(f"{C.GRAY}  {G.RESULT} {_abbrev(line, 100)}{C.RESET}")
        if len(lines) > max_lines:
            print(f"{C.GRAY}  {G.RESULT} …(+{len(lines) - max_lines} Zeilen){C.RESET}")


# ------------------------------------------------------------------ Approval
def confirm_shell(command: str) -> bool:
    """approve-Callback für `run_shell`: fragt mit eingefärbtem Prompt nach.
    (Bei `--yes` wird `approval=False` gesetzt, sodass dieser Callback gar nicht läuft.)"""
    print(f"\n{C.YELLOW}{G.WARN}  Shell-Befehl ausführen?{C.RESET}\n  {C.BOLD}{command}{C.RESET}")
    try:
        ans = input(f"{C.YELLOW}  [j]a / [N]ein {G.PROMPT} {C.RESET}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return ans in ("j", "ja", "y", "yes")


# --------------------------------------------------------------------- Setup
def build_llm(provider: str):
    """Baut den LLM je nach Provider; 'auto' rät aus den vorhandenen Env-Variablen."""
    from .llm import azure_from_env, openai_from_env

    if provider == "auto":
        if os.environ.get("AZURE_OPENAI_API_KEY"):
            provider = "azure"
        elif os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        else:
            raise SystemExit(
                "Keine LLM-Zugangsdaten gefunden. Lege eine .env an (siehe .env.example) "
                "mit AZURE_OPENAI_* oder OPENAI_API_KEY — oder gib --provider an."
            )
    return (azure_from_env() if provider == "azure" else openai_from_env())


def build_agent(args) -> tuple[Agent, ToolRegistry, Plan, Skills | None]:
    """Stellt einen Coding-fähigen Agenten zusammen (Tools + Plan + optional Skills/Memory)."""
    llm = build_llm(args.provider)

    tools = ToolRegistry()
    CodingTools(workspace=args.workspace, approval=not args.yes,
                approve=confirm_shell).register(tools)

    skills = Skills(args.skills) if args.skills else None
    long_term = LongTermMemory(args.memory) if args.memory else None

    # System-Prompt: Coding-Basis, um Skill-Hinweis ergänzt, wenn Skills aktiv sind.
    system = CODING_SYSTEM
    if skills is not None:
        system = CODING_SYSTEM + "\n\n" + SKILL_SYSTEM

    plan = Plan()  # Render erfolgt über das PLAN-Event im Renderer
    agent = Agent(llm, tools=tools, system=system, strategy=args.strategy,
                  plan=plan, skills=skills, long_term=long_term,
                  max_steps=args.max_steps)
    return agent, tools, plan, skills


# ------------------------------------------------------------------ Ausführen
def run_task(agent: Agent, task: str, renderer: Renderer) -> str:
    """Treibt EINE Aufgabe auf einem Worker-Thread an und rendert die Events live.
    Ctrl-C setzt den Stop-Knopf (kooperativer Abbruch), statt das Programm zu beenden."""
    bus = EventBus()
    q = bus.subscribe()
    cancel = threading.Event()
    result = {"final": "(keine Antwort)"}

    def worker():
        result["final"] = agent.run_on_bus(task, bus, cancel=cancel)

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    interrupted = False
    while True:
        try:
            ev = q.get()           # Ctrl-C kann hier ODER im handle() unten landen
            if ev.type == DONE:
                break
            renderer.handle(ev)
        except KeyboardInterrupt:
            if interrupted:        # zweites Ctrl-C: durchreichen -> Programmende
                raise
            interrupted = True     # erstes Ctrl-C: kooperativ abbrechen
            cancel.set()
            print(f"\n{C.YELLOW}{G.PAUSE}  unterbreche … (nochmal Ctrl-C zum Beenden){C.RESET}",
                  flush=True)
    t.join()
    return result["final"]


# -------------------------------------------------------------- Slash-Befehle
def help_text() -> str:
    """Die Hilfe — als Funktion, damit die Farb-Codes erst beim Anzeigen gelesen
    werden (nach `C.disable()` bei --no-color)."""
    return f"""{C.BOLD}Befehle{C.RESET}
  {C.CYAN}/help{C.RESET}      diese Hilfe
  {C.CYAN}/clear{C.RESET}     Bildschirm leeren
  {C.CYAN}/reset{C.RESET}     Unterhaltung vergessen (neues Kurzzeitgedächtnis)
  {C.CYAN}/plan{C.RESET}      aktuellen Plan zeigen
  {C.CYAN}/tools{C.RESET}     registrierte Tools auflisten
  {C.CYAN}/skills{C.RESET}    verfügbare Skills auflisten
  {C.CYAN}/exit{C.RESET}      beenden (auch /quit, Ctrl-D)

Sonst: einfach eine Aufgabe eintippen. Ctrl-C bricht die laufende Aufgabe ab."""


def handle_slash(cmd: str, agent: Agent, tools: ToolRegistry,
                 plan: Plan, skills: Skills | None) -> bool:
    """Bearbeitet einen /Befehl. Gibt False zurück, wenn die Session enden soll."""
    name = cmd[1:].strip().lower()
    if name in ("exit", "quit", "q"):
        return False
    if name == "help":
        print(help_text())
    elif name == "clear":
        os.system("cls" if os.name == "nt" else "clear")
    elif name == "reset":
        sys_msg = next((m for m in agent.memory.messages if m.get("role") == "system"), None)
        agent.memory = ShortTermMemory(sys_msg["content"] if sys_msg else None)
        print(f"{C.GREEN}{G.OK} Unterhaltung zurückgesetzt.{C.RESET}")
    elif name == "plan":
        print(f"{C.MAGENTA}{plan.render()}{C.RESET}")
    elif name == "tools":
        print(f"{C.BOLD}Tools:{C.RESET} " + ", ".join(tools.names()))
    elif name == "skills":
        if skills is None:
            print(f"{C.GRAY}(keine Skills aktiv — mit --skills <ordner> starten){C.RESET}")
        else:
            idx = skills.index()
            if not idx:
                print(f"{C.GRAY}(keine Skills in {skills.dir} gefunden){C.RESET}")
            for s in idx:
                print(f"  {C.CYAN}{s['name']}{C.RESET} — {s['description']}")
    else:
        print(f"{C.RED}Unbekannter Befehl: {cmd}{C.RESET}  ({C.CYAN}/help{C.RESET})")
    return True


# --------------------------------------------------------------------- Banner
def banner(args) -> str:
    from pathlib import Path
    ws = _abbrev(str(Path(args.workspace).resolve()), 40)
    # (sichtbarer Text, eingefärbter Text) — die Polsterung richtet sich nach dem
    # sichtbaren Text, damit ANSI-Codes die Ausrichtung nicht verfälschen.
    rows = [
        ("agentkit — ein LLM in einer Schleife mit Tools",
         f"{C.BOLD}agentkit{C.RESET} — ein LLM in einer Schleife mit Tools"),
        (f"Workspace: {ws}", f"{C.GRAY}Workspace:{C.RESET} {ws}"),
        (f"Strategie: {args.strategy}", f"{C.GRAY}Strategie:{C.RESET} {args.strategy}"),
        ("/help für Befehle, /exit zum Beenden",
         f"{C.GRAY}/help{C.RESET} für Befehle, {C.GRAY}/exit{C.RESET} zum Beenden"),
    ]
    if G.ascii:  # ASCII-Fallback: schlichte Zeilen statt Box-Zeichnung
        head = f"{C.CYAN}== agentkit =={C.RESET}\n"
        return head + "\n".join(colored for _, colored in rows[1:])

    width = max(len(plain) for plain, _ in rows) + 2  # 2 Leerzeichen Innenrand links
    bar = "─" * (width + 2)
    out = [f"{C.CYAN}╭{bar}╮{C.RESET}"]
    for plain, colored in rows:
        pad = " " * (width - 2 - len(plain))
        out.append(f"{C.CYAN}│{C.RESET}  {colored}{pad}  {C.CYAN}│{C.RESET}")
    out.append(f"{C.CYAN}╰{bar}╯{C.RESET}")
    return "\n".join(out)


def repl(agent, tools, plan, skills, renderer) -> None:
    """Die interaktive Session: Eingabe lesen, Slash-Befehle oder Aufgabe abarbeiten."""
    while True:
        try:
            user = input(f"\n{C.GREEN}{G.PROMPT}{C.RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{C.GRAY}Tschüss.{C.RESET}")
            return
        if not user:
            continue
        if user.startswith("/"):
            if not handle_slash(user, agent, tools, plan, skills):
                print(f"{C.GRAY}Tschüss.{C.RESET}")
                return
            continue
        run_task(agent, user, renderer)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agentkit",
        description="Claude-Code-artiges CLI für den agentkit-Agenten.",
    )
    p.add_argument("prompt", nargs="*", help="Aufgabe (one-shot). Ohne Angabe: interaktive Session.")
    p.add_argument("-w", "--workspace", default=".",
                   help="Arbeits-/Sandbox-Verzeichnis für die Coding-Tools "
                        "(Default: . — das aktuelle Verzeichnis, wie Claude Code).")
    p.add_argument("-s", "--strategy", default="react", choices=["react", "plan", "plain"],
                   help="Agenten-Strategie (Default: react).")
    p.add_argument("--skills", metavar="DIR", default=None,
                   help="Skills-Verzeichnis aktivieren (SKILL.md-Ordner).")
    p.add_argument("--memory", metavar="FILE", default=None,
                   help="Langzeitgedächtnis-Datei (JSONL) für remember/recall.")
    p.add_argument("--provider", default="auto", choices=["auto", "azure", "openai"],
                   help="LLM-Provider (Default: auto — aus der .env erraten).")
    p.add_argument("--max-steps", type=int, default=160, help="Max. Loop-Schritte pro Aufgabe.")
    p.add_argument("-y", "--yes", action="store_true",
                   help="Shell-Befehle ohne Rückfrage ausführen (Vorsicht!).")
    p.add_argument("--steps", action="store_true", help="Schritt-Grenzen mit anzeigen.")
    p.add_argument("--no-color", action="store_true", help="Farbausgabe deaktivieren.")
    p.add_argument("-p", "--print", dest="print_mode", action="store_true",
                   help="One-shot: Aufgabe abarbeiten, finale Antwort ausgeben, beenden.")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    # .env laden, falls vorhanden (für azure_from_env / openai_from_env).
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    _setup_console()  # UTF-8 + ASCII-Glyph-Fallback (verhindert UnicodeEncodeError)
    if args.no_color:
        C.disable()
    else:
        _enable_colors()

    agent, tools, plan, skills = build_agent(args)
    renderer = Renderer(show_steps=args.steps, quiet=args.print_mode)

    task = " ".join(args.prompt).strip()

    # One-shot: Aufgabe als Argument übergeben (oder --print).
    if task or args.print_mode:
        if not task:
            print("Keine Aufgabe übergeben.", file=sys.stderr)
            return 2
        final = run_task(agent, task, renderer)
        if args.print_mode:
            # Im --print-Modus die finale Antwort sauber (ohne Trace) ausgeben.
            print(final)
        return 0

    # Interaktive Session.
    print(banner(args))
    repl(agent, tools, plan, skills, renderer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
