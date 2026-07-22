# Benchmarks: Rust vs. Python (agentkit)

Vergleicht den **Framework-Overhead** des Rust-Ports mit dem Python-Original
([`../agent_framework`](../agent_framework)).

> Der Rust-Port ist nach **[rudi77/agentkit_rs](https://github.com/rudi77/agentkit_rs)**
> umgezogen. Die Skripte hier erwarten ihn weiterhin unter `../agent_framework_rs` —
> dafür das agentkit_rs-Repo klonen und `agent_framework_rs` hierher verlinken oder
> die Pfade in `compare.py` anpassen.

## Warum FakeLLM?

Bei einem echten Agenten dominiert die **LLM-Latenz** (Netzwerk, Inferenz) — und die
ist für Rust und Python identisch. Um *das Framework selbst* zu messen, spielt ein
`FakeLLM` vorgegebene Streaming-Chunks ab (kein Netz, deterministisch). So wird
sichtbar, was die Sprache/Implementierung kostet: Agent-Loop, Tool-Dispatch,
parallele Tools, Token-Zählung, JSON-Parsing, Skill-Parsing.

Beide Seiten fahren **dieselben Szenarien mit denselben Iterationszahlen**. Die
Token-Zählung nutzt beidseitig den `len // 4`-Fallback (kein tiktoken) — gemessen
wird also Schleifen-/Sprach-Overhead, nicht die Geschwindigkeit eines Tokenizers.

## Ausführen

```bash
# Baut das Rust-Release-Binary und führt beide Suites aus, druckt eine Tabelle
# und schreibt RESULTS.md:
python3 benchmarks/compare.py

python3 benchmarks/compare.py --scale 0.2     # schneller (weniger Iterationen)
python3 benchmarks/compare.py --no-build      # vorhandenes Rust-Binary nutzen
```

Einzeln:

```bash
( cd agent_framework_rs && cargo run --release --no-default-features --bin bench )
python3 benchmarks/bench_python.py
```

## Szenarien

| Szenario | Was es misst |
|---|---|
| `agent_loop_single_tool` | Voller Loop: Tool-Call → Ergebnis → finale Antwort (frischer Agent) |
| `parallel_tools_8` | 8 Tool-Calls aus EINER Antwort, nebenläufig (Thread-Overhead) |
| `tool_dispatch` | Reiner `ToolRegistry.call` (Lookup + Argument-Handling) |
| `token_count_history` | Token-Schätzung über 20 Nachrichten |
| `frontmatter_parse` | YAML-Frontmatter einer `SKILL.md` parsen |
| `json_roundtrip` | Tool-Argument-Objekt serialisieren + parsen |

## Ergebnisse & Analyse

Aktuelle Rohzahlen liegen in [`RESULTS.md`](RESULTS.md) (wird von `compare.py`
geschrieben). Die **eingeordnete Auswertung mit Handlungsempfehlung** („lohnt sich
ein Umstieg auf Rust?") steht in [`ANALYSE.md`](ANALYSE.md). Richtwert auf Linux/Python 3.11: Rust ist je nach Szenario **~2.6×–5.3×**
schneller, geometrisches Mittel **≈ 3.6×**. Rechenlastige, allokationsarme Pfade
(Token-/Frontmatter-Parsing) profitieren am stärksten; der volle Agent-Loop weniger,
weil dort JSON-Value-Allokation und Thread-Aufbau auf beiden Seiten anfallen.
