"""Demo-LLM, Demo-Tools und LLM-Auswahl — der netzfreie Fallback für die CLI.

Spiegelt das Rust-Pendant (`agent_framework_rs/src/demo.rs`): Ohne API-Key läuft
ein winziges, deterministisches Modell, das echte Tool-Calls auslöst (Addition,
Wetter) — so ist die installierte Executable auch ohne Netz sofort interaktiv.
"""

from __future__ import annotations

import os
import re
from types import SimpleNamespace
from typing import Optional, Tuple

from .tools import ToolRegistry


# --------------------------------------------------------------- LLM-Auswahl
def build_llm(force_demo: bool = False) -> Tuple[object, str]:
    """Wählt den LLM: Azure -> OpenAI -> Demo (Fallback). Gibt zusätzlich ein
    Label für die Statusausgabe zurück."""
    if not force_demo:
        if os.environ.get("AZURE_OPENAI_API_KEY"):
            try:
                from .llm import azure_from_env

                dep = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "?")
                return azure_from_env(), f"azure:{dep}"
            except Exception:
                pass
        # OPENAI_BASE_URL allein reicht: lokale OpenAI-kompatible Server
        # (Ollama, LM Studio, vLLM, …) brauchen keinen API-Key.
        if os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_BASE_URL"):
            try:
                from .llm import openai_from_env

                model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
                base = os.environ.get("OPENAI_BASE_URL")
                label = f"openai:{model} @ {base}" if base else f"openai:{model}"
                return openai_from_env(), label
            except Exception:
                pass
    return DemoLLM(), "demo (kein Netz)"


# ----------------------------------------------------------------- Demo-Tools
def demo_tools() -> ToolRegistry:
    """Ein kleiner Demo-Werkzeugkasten — dieselben Tools, die das `DemoLLM`
    ansteuert, aber auch ein echtes Modell kann sie nutzen."""
    reg = ToolRegistry()

    @reg.tool()
    def add(a: int, b: int) -> int:
        """Addiert zwei ganze Zahlen a und b."""
        return a + b

    @reg.tool()
    def wetter(stadt: str) -> str:
        """Liefert (frei erfundenes) Wetter für eine Stadt."""
        return f"In {stadt}: 18°C, leicht bewölkt, schwacher Wind."

    @reg.tool()
    def reverse(text: str) -> str:
        """Dreht eine Zeichenkette um."""
        return text[::-1]

    return reg


# ------------------------------------------------------------------- Demo-LLM
def _chunk(content=None, tool=None, index=0):
    """Baut einen OpenAI-kompatiblen Streaming-Chunk (wie der echte Client)."""
    delta = SimpleNamespace(content=content, tool_calls=None)
    if tool:
        tc = SimpleNamespace(
            index=index,
            id=tool.get("id"),
            function=SimpleNamespace(name=tool.get("name"), arguments=tool.get("arguments")),
        )
        delta.tool_calls = [tc]
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


class DemoLLM:
    """Ein winziger, deterministischer LLM ohne Netz — für den Demo-Modus.

    Er schaut auf die letzte Nachricht: liegt schon ein Tool-Ergebnis vor, fasst er
    es zusammen; sonst sucht er in der letzten User-Nachricht nach einem passenden
    Tool-Aufruf (Addition `a + b`, `wetter in <Stadt>`) und ruft es auf — andernfalls
    antwortet er direkt. Dadurch ist die Anwendung auch ohne API-Key interaktiv.
    """

    def complete(self, messages, tools=None):
        return SimpleNamespace(content="(komprimierte Zusammenfassung)", tool_calls=None)

    def stream(self, messages, tools=None):
        last = messages[-1] if messages else {}

        # Schon ein Tool-Ergebnis da -> finale Antwort.
        if last.get("role") == "tool":
            text = f"Ergebnis: {last.get('content', '')}"
            return iter(_answer_chunks(text))

        # Letzte User-Nachricht heranziehen.
        user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user = m.get("content", "")
                break
        lower = user.lower()

        # 1) Addition "a + b"?
        ab = _parse_addition(user)
        if ab is not None:
            a, b = ab
            args = f'{{"a": {a}, "b": {b}}}'
            return iter([_chunk(tool={"id": "demo-add", "name": "add", "arguments": args})])

        # 2) Wetter?
        if "wetter" in lower or "weather" in lower:
            stadt = _parse_city(user) or "Wien"
            args = f'{{"stadt": "{stadt}"}}'
            return iter([_chunk(tool={"id": "demo-wetter", "name": "wetter", "arguments": args})])

        # 3) Sonst: direkte Demo-Antwort.
        text = (
            f"Demo-Modus (kein Netz): Ich habe »{user.strip()}« erhalten. Setze einen "
            "API-Key (OPENAI_API_KEY oder AZURE_OPENAI_*) oder OPENAI_BASE_URL für einen "
            "lokalen Server (Ollama & Co.), um ein echtes Modell zu nutzen. "
            "Probier z. B. »17 + 25« oder »Wetter in Berlin«."
        )
        return iter(_answer_chunks(text))


def _answer_chunks(text: str):
    """Streamt Wort für Wort — zeigt den Streaming-Pfad. Das trennende Leerzeichen
    bleibt am Wort (wie Rusts `split_inclusive(' ')`), sodass die Stücke wieder den
    Originaltext ergeben."""
    words = text.split(" ")
    return [
        _chunk(content=w + (" " if i < len(words) - 1 else ""))
        for i, w in enumerate(words)
    ]


def _parse_addition(text: str) -> Optional[Tuple[int, int]]:
    """Findet das erste Muster `<int> + <int>`: den Ziffernlauf direkt links bzw.
    rechts vom ersten `+`."""
    if "+" not in text:
        return None
    left, right = text.split("+", 1)
    m_left = re.search(r"(\d+)\s*$", left)
    m_right = re.search(r"^\s*(\d+)", right)
    if not (m_left and m_right):
        return None
    return int(m_left.group(1)), int(m_right.group(1))


def _parse_city(text: str) -> Optional[str]:
    """Sehr einfache Stadt-Extraktion: das Wort nach einem alleinstehenden 'in'."""
    words = text.split()
    for i, w in enumerate(words):
        if w.lower() == "in" and i + 1 < len(words):
            city = "".join(c for c in words[i + 1] if c.isalpha() or c == "-")
            if city:
                return city
    return None
