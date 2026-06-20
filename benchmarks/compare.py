"""Vergleichs-Runner: führt die Rust- und Python-Microbenchmarks mit IDENTISCHEN
Iterationszahlen aus und stellt ns/op sowie den Speedup (Python / Rust) gegenüber.

    python3 benchmarks/compare.py                 # voller Lauf
    python3 benchmarks/compare.py --scale 0.2     # schneller (weniger Iterationen)
    python3 benchmarks/compare.py --no-build      # vorhandenes Rust-Binary nutzen

Schreibt zusätzlich eine Markdown-Tabelle nach benchmarks/RESULTS.md.
"""

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUST_DIR = os.path.join(ROOT, "agent_framework_rs")
RUST_BIN = os.path.join(RUST_DIR, "target", "release", "bench")
PY_BENCH = os.path.join(ROOT, "benchmarks", "bench_python.py")
RESULTS_MD = os.path.join(ROOT, "benchmarks", "RESULTS.md")

# Reihenfolge der Szenarien für die Tabelle.
ORDER = [
    "agent_loop_single_tool",
    "parallel_tools_8",
    "tool_dispatch",
    "token_count_history",
    "frontmatter_parse",
    "json_roundtrip",
]

LABELS = {
    "agent_loop_single_tool": "Agent-Loop (1 Tool + Antwort)",
    "parallel_tools_8": "8 parallele Tool-Calls",
    "tool_dispatch": "Tool-Dispatch (Registry.call)",
    "token_count_history": "Token-Zählung (20 Msgs)",
    "frontmatter_parse": "Skill-Frontmatter parsen",
    "json_roundtrip": "JSON dump+parse",
}


def run_capture(cmd, env, cwd=None):
    """Führt cmd aus, gibt die JSON-Ergebniszeile (letzte stdout-Zeile) zurück.
    stderr (menschenlesbare Zeilen) wird durchgereicht."""
    proc = subprocess.run(cmd, env=env, cwd=cwd, capture_output=True, text=True)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        raise SystemExit(f"FEHLER bei {' '.join(cmd)} (exit={proc.returncode})\n{proc.stdout}")
    last = [l for l in proc.stdout.strip().splitlines() if l.strip()][-1]
    return json.loads(last)


def fmt_ns(ns):
    if ns >= 1_000_000:
        return f"{ns / 1_000_000:.2f} ms"
    if ns >= 1_000:
        return f"{ns / 1_000:.2f} µs"
    return f"{ns:.1f} ns"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="1.0")
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()

    env = dict(os.environ, AGENTKIT_BENCH_SCALE=str(args.scale))

    if not args.no_build:
        print(">> Baue Rust-Release-Benchmark ...", file=sys.stderr)
        subprocess.run(
            ["cargo", "build", "--release", "--no-default-features", "--bin", "bench"],
            cwd=RUST_DIR, check=True,
        )

    print("\n>> Rust:", file=sys.stderr)
    rust = run_capture([RUST_BIN], env)["results"]
    print("\n>> Python:", file=sys.stderr)
    py = run_capture([sys.executable, PY_BENCH], env)["results"]

    # Tabelle bauen.
    header = f"{'Szenario':<32} {'Python':>12} {'Rust':>12} {'Speedup':>10}"
    sep = "-" * len(header)
    lines = [header, sep]
    md = [
        f"# Benchmark: Rust vs. Python (agentkit)",
        "",
        f"- Datum: {date.today().isoformat()}",
        f"- Skala: {args.scale}",
        f"- Plattform: {platform.platform()}",
        f"- Python: {platform.python_version()}",
        "",
        "Reiner Framework-Overhead mit einem FakeLLM (kein Netz). Token-Zählung in",
        "beiden über denselben `len//4`-Fallback (kein tiktoken). Speedup = Python ÷ Rust.",
        "",
        "| Szenario | Python (ns/op) | Rust (ns/op) | Speedup |",
        "|---|---:|---:|---:|",
    ]

    speedups = []
    for key in ORDER:
        if key not in rust or key not in py:
            continue
        r = rust[key]["ns_per_op"]
        p = py[key]["ns_per_op"]
        s = p / r if r else float("nan")
        speedups.append(s)
        lines.append(f"{LABELS.get(key, key):<32} {fmt_ns(p):>12} {fmt_ns(r):>12} {s:>9.1f}x")
        md.append(f"| {LABELS.get(key, key)} | {p:,.1f} | {r:,.1f} | {s:.1f}× |")

    if speedups:
        geomean = 1.0
        for s in speedups:
            geomean *= s
        geomean **= 1.0 / len(speedups)
        lines.append(sep)
        lines.append(f"{'Geometrisches Mittel':<32} {'':>12} {'':>12} {geomean:>9.1f}x")
        md += ["", f"**Geometrisches Mittel des Speedups: {geomean:.1f}×**"]

    table = "\n".join(lines)
    print("\n" + table + "\n")

    with open(RESULTS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f">> Markdown geschrieben: {os.path.relpath(RESULTS_MD, ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
