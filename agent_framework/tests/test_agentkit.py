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
                      LongTermMemory, Plan, ROLES, ShortTermMemory, Skills,
                      ToolRegistry, add_subagent, add_task_tool, coding_tools,
                      skills_tools)
from agentkit.coding import READ_ONLY_TOOLS  # noqa: E402
from agentkit.roles import load_roles_from_dir  # noqa: E402
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


def test_coding_tools_glob_and_grep(tmp_path):
    reg = coding_tools(workspace=str(tmp_path), approval=False)
    reg.call("write_file", {"path": "src/app.py", "content": "def hello():\n    return 42\n"})
    reg.call("write_file", {"path": "src/util.py", "content": "x = 1\n"})
    reg.call("write_file", {"path": "README.md", "content": "# Doku\n"})
    # glob_files: nur Python-Dateien, plattformneutrale '/'-Pfade
    py = reg.call("glob_files", {"pattern": "**/*.py"})
    assert "src/app.py" in py and "src/util.py" in py and "README.md" not in py
    # grep: findet Inhalt mit Pfad:Zeile
    hit = reg.call("grep", {"pattern": "return", "glob": "**/*.py"})
    assert "src/app.py:2:" in hit and "return 42" in hit
    # Ignore-Ordner werden übersprungen
    reg.call("write_file", {"path": ".git/config.py", "content": "return 99\n"})
    assert ".git" not in reg.call("grep", {"pattern": "return"})
    # Ungültiges Regex -> Fehlertext statt Crash
    assert "ERROR" in reg.call("grep", {"pattern": "([unbalanced"})


def test_coding_tools_run_shell_no_approval(tmp_path):
    reg = coding_tools(workspace=str(tmp_path), approval=False)
    out = reg.call("run_shell", {"command": "echo hallo"})
    assert "hallo" in out and "exit=0" in out


# ------------------------------------------------------------------ Skills
def _write_skill(root, folder, name, description, body="Schritt 1. Tu etwas."):
    d = root / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\n{body}\n",
        encoding="utf-8",
    )


def test_skills_index_only_frontmatter(tmp_path):
    _write_skill(tmp_path, "alpha", "alpha", "Macht A", body="GEHEIMER LANGER BODY")
    _write_skill(tmp_path, "beta", "beta", "Macht B")
    sk = Skills(str(tmp_path))
    idx = sk.index()
    assert {s["name"] for s in idx} == {"alpha", "beta"}
    # Discovery liefert NUR Frontmatter -> der Body ist (noch) nicht im Index.
    assert "GEHEIMER LANGER BODY" not in sk.list_skills()
    assert any(s["description"] == "Macht A" for s in idx)


def test_skills_read_full_body_on_demand(tmp_path):
    _write_skill(tmp_path, "alpha", "alpha", "Macht A", body="GEHEIMER LANGER BODY")
    sk = Skills(str(tmp_path))
    # read_skill lädt die ganze SKILL.md (progressive disclosure).
    assert "GEHEIMER LANGER BODY" in sk.read_skill("alpha")
    assert "kein Skill" in sk.read_skill("gibtsnicht")


def test_skills_read_by_folder_name_when_frontmatter_differs(tmp_path):
    # Frontmatter-Name weicht vom Ordnernamen ab -> beide Wege müssen finden.
    _write_skill(tmp_path, "ordner-x", "anzeige-name", "Beschreibung")
    sk = Skills(str(tmp_path))
    assert "anzeige-name" in sk.read_skill("anzeige-name")
    assert "anzeige-name" in sk.read_skill("ordner-x")


def test_skills_register_tools_and_missing_dir(tmp_path):
    _write_skill(tmp_path, "alpha", "alpha", "Macht A")
    reg = skills_tools(skills_dir=str(tmp_path))
    assert reg.has("list_skills") and reg.has("read_skill")
    assert "alpha" in reg.call("list_skills", {})
    # Fehlendes Verzeichnis -> leerer Index, kein Crash.
    empty = Skills(str(tmp_path / "gibtsnicht"))
    assert empty.index() == []


def test_agent_skills_param_registers_tools():
    agent = Agent(FakeLLM([]), skills=Skills("./does-not-matter"), strategy="plain")
    assert agent.tools.has("list_skills") and agent.tools.has("read_skill")


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


def test_coding_register_only_subset(tmp_path):
    # only= beschränkt auf eine Tool-Teilmenge (read-only -> kein write/edit/shell).
    reg = ToolRegistry()
    CodingTools(workspace=str(tmp_path), approval=False).register(reg, only=READ_ONLY_TOOLS)
    names = set(reg.names())
    assert names == set(READ_ONLY_TOOLS)
    assert "write_file" not in names and "run_shell" not in names


def test_roles_presets_have_expected_tool_subsets():
    assert set(ROLES) == {"explorer", "reviewer", "tester"}
    assert ROLES["explorer"].tools == READ_ONLY_TOOLS      # read-only
    assert ROLES["reviewer"].tools == READ_ONLY_TOOLS      # read-only
    assert "run_shell" in ROLES["tester"].tools            # tester darf Tests ausführen
    assert "write_file" not in ROLES["tester"].tools       # aber keinen Code schreiben


def test_add_task_tool_registers_and_delegates(tmp_path):
    # Ohne aktiven Bus (Library-Nutzung) gibt das task-Tool nur das Sub-Ergebnis zurück.
    sub_llm = FakeLLM([[_chunk(content="Architektur-Überblick")]])
    orchestrator = Agent(FakeLLM([]), strategy="plain")
    add_task_tool(orchestrator.tools, agent=orchestrator, llm=sub_llm,
                  workspace=str(tmp_path), approval=False)
    assert orchestrator.tools.has("task")
    # Schema bietet subagent_type als Enum (Rollen + general) an.
    schema = next(s for s in orchestrator.tools.schemas() if s["function"]["name"] == "task")
    enum = schema["function"]["parameters"]["properties"]["subagent_type"]["enum"]
    assert "explorer" in enum and "general" in enum
    out = orchestrator.tools.call("task", {"subagent_type": "explorer", "prompt": "Erkunde es"})
    assert out == "Architektur-Überblick"


def test_task_tool_forwards_subagent_events_to_active_bus(tmp_path):
    bus = EventBus()
    q = bus.subscribe()

    sub_llm = FakeLLM([[_chunk(content="explorer fertig")]])
    orch_llm = FakeLLM([
        [_chunk(tool={"id": "t0", "name": "task",
                      "arguments": '{"subagent_type": "explorer", "prompt": "Erkunde"}'})],
        [_chunk(content="Bericht fertig")],
    ])
    orchestrator = Agent(orch_llm, strategy="plain")
    add_task_tool(orchestrator.tools, agent=orchestrator, llm=sub_llm,
                  workspace=str(tmp_path), approval=False)

    final = orchestrator.run_on_bus("Erkunde das Repo.", bus, source="")

    seen = []
    while not q.empty():
        seen.append(q.get_nowait())

    # Sub-Agent-Events sind mit der Rolle getaggt; der Orchestrator mit "".
    assert any(e.source.startswith("explorer:") for e in seen)
    sub_finals = [e for e in seen if e.source.startswith("explorer:") and e.type == FINAL]
    assert sub_finals and sub_finals[0].data == "explorer fertig"
    # Der Orchestrator bekommt das Sub-Ergebnis als Tool-Ergebnis; Root-DONE trägt source="".
    tool_results = [e for e in seen if e.source == "" and e.type == TOOL_RESULT]
    assert tool_results[0].data["result"] == "explorer fertig"
    assert seen[-1].type == DONE and seen[-1].source == ""
    assert final == "Bericht fertig"


def _write_agent_md(root, filename, frontmatter, body):
    root.mkdir(parents=True, exist_ok=True)
    fm = "\n".join(f"{k}: {v}" for k, v in frontmatter.items())
    (root / filename).write_text(f"---\n{fm}\n---\n\n{body}\n", encoding="utf-8")


def test_load_roles_from_dir_parses_frontmatter_and_body(tmp_path):
    _write_agent_md(tmp_path, "security-reviewer.md",
                    {"name": "security-reviewer",
                     "description": "Security-Review.", "tools": "read_only"},
                    "Du bist ein Security-Reviewer. GEHEIMER PROMPT-BODY.")
    _write_agent_md(tmp_path, "doc-writer.md",
                    {"name": "doc-writer", "description": "Schreibt Doku.",
                     "tools": "read_file, write_file", "strategy": "plan"},
                    "Du schreibst Dokumentation.")

    roles = load_roles_from_dir(str(tmp_path))
    assert set(roles) == {"security-reviewer", "doc-writer"}
    sec = roles["security-reviewer"]
    assert sec.tools == READ_ONLY_TOOLS                  # 'read_only'-Kürzel
    assert "GEHEIMER PROMPT-BODY" in sec.system          # Body = System-Prompt
    assert sec.strategy == "react"                       # Default
    doc = roles["doc-writer"]
    assert doc.tools == ("read_file", "write_file")      # explizite Liste
    assert doc.strategy == "plan"
    # Fehlender Ordner -> leeres Dict, kein Crash.
    assert load_roles_from_dir(str(tmp_path / "gibtsnicht")) == {}


def test_load_roles_without_tools_field_means_all_tools(tmp_path):
    _write_agent_md(tmp_path, "general-helper.md",
                    {"name": "general-helper", "description": "Alles."},
                    "Du hilfst bei allem.")
    role = load_roles_from_dir(str(tmp_path))["general-helper"]
    assert role.tools is None  # None = alle Coding-Tools


def test_cli_agents_flag_merges_custom_roles(tmp_path, monkeypatch):
    from agentkit import cli
    _write_agent_md(tmp_path, "security-reviewer.md",
                    {"name": "security-reviewer", "description": "Security.", "tools": "read_only"},
                    "Du bist ein Security-Reviewer.")
    args = cli.build_parser().parse_args(
        ["-w", str(tmp_path), "--agents", str(tmp_path), "--provider", "openai"])
    monkeypatch.setattr(cli, "build_llm", lambda provider: FakeLLM([]))
    agent, tools, plan, skills, roles = cli.build_agent(args)
    # Eingebaute + Custom-Rolle sind aktiv.
    assert "security-reviewer" in roles and "explorer" in roles
    # Custom-Typ steht im task-Schema-Enum (also für das Modell wählbar).
    schema = next(s for s in tools.schemas() if s["function"]["name"] == "task")
    assert "security-reviewer" in schema["function"]["parameters"]["properties"]["subagent_type"]["enum"]


def test_add_subagent_registers_delegate_tool():
    orch = ToolRegistry()
    # Sub-Agent gibt einfach "fertig" zurück.
    sub_llm = FakeLLM([[_chunk(content="Steckbrief Wien")]])
    add_subagent(orch, "delegate", "Delegiert einen Auftrag.", sub_llm,
                 system="Recherche.", strategy="plain")
    assert orch.has("delegate")
    assert orch.call("delegate", {"auftrag": "Wien"}) == "Steckbrief Wien"


# ---------------------------------------------------------------------- CLI
def test_cli_run_task_renders_and_returns_final(capsys):
    from agentkit import cli
    cli.C.disable()  # keine ANSI-Codes im Test

    agent = _agent_with_tool()
    renderer = cli.Renderer()
    final = cli.run_task(agent, "Was ist 2+3?", renderer)

    out = capsys.readouterr().out
    assert final == "Das Ergebnis ist 5."
    assert "⏺ add" in out                 # Tool-Aufruf wurde gerendert
    assert "Das Ergebnis ist 5." in out   # gestreamter Text wurde gerendert


def test_cli_quiet_renderer_is_silent(capsys):
    from agentkit import cli
    cli.C.disable()

    agent = _agent_with_tool()
    final = cli.run_task(agent, "Was ist 2+3?", cli.Renderer(quiet=True))
    out = capsys.readouterr().out
    assert final == "Das Ergebnis ist 5."
    assert out == ""  # im --print-Modus erscheint live nichts


def test_cli_yes_flag_disables_shell_approval(tmp_path, monkeypatch):
    # --yes -> CodingTools wird mit approval=False gebaut, der confirm_shell-Callback
    # läuft also gar nicht erst (run_shell führt ohne Rückfrage aus).
    from agentkit import cli
    args = cli.build_parser().parse_args(["-y", "-w", str(tmp_path), "--provider", "openai"])
    monkeypatch.setattr(cli, "build_llm", lambda provider: FakeLLM([]))  # kein echter LLM nötig
    agent, *_ = cli.build_agent(args)
    out = agent.tools.call("run_shell", {"command": "echo hi"})
    assert "hi" in out and "ABGELEHNT" not in out


def test_cli_build_llm_auto_without_creds_errors(monkeypatch):
    from agentkit import cli
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import pytest
    with pytest.raises(SystemExit):
        cli.build_llm("auto")


def test_cli_handle_slash_tools_and_exit(capsys):
    from agentkit import cli
    cli.C.disable()
    agent = _agent_with_tool()
    reg = agent.tools
    plan = Plan()

    # /tools listet registrierte Tools, Session läuft weiter.
    assert cli.handle_slash("/tools", agent, reg, plan, None) is True
    assert "add" in capsys.readouterr().out
    # /exit beendet die Session.
    assert cli.handle_slash("/exit", agent, reg, plan, None) is False


def test_cli_handle_slash_reset_keeps_system_message():
    from agentkit import cli
    agent = Agent(FakeLLM([]), strategy="plan", system="Sei knapp.")
    # Unterhaltung anreichern, dann zurücksetzen.
    agent.memory.add_user("hallo")
    cli.handle_slash("/reset", agent, agent.tools, Plan(), None)
    roles = [m["role"] for m in agent.memory.messages]
    assert roles == ["system"]  # nur die System-Nachricht bleibt
    assert "Plan-and-Execute" in agent.memory.messages[0]["content"]


def test_cli_parser_defaults_and_oneshot():
    from agentkit import cli
    args = cli.build_parser().parse_args(["Schreibe", "fizzbuzz"])
    assert args.prompt == ["Schreibe", "fizzbuzz"]
    assert args.strategy == "react"
    assert args.workspace == "."
    assert args.yes is False


def test_subagent_forwards_events_to_shared_bus():
    bus = EventBus()
    q = bus.subscribe()

    # Sub-Agent: ein Token + finale Antwort.
    sub_llm = FakeLLM([[_chunk(content="Steckbrief Wien")]])
    orch_tools = ToolRegistry()
    add_subagent(orch_tools, "delegate", "Delegiert.", sub_llm,
                 system="Recherche.", strategy="plain", bus=bus)

    # Orchestrator: ruft delegate, dann finale Antwort.
    orch_llm = FakeLLM([
        [_chunk(tool={"id": "d0", "name": "delegate", "arguments": '{"auftrag": "Wien"}'})],
        [_chunk(content="Tabelle fertig")],
    ])
    orchestrator = Agent(orch_llm, tools=orch_tools, strategy="plain")
    final = orchestrator.run_on_bus("Vergleiche Wien.", bus, source="")

    seen = []
    while not q.empty():
        seen.append(q.get_nowait())

    sources = {e.source for e in seen}
    assert "delegate:Wien" in sources          # Sub-Agent-Events sind getaggt
    assert "" in sources                       # Orchestrator-Events ebenfalls dabei

    # Sub-Agent-Token + finale Antwort wurden weitergeleitet.
    sub_finals = [e for e in seen if e.source == "delegate:Wien" and e.type == FINAL]
    assert sub_finals and sub_finals[0].data == "Steckbrief Wien"

    # Der Orchestrator hat das Sub-Ergebnis als Tool-Ergebnis bekommen.
    tool_results = [e for e in seen if e.source == "" and e.type == TOOL_RESULT]
    assert tool_results[0].data["result"] == "Steckbrief Wien"

    # Jeder Sub-Agent schließt mit eigenem DONE; der Root-DONE trägt source="".
    assert any(e.type == DONE and e.source == "delegate:Wien" for e in seen)
    assert seen[-1].type == DONE and seen[-1].source == ""
    assert final == "Tabelle fertig"
