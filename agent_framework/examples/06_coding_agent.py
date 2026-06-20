"""Beispiel 6 — Ein Coding-Agent mit Plan, Sandbox und Tests.

Kombiniert: Coding-Tools (write/edit/read/list/shell), das update_plan-Tool und
Plan-and-Execute. Der Agent schreibt FizzBuzz + pytest-Tests und lässt sie grün
laufen — alles in ./agent_workspace.

    APPROVAL: run_shell fragt vor jeder Ausführung nach. Für eine schnelle Demo
    approval=False setzen.

    python examples/06_coding_agent.py
"""
from dotenv import load_dotenv

from agentkit import (Agent, AgentEvent, CODING_SYSTEM, CodingTools, Plan,
                      ToolRegistry, azure_from_env)
from agentkit.events import PLAN, STEP, TEXT_DELTA, TOOL_CALL

load_dotenv()


def live(ev):
    if ev.type == STEP:
        print(f"\n[Schritt {ev.data['step']}]", flush=True)
    elif ev.type == TOOL_CALL:
        print(f"  🔧 {ev.data['name']}({list(ev.data['args'])})", flush=True)
    elif ev.type == PLAN:
        print("  📋 Plan aktualisiert:\n" + ev.data.render(), flush=True)
    elif ev.type == TEXT_DELTA:
        print(ev.data, end="", flush=True)


if __name__ == "__main__":
    tools = ToolRegistry()
    CodingTools(workspace="./agent_workspace", approval=True).register(tools)

    # Plan mit Callback -> jede Aktualisierung wird über unsere live()-Anzeige sichtbar.
    plan = Plan(on_update=lambda p: live(AgentEvent(PLAN, p)))

    agent = Agent(azure_from_env(), tools=tools, system=CODING_SYSTEM,
                  strategy="plan", plan=plan, max_steps=18)

    answer = agent.run(
        "Erstelle fizzbuzz.py mit fizzbuzz(n), das für 1..n die FizzBuzz-Regeln als Liste "
        "von Strings zurückgibt. Schreibe test_fizzbuzz.py (prüfe 3->'Fizz', 5->'Buzz', "
        "15->'FizzBuzz', 1->'1') und führe 'python -m pytest -q' aus, bis alles grün ist.",
        on_event=live,
    )
    print("\n\n=== Ergebnis ===\n", answer)
    print("\nFinaler Plan:\n" + plan.render())
