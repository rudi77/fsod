"""Events & Event-Bus — *was passiert* entkoppelt von *wie es angezeigt wird*.

Der Agent-Loop `publish`-t neutrale, typisierte `AgentEvent`s. Das ist der
ganze Trick hinter "Streaming" und "Event-basiert": ein Producer/Consumer-Muster
um denselben Loop. Mehrere Consumer (UI-Renderer, Metriken, Logger) abonnieren
denselben Strom.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any, List

# Event-Typen (schlichte Konstanten statt Enum-Overhead)
STEP = "step"                # ein neuer Loop-Schritt beginnt
TEXT_DELTA = "text_delta"    # ein Stück der Antwort (Streaming-Token)
TOOL_CALL = "tool_call"      # Agent ruft ein Tool auf
TOOL_RESULT = "tool_result"  # Ergebnis eines Tools
PLAN = "plan"                # der Agent hat seinen Plan / seine Todo-Liste aktualisiert
FINAL = "final"              # finale Antwort steht
ERROR = "error"              # ein Tool/Call ist schiefgegangen
CANCELLED = "cancelled"      # Auftrag wurde mittendrin abgebrochen
DONE = "done"                # Auftrag komplett abgearbeitet (auch nach Abbruch)


@dataclass
class AgentEvent:
    type: str
    data: Any = None
    task_id: int = -1


class EventBus:
    """Minimaler Pub/Sub: ein `publish`, beliebig viele Subscriber-Queues."""

    def __init__(self):
        self._subscribers: List[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> "queue.Queue":
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def publish(self, event: AgentEvent) -> None:
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            q.put(event)
