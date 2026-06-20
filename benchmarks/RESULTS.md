# Benchmark: Rust vs. Python (agentkit)

- Datum: 2026-06-20
- Skala: 1.0
- Plattform: Linux-6.18.5-x86_64-with-glibc2.39
- Python: 3.11.15

Reiner Framework-Overhead mit einem FakeLLM (kein Netz). Token-Zählung in
beiden über denselben `len//4`-Fallback (kein tiktoken). Speedup = Python ÷ Rust.

| Szenario | Python (ns/op) | Rust (ns/op) | Speedup |
|---|---:|---:|---:|
| Agent-Loop (1 Tool + Antwort) | 17,629.7 | 6,369.6 | 2.8× |
| 8 parallele Tool-Calls | 876,426.1 | 261,184.4 | 3.4× |
| Tool-Dispatch (Registry.call) | 271.0 | 105.4 | 2.6× |
| Token-Zählung (20 Msgs) | 2,028.6 | 430.0 | 4.7× |
| Skill-Frontmatter parsen | 1,152.5 | 219.5 | 5.3× |
| JSON dump+parse | 4,721.5 | 1,182.3 | 4.0× |

**Geometrisches Mittel des Speedups: 3.6×**
