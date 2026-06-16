"""Baut aus notebook_source.txt ein valides .ipynb und prueft jede Code-Zelle auf Syntaxfehler.

Zell-Marker (jeweils eigene Zeile):  <<<MD>>>  <<<CODE>>>  <<<END>>>
"""
import json

SRC = "notebook_source.txt"
OUT = "AI_Agents_under_the_Hood.ipynb"

text = open(SRC, encoding="utf-8").read()
cells, cur_type, buf = [], None, []


def flush():
    global cur_type, buf
    if cur_type is None:
        return
    source = "\n".join(buf).strip("\n")
    src_lines = source.splitlines(keepends=True)
    if cur_type == "MD":
        cells.append({"cell_type": "markdown", "metadata": {}, "source": src_lines})
    else:
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None,
                      "outputs": [], "source": src_lines})
    buf = []


for line in text.split("\n"):
    s = line.strip()
    if s == "<<<MD>>>":
        flush(); cur_type = "MD"
    elif s == "<<<CODE>>>":
        flush(); cur_type = "CODE"
    elif s == "<<<END>>>":
        flush(); cur_type = None
    else:
        buf.append(line)
flush()

# Syntaxpruefung aller Code-Zellen
errors = 0
for i, c in enumerate(cells):
    if c["cell_type"] != "code":
        continue
    code = "".join(c["source"])
    try:
        compile(code, f"<cell {i}>", "exec")
    except SyntaxError as e:
        errors += 1
        print(f"SYNTAXFEHLER in Zelle {i}: {e}")

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
json.dump(nb, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

md = sum(1 for c in cells if c["cell_type"] == "markdown")
code = sum(1 for c in cells if c["cell_type"] == "code")
print(f"OK -> {OUT}: {len(cells)} Zellen ({md} Markdown, {code} Code), Syntaxfehler: {errors}")
