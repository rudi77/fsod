# Benchmark: Rust vs. Python (agentkit)

- Datum: 2026-06-21
- Skala: 1.0
- Plattform: Linux-6.18.5-x86_64-with-glibc2.39
- Python: 3.11.15

Reiner Framework-Overhead mit einem FakeLLM (kein Netz). Token-Zählung in
beiden über denselben `len//4`-Fallback (kein tiktoken). Speedup = Python ÷ Rust.

| Szenario | Python (ns/op) | Rust (ns/op) | Speedup |
|---|---:|---:|---:|
| Agent-Loop (1 Tool + Antwort) | 23,298.5 | 6,098.6 | 3.8× |
| 8 parallele Tool-Calls | 1,248,376.3 | 428,628.3 | 2.9× |
| Tool-Dispatch (Registry.call) | 381.8 | 156.9 | 2.4× |
| Token-Zählung (20 Msgs) | 3,254.6 | 610.2 | 5.3× |
| Skill-Frontmatter parsen | 1,617.9 | 275.6 | 5.9× |
| JSON dump+parse | 5,822.3 | 1,447.9 | 4.0× |

**Geometrisches Mittel des Speedups: 3.9×**
