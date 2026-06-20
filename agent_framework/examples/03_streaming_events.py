"""Beispiel 3 — Event-Bus, Worker-Thread und Stop-Knopf.

Der Agent läuft in einem Worker-Thread und publiziert Events auf einen EventBus.
Zwei Consumer hören parallel: einer rendert live, einer zählt Metriken. Ein
`threading.Event` ist der Stop-Knopf (kooperatives Abbrechen).

    python examples/03_streaming_events.py
"""
import threading
import time

from dotenv import load_dotenv

from agentkit import Agent, EventBus, azure_from_env
from agentkit.events import DONE, STEP, TEXT_DELTA, TOOL_CALL, CANCELLED

load_dotenv()


def ui_consumer(q):
    while True:
        ev = q.get()
        if ev.type == STEP:
            print(f"\n[#{ev.task_id} Schritt {ev.data['step']}] ", end="", flush=True)
        elif ev.type == TEXT_DELTA:
            print(ev.data, end="", flush=True)
        elif ev.type == TOOL_CALL:
            print(f"\n  🔧 {ev.data['name']}({ev.data['args']})", flush=True)
        elif ev.type == CANCELLED:
            print(f"\n  ⛔ abgebrochen ({ev.data['where']})", flush=True)
        elif ev.type == DONE:
            return


def metrics_consumer(q):
    tokens = 0
    while True:
        ev = q.get()
        if ev.type == TEXT_DELTA:
            tokens += 1
        elif ev.type == DONE:
            print(f"\n\n📊 (zweiter Consumer) {tokens} Token-Deltas gezählt.")
            return


if __name__ == "__main__":
    agent = azure_from_env()
    bus = EventBus()
    ui_q, metrics_q = bus.subscribe(), bus.subscribe()
    cancel = threading.Event()

    ui = threading.Thread(target=ui_consumer, args=(ui_q,), daemon=True)
    metrics = threading.Thread(target=metrics_consumer, args=(metrics_q,), daemon=True)
    ui.start()
    metrics.start()

    a = Agent(agent, strategy="plain")
    worker = threading.Thread(
        target=a.run_on_bus,
        args=("Schreibe einen langen, mehrere Absätze langen Text über die Geschichte der "
              "Programmiersprachen.",),
        kwargs={"bus": bus, "task_id": 0, "cancel": cancel},
        daemon=True,
    )
    worker.start()

    time.sleep(2.0)  # kurz streamen lassen ...
    print("\n\n>>> STOP-KNOPF <<<", flush=True)
    cancel.set()     # ... dann mittendrin abbrechen

    ui.join()
    metrics.join()
    worker.join()
    print("\n— fertig —")
