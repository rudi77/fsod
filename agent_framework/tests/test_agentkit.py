"""Tests ohne Netz — Tools, Memory, Events, MCP-Konvertierung und der Agent-Loop
mit einem FakeLLM, das OpenAI-Streaming-Chunks nachstellt.
"""

import json
import os
import sys
import threading
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentkit import (Agent, AgentEvent, CodingTools, EventBus,  # noqa: E402
                      LongTermMemory, Plan, ShortTermMemory, ToolRegistry,
                      add_subagent, coding_tools)
from agentkit.events import DONE, FINAL, TOOL_CALL, TOOL_RESULT  # noqa: E402
from agentkit.mcp import mcp_tools_to_schemas  # noqa: E402


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
        self.seen_messages = []

    def stream(self, messages, tools=None):
        self.seen_messages.append(list(messages))
        turn = self.turns[self.i]
        self.i += 1
        return iter(turn)

    def complete(self, messages, tools=None):
        return SimpleNamespace(content="komprimierte Zusammenfassung", tool_calls=None)


# ------------------------------------------------------------------ Tools
def test_tool_auto_schema_and_call():
    reg = ToolRegistry()

    @reg.tool()
    def add(a: int, b: int) -> int:
        """Addiert zwei Zahlen."""
        return a + b

    schema = reg.schemas()[0]["function"]
    assert schema["name"] == "add"
    assert schema["description"] == "Addiert zwei Zahlen."
    assert schema["parameters"]["properties"]["a"]["type"] == "integer"
    assert set(schema["parameters"]["required"]) == {"a", "b"}
    assert reg.call("add", {"a": 2, "b": 3}) == 5


def test_tool_unknown_is_soft_error():
    reg = ToolRegistry()
    assert "ERROR" in str(reg.call("nope", {}))


# ----------------------------------------------------------------- Memory
def test_short_term_compaction_keeps_system_and_tail():
    mem = ShortTermMemory(system="SYS")
    for i in range(10):
        mem.add({"role": "user", "content": f"nachricht {i}"})
    compacted = mem.compact(FakeLLM([]), keep_last=3)
    assert compacted is True
    assert mem.messages[0] == {"role": "system", "content": "SYS"}
    # Eine Compaction-Notiz + die letzten 3 Originale.
    assert mem.messages[1]["role"] == "system"
    assert mem.messages[-1]["content"] == "nachricht 9"
    assert len(mem.messages) == 1 + 1 + 3


def test_long_term_memory_roundtrip(tmp_path):
    path = tmp_path / "mem.jsonl"
    ltm = LongTermMemory(str(path))
    ltm.remember("Rudi mag Kaffee am Morgen")
    ltm.remember("Das Projekt heißt fsod")
    assert "Kaffee" in ltm.recall("kaffee")
    # Persistenz: neue Instanz liest die Datei.
    again = LongTermMemory(str(path))
    assert len(again.items) == 2
    # register_tools bietet remember/recall an.
    reg = ToolRegistry()
    ltm.register_tools(reg)
    assert reg.has("remember") and reg.has("recall")


# ----------------------------------------------------------------- Events
def test_eventbus_fans_out_to_all_subscribers():
    bus = EventBus()
    a, b = bus.subscribe(), bus.subscribe()
    bus.publish(AgentEvent("step", {"step": 1}))
    assert a.get_nowait().data == {"step": 1}
    assert b.get_nowait().data == {"step": 1}


# -------------------------------------------------------------------- MCP
def test_mcp_tools_to_schemas():
    fake = SimpleNamespace(name="add", description="adds",
                           inputSchema={"type": "object", "properties": {}})
    out = mcp_tools_to_schemas([fake])
    assert out[0]["function"]["name"] == "add"
    assert out[0]["type"] == "function"


# ----------------------------------------------------------- Agent-Loop
def _agent_with_tool():
    reg = ToolRegistry()

    @reg.tool()
    def add(a: int, b: int) -> int:
        """Addiert zwei Zahlen."""
        return a + b

    turns = [
        # Turn 1: Modell fordert das Tool an.
        [_chunk(tool={"id": "c1", "name": "add", "arguments": json.dumps({"a": 2, "b": 3})})],
        # Turn 2: finale Antwort, Token für Token.
        [_chunk(content="Das Ergebnis "), _chunk(content="ist 5.")],
    ]
    return Agent(FakeLLM(turns), tools=reg, strategy="plain")


def test_agent_runs_tool_then_answers():
    agent = _agent_with_tool()
    events = list(agent.run_iter("Was ist 2+3?"))
    types = [e.type for e in events]
    assert TOOL_CALL in types and TOOL_RESULT in types
    tool_result = next(e for e in events if e.type == TOOL_RESULT)
    assert tool_result.data["result"] == "5"
    final = next(e for e in events if e.type == FINAL)
    assert final.data == "Das Ergebnis ist 5."


def test_agent_run_returns_final_string():
    agent = _agent_with_tool()
    assert agent.run("Was ist 2+3?") == "Das Ergebnis ist 5."


def test_agent_strategy_injects_preamble():
    agent = Agent(FakeLLM([]), strategy="plan", system="Sei knapp.")
    sys_msg = agent.memory.messages[0]["content"]
    assert "Plan-and-Execute" in sys_msg and "Sei knapp." in sys_msg


def test_agent_cancel_before_start():
    agent = _agent_with_tool()
    cancel = threading.Event()
    cancel.set()
    events = list(agent.run_iter("egal", cancel=cancel))
    assert events[0].type == "cancelled"


def test_agent_run_on_bus_emits_done():
    agent = _agent_with_tool()
    bus = EventBus()
    q = bus.subscribe()
    agent.run_on_bus("Was ist 2+3?", bus, task_id=7)
    seen = []
    while not q.empty():
        seen.append(q.get_nowait())
    assert seen[-1].type == DONE
    assert all(e.task_id == 7 for e in seen)


# ---------------------------------------------------------------- Planning
def test_plan_update_and_render():
    plan = Plan()
    out = plan.update([
        {"step": "Code schreiben", "status": "done"},
        {"step": "Tests", "status": "in_progress"},
        {"step": "Aufräumen", "status": "pending"},
    ])
    assert "[x] 1. Code schreiben" in out
    assert "[~] 2. Tests" in out
    assert "[ ] 3. Aufräumen" in out


def test_plan_registers_update_plan_tool_and_fires_callback():
    seen = {}
    plan = Plan(on_update=lambda p: seen.setdefault("steps", len(p.steps)))
    reg = ToolRegistry()
    plan.register_tool(reg)
    assert reg.has("update_plan")
    reg.call("update_plan", {"steps": [{"step": "A", "status": "pending"}]})
    assert seen["steps"] == 1


# ----------------------------------------------------------- Coding-Tools
def test_coding_tools_sandbox_and_io(tmp_path):
    ct = CodingTools(workspace=str(tmp_path), approval=False)
    reg = ToolRegistry()
    ct.register(reg)
    assert "20 Zeichen" in reg.call("write_file", {"path": "a.txt", "content": "x" * 20})
    assert reg.call("read_file", {"path": "a.txt"}) == "x" * 20
    assert "a.txt" in reg.call("list_files", {"path": "."})
    # edit_file
    reg.call("write_file", {"path": "b.txt", "content": "hallo welt"})
    reg.call("edit_file", {"path": "b.txt", "old": "welt", "new": "agent"})
    assert reg.call("read_file", {"path": "b.txt"}) == "hallo agent"
    # Sandbox-Ausbruch wird verhindert (im Agent-Loop würde daraus ein ERROR-Ergebnis)
    import pytest
    with pytest.raises(ValueError):
        reg.call("read_file", {"path": "../../etc/passwd"})


def test_coding_tools_run_shell_no_approval(tmp_path):
    reg = coding_tools(workspace=str(tmp_path), approval=False)
    out = reg.call("run_shell", {"command": "echo hallo"})
    assert "hallo" in out and "exit=0" in out


# ------------------------------------------------------- Parallel + Subagents
def test_parallel_tools_preserve_order_and_pairing():
    reg = ToolRegistry()

    @reg.tool()
    def slow(x: int) -> int:
        """Verdoppelt x."""
        import time
        time.sleep(0.05)
        return x * 2

    # Eine Antwort mit DREI Tool-Calls -> parallel ausgeführt.
    turn1 = [
        _chunk(tool={"id": "t0", "name": "slow", "arguments": '{"x": 1}'}, index=0),
        _chunk(tool={"id": "t1", "name": "slow", "arguments": '{"x": 2}'}, index=1),
        _chunk(tool={"id": "t2", "name": "slow", "arguments": '{"x": 3}'}, index=2),
    ]
    turn2 = [_chunk(content="fertig")]
    agent = Agent(FakeLLM([turn1, turn2]), tools=reg, strategy="plain", parallel_tools=True)
    events = list(agent.run_iter("rechne"))
    results = [e.data["result"] for e in events if e.type == TOOL_RESULT]
    assert results == ["2", "4", "6"]  # Reihenfolge erhalten
    # tool-Nachrichten tragen die passenden IDs in Reihenfolge
    tool_msgs = [m for m in agent.memory.messages if m.get("role") == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["t0", "t1", "t2"]


def test_add_subagent_registers_delegate_tool():
    orch = ToolRegistry()
    # Sub-Agent gibt einfach "fertig" zurück.
    sub_llm = FakeLLM([[_chunk(content="Steckbrief Wien")]])
    add_subagent(orch, "delegate", "Delegiert einen Auftrag.", sub_llm,
                 system="Recherche.", strategy="plain")
    assert orch.has("delegate")
    assert orch.call("delegate", {"auftrag": "Wien"}) == "Steckbrief Wien"
