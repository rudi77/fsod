# agentkit — Spezifikationen

Verhaltens-orientierte Specs: **was** jedes Subsystem für den Nutzer leistet,
nicht **wie** es implementiert ist. Ein Refactor, der eine Klasse umbenennt oder
eine Datei verschiebt, darf eine Spec nicht brechen — eine echte Regression (eine
fehlende Fähigkeit, eine verletzte Invariante) soll sie brechen.

Eine Datei pro Subsystem. Geprüft gegen den Code via `/spec-check`.

| Spec | Subsystem | Code | Status |
|---|---|---|---|
| [agentic-loop](agentic-loop.md) | Der Agent-Loop (ReAct/Plan, Streaming, Harness) | `agentkit/agent.py` | shipped |
| [tool-registry](tool-registry.md) | Tools als Funktion + JSON-Schema | `agentkit/tools.py` | shipped |
| [events](events.md) | Typisierte Events + Pub/Sub-Bus | `agentkit/events.py` | shipped |
| [memory](memory.md) | Kurzzeit- (Compaction) und Langzeitgedächtnis | `agentkit/memory.py` | shipped |
| [planning](planning.md) | Mitgeführte Todo-Liste (`update_plan`) | `agentkit/planning.py` | shipped |
| [skills](skills.md) | Vorgehen als `SKILL.md`, on demand geladen | `agentkit/skills.py` | shipped |
| [coding-tools](coding-tools.md) | Sandbox-Dateitools + Shell mit Approval | `agentkit/coding.py` | shipped |
| [sub-agents](sub-agents.md) | Ein Agent als `delegate`-Tool eines Orchestrators | `agentkit/subagents.py` | shipped |
| [agent-roles](agent-roles.md) | `task`-Tool + Rollen (Claude-Code-Stil) | `agentkit/roles.py` | shipped |
| [mcp](mcp.md) | Tools über das Model Context Protocol | `agentkit/mcp.py` | shipped |
| [llm](llm.md) | Dünner Draht zu OpenAI / Azure OpenAI | `agentkit/llm.py` | shipped |
| [cli](cli.md) | Terminal-Frontend (REPL + one-shot) | `agentkit/cli.py` | shipped |

Vorlage für neue Specs: [`_template.md`](_template.md).
