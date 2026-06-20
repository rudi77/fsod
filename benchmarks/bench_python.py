"""Microbenchmarks für den Framework-Overhead des Python-`agentkit` (FakeLLM).

Spiegelt 1:1 das Rust-Pendant (`agent_framework_rs/src/bin/bench.rs`), damit
Rust vs. Python direkt vergleichbar ist. Gibt am Ende eine JSON-Zeile
`{"lang":"python","results":{...}}` auf stdout aus; menschenlesbare Zeilen nach
stderr.

    python3 benchmarks/bench_python.py            # alle Szenarien
    AGENTKIT_BENCH_SCALE=0.2 python3 ...          # schneller, weniger Iterationen

Hinweis Token-Zählung: tiktoken ist (wie in Rust) NICHT im Spiel — beide messen
denselben len//4-Fallback, also reinen Schleifen-/Sprach-Overhead, nicht die
Geschwindigkeit eines echten Tokenizers.
"""

import json
import os
import sys
import time
from types import SimpleNamespace

# agentkit aus dem Quellbaum importierbar machen.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_framework"))

import agentkit.memory as _memory  # noqa: E402

# Token-Zählung auf den len//4-Fallback festnageln (deckungsgleich mit Rust).
_memory.count_tokens_text = lambda text: len(text) // 4

from agentkit import Agent, ShortTermMemory, ToolRegistry  # noqa: E402
from agentkit.skills import parse_frontmatter  # noqa: E402


# --------------------------------------------------------------- FakeLLM
def _chunk(content=None, tool=None, index=0):
    delta = SimpleNamespace(content=content, tool_calls=None)
    if tool:
        tc = SimpleNamespace(
            index=index, id=tool.get("id"),
            function=SimpleNamespace(name=tool.get("name"), arguments=tool.get("arguments")),
        )
        delta.tool_calls = [tc]
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


class FakeLLM:
    """Spielt eine Liste von 'Turns' ab; jeder Turn ist eine Liste von Chunks."""

    def __init__(self, turns):
        self.turns = turns
        self.i = 0

    def stream(self, messages, tools=None):
        turn = self.turns[self.i]
        self.i += 1
        return iter(turn)

    def complete(self, messages, tools=None):
        return SimpleNamespace(content="komprimierte Zusammenfassung", tool_calls=None)


# ----------------------------------------------------------- Hilfen
ADD_SCHEMA = {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]}


def build_add_registry():
    reg = ToolRegistry()
    reg.add("add", "Addiert zwei Zahlen.", ADD_SCHEMA, lambda a, b: a + b)
    return reg


def time_it(iters, f):
    start = time.perf_counter_ns()
    for _ in range(iters):
        f()
    return float(time.perf_counter_ns() - start)


SCALE = float(os.environ.get("AGENTKIT_BENCH_SCALE", "1.0"))


def scaled(base):
    return max(1, int(base * SCALE))


results = {}


def run(name, iters, f):
    ns = time_it(iters, f)
    print(f"{name:<24} iters={iters:>9}  {ns / iters:>10.1f} ns/op  ({ns / 1e9:.3f} s total)",
          file=sys.stderr)
    results[name] = {"iters": iters, "total_ns": ns, "ns_per_op": ns / iters}


# 1) Voller Agent-Loop: Tool-Call -> Ergebnis -> finale Antwort (frischer Agent).
def scenario_agent_loop():
    reg = build_add_registry()
    llm = FakeLLM([
        [_chunk(tool={"id": "c1", "name": "add", "arguments": '{"a":2,"b":3}'})],
        [_chunk(content="Das Ergebnis ist 5.")],
    ])
    agent = Agent(llm, tools=reg, strategy="plain")
    agent.run("Was ist 2+3?")


# 2) Parallele Tool-Calls: 8 Tools in EINER Antwort (Thread-Overhead).
def scenario_parallel_tools():
    reg = ToolRegistry()
    reg.add("noop", "Gibt ok zurück.",
            {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
            lambda x: f"ok{x}")
    turn1 = [_chunk(tool={"id": f"t{i}", "name": "noop", "arguments": f'{{"x":{i}}}'}, index=i)
             for i in range(8)]
    llm = FakeLLM([turn1, [_chunk(content="fertig")]])
    agent = Agent(llm, tools=reg, strategy="plain", parallel_tools=True)
    agent.run("rechne")


# 4) Token-Zählung über eine Historie (20 Nachrichten ~200 Zeichen).
_FILLER = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor "
           "incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam quis nostrud.")
_MEM = ShortTermMemory(system="Du bist ein hilfreicher Agent.")
for _i in range(20):
    _MEM.add({"role": "user", "content": f"Nachricht {_i}: {_FILLER}"})

# 5) Frontmatter-Parsing einer SKILL.md.
_SKILL_TEXT = ("---\nname: rechnungsrueckfrage\n"
               "description: Beantwortet Rückfragen zu Rechnungen sauber und vollständig.\n---\n\n"
               "# Rechnungsrückfrage\n\nSchritt 1. Lies die Rechnung.\nSchritt 2. Prüfe die Positionen.\n")

# 6) JSON-Roundtrip eines Tool-Argument-Objekts.
_JSON_OBJ = {"a": 2, "b": 3, "name": "test", "items": [1, 2, 3], "nested": {"k": "v"}}


def main():
    run("agent_loop_single_tool", scaled(50_000), scenario_agent_loop)
    run("parallel_tools_8", scaled(5_000), scenario_parallel_tools)

    reg = build_add_registry()
    run("tool_dispatch", scaled(500_000), lambda: reg.call("add", {"a": 2, "b": 3}))

    run("token_count_history", scaled(200_000), _MEM.tokens)
    run("frontmatter_parse", scaled(500_000), lambda: parse_frontmatter(_SKILL_TEXT))

    def json_roundtrip():
        s = json.dumps(_JSON_OBJ)
        json.loads(s)

    run("json_roundtrip", scaled(300_000), json_roundtrip)

    print(json.dumps({"lang": "python", "results": results}))


if __name__ == "__main__":
    main()
