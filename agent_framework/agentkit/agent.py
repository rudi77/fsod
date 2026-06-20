"""Der Agent — ein LLM in einer Schleife mit Tools.

Derselbe Loop wie in den Notebooks, hier streamend und event-basiert:

    solange das Modell ein Tool aufruft:
        Tool ausführen -> Ergebnis anhängen -> Modell erneut fragen
    sonst:
        finale Antwort

`run_iter()` ist ein Generator, der `AgentEvent`s liefert (Streaming-Tokens,
Tool-Calls, Ergebnisse, finale Antwort). Darauf bauen die bequemen Methoden
`run()` (sammelt die finale Antwort) und `run_on_bus()` (für Worker-Threads +
mehrere Consumer) auf.

ReAct vs. Plan-and-Execute steuert nur der System-Prompt — `strategy=`.
Harness: max_steps, Retries, Fehlertoleranz, Compaction, kooperatives Abbrechen.
"""

from __future__ import annotations

import json
from typing import Callable, Iterator, Optional

from .events import (AgentEvent, CANCELLED, DONE, ERROR, FINAL, STEP,
                     TEXT_DELTA, TOOL_CALL, TOOL_RESULT)
from .memory import ShortTermMemory, truncate
from .tools import ToolRegistry

REACT_PREAMBLE = (
    "Arbeite nach dem ReAct-Muster: Überlege in kurzen Schritten, was als Nächstes "
    "sinnvoll ist, rufe dann ein Tool auf, beobachte das Ergebnis und entscheide den "
    "nächsten Schritt. Wenn du genug weißt, antworte final ohne weiteren Tool-Aufruf."
)

PLAN_PREAMBLE = (
    "Arbeite nach dem Muster Plan-and-Execute: Erstelle ZUERST einen kurzen, "
    "nummerierten Plan (1., 2., 3.) für die Aufgabe. Arbeite den Plan danach Schritt "
    "für Schritt mit Tools ab und nenne am Ende das Ergebnis."
)

_PREAMBLES = {"react": REACT_PREAMBLE, "plan": PLAN_PREAMBLE, "plain": ""}


def to_assistant_dict(content: Optional[str], tool_calls: list) -> dict:
    """content + tool_calls -> serialisierbares Assistant-Dict für die Historie."""
    d = {"role": "assistant", "content": content or ""}
    if tool_calls:
        d["tool_calls"] = tool_calls
    return d


class Agent:
    def __init__(self, llm, tools: Optional[ToolRegistry] = None,
                 system: Optional[str] = None, strategy: str = "react",
                 long_term=None, max_steps: int = 12, token_budget: int = 8000,
                 memory: Optional[ShortTermMemory] = None):
        if strategy not in _PREAMBLES:
            raise ValueError(f"strategy muss eine von {list(_PREAMBLES)} sein, war '{strategy}'")
        self.llm = llm
        self.tools = tools or ToolRegistry()
        self.strategy = strategy
        self.max_steps = max_steps
        self.token_budget = token_budget

        # Langzeitgedächtnis als Tools (remember/recall) einklinken.
        self.long_term = long_term
        if long_term is not None:
            long_term.register_tools(self.tools)

        system_prompt = self._build_system(system, strategy)
        if memory is None:
            self.memory = ShortTermMemory(system_prompt)
        else:
            self.memory = memory
            if system_prompt and not any(m.get("role") == "system" for m in memory.messages):
                memory.messages.insert(0, {"role": "system", "content": system_prompt})

    @staticmethod
    def _build_system(system: Optional[str], strategy: str) -> Optional[str]:
        parts = [p for p in (_PREAMBLES[strategy], system) if p]
        return "\n\n".join(parts) or None

    # ----------------------------------------------------------------- core
    def run_iter(self, task: str, cancel=None) -> Iterator[AgentEvent]:
        """Arbeitet einen Auftrag ab und liefert dabei `AgentEvent`s.

        `cancel` ist ein optionales `threading.Event` (der Stop-Knopf): an
        sicheren Punkten (Schritt-Grenze, Token-Stream, vor jedem Tool) wird
        kooperativ abgebrochen.
        """
        mem = self.memory
        mem.add_user(task)

        def stopped() -> bool:
            return cancel is not None and cancel.is_set()

        for step in range(1, self.max_steps + 1):
            if stopped():
                yield AgentEvent(CANCELLED, {"where": f"vor Schritt {step}"})
                return

            # Harness: Kontext klein halten.
            if mem.tokens() > self.token_budget:
                mem.compact(self.llm)

            yield AgentEvent(STEP, {"step": step})

            # 1) Modell streamen; Text-Deltas als Events; tool_calls rekonstruieren.
            content, tool_calls = None, None
            for kind, payload in self._consume_stream(mem.messages, stopped):
                if kind == "text":
                    yield AgentEvent(TEXT_DELTA, payload)
                else:
                    content, tool_calls = payload
            mem.add(to_assistant_dict(content, tool_calls))

            if stopped():
                yield AgentEvent(CANCELLED, {"where": "mitten im Stream"})
                return

            # 2) Keine Tools mehr -> fertig.
            if not tool_calls:
                yield AgentEvent(FINAL, content)
                return

            # 3) Alle angeforderten Tools ausführen (Fehler werden zum Ergebnis).
            for tc in tool_calls:
                if stopped():
                    yield AgentEvent(CANCELLED, {"where": "vor Tool-Aufruf"})
                    return
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield AgentEvent(TOOL_CALL, {"name": name, "args": args})
                try:
                    result = str(self.tools.call(name, args))
                except Exception as e:  # Fehler ist auch ein Ergebnis -> Selbstkorrektur
                    result = f"ERROR: {e}"
                    yield AgentEvent(ERROR, {"name": name, "error": str(e)})
                result = truncate(result)
                yield AgentEvent(TOOL_RESULT, {"name": name, "result": result})
                mem.add({"role": "tool", "tool_call_id": tc["id"], "content": result})

        yield AgentEvent(FINAL, "(max_steps erreicht)")

    def _consume_stream(self, messages, should_stop):
        """Konsumiert den Streaming-Iterator: yieldet ('text', delta) pro Token
        und am Ende ('done', (content, tool_calls)). Setzt fragmentierte
        tool_call-Deltas pro `index` wieder zusammen."""
        content_parts = []
        tool_calls = {}  # index -> {"id","name","args":[...]}
        stream = self._stream_with_retry(messages)
        for chunk in stream:
            if should_stop():
                try:
                    stream.close()
                except Exception:
                    pass
                break
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                content_parts.append(delta.content)
                yield ("text", delta.content)

            for tc in (delta.tool_calls or []):
                slot = tool_calls.setdefault(tc.index, {"id": None, "name": None, "args": []})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    slot["args"].append(tc.function.arguments)

        calls = [{
            "id": s["id"], "type": "function",
            "function": {"name": s["name"], "arguments": "".join(s["args"]) or "{}"},
        } for _, s in sorted(tool_calls.items())]
        yield ("done", ("".join(content_parts), calls))

    def _stream_with_retry(self, messages, attempts: int = 3):
        """Retry bei transienten API-Fehlern beim Aufbau des Streams."""
        last = None
        for _ in range(attempts):
            try:
                return self.llm.stream(messages, self.tools.schemas())
            except Exception as e:
                last = e
        raise last

    # ------------------------------------------------------------- bequem
    def run(self, task: str, cancel=None,
            on_event: Optional[Callable[[AgentEvent], None]] = None) -> str:
        """Arbeitet den Auftrag ab und gibt die finale Antwort als String zurück.
        `on_event` bekommt (optional) jedes Event zur Live-Anzeige."""
        final = "(keine Antwort)"
        for ev in self.run_iter(task, cancel=cancel):
            if on_event:
                on_event(ev)
            if ev.type in (FINAL, CANCELLED):
                final = ev.data if isinstance(ev.data, str) else "(abgebrochen)"
        return final

    def run_on_bus(self, task: str, bus, task_id: int = -1, cancel=None) -> None:
        """Arbeitet den Auftrag ab und publiziert jedes Event auf einen EventBus.
        Schließt mit einem DONE-Event. Ideal für Worker-Threads + mehrere Consumer."""
        try:
            for ev in self.run_iter(task, cancel=cancel):
                ev.task_id = task_id
                bus.publish(ev)
        except Exception as e:
            bus.publish(AgentEvent(ERROR, {"error": str(e)}, task_id))
        bus.publish(AgentEvent(DONE, None, task_id))
