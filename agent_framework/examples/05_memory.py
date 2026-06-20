"""Beispiel 5 — Kurzzeit- und Langzeitgedächtnis.

- Kurzzeit: derselbe Agent über mehrere Turns -> Folgefragen funktionieren.
- Langzeit: `LongTermMemory` gibt dem Agenten die Tools `remember`/`recall`;
  der Inhalt überdauert den Programmlauf (JSONL-Datei).

    python examples/05_memory.py
"""
from dotenv import load_dotenv

from agentkit import Agent, LongTermMemory, azure_from_env

load_dotenv()

if __name__ == "__main__":
    ltm = LongTermMemory("agent_memory.jsonl")
    agent = Agent(azure_from_env(), long_term=ltm, strategy="react")

    # Turn 1 — etwas merken (der Agent nutzt das remember-Tool).
    print(agent.run("Merke dir bitte dauerhaft: Mein Lieblingseditor ist Neovim."))

    # Turn 2 — Kurzzeitgedächtnis: der Agent kennt den Kontext aus Turn 1.
    print(agent.run("Worum ging es gerade?"))

    # Turn 3 — Langzeitgedächtnis: in einer FRISCHEN Session abrufbar.
    fresh = Agent(azure_from_env(), long_term=LongTermMemory("agent_memory.jsonl"),
                  strategy="react")
    print(fresh.run("Welchen Editor mag ich? Schau im Langzeitgedächtnis nach."))
