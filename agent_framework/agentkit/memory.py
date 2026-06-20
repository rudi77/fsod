"""Memory — Kurzzeit (die Konversation) und Langzeit (über Sessions hinweg).

- `ShortTermMemory`: die `messages[]`-Liste = das Arbeitsgedächtnis. Misst Tokens,
  kürzt (truncation) und fasst alte Historie zusammen (compaction) — genau die
  Context-Engineering-Hebel aus dem Notebook.
- `LongTermMemory`: ein dateibasierter Notizspeicher, der Sessions überdauert.
  Bewusst ohne Embeddings (keine schwere Abhängigkeit): Abruf per Stichwort-Overlap.
  Wird dem Agenten als Tools `remember` / `recall` angeboten.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

# Token-Zählung: tiktoken wenn vorhanden, sonst grobe Schätzung.
try:
    import tiktoken

    _enc = tiktoken.get_encoding("o200k_base")

    def count_tokens_text(text: str) -> int:
        return len(_enc.encode(text))
except Exception:  # pragma: no cover - Fallback ohne tiktoken
    def count_tokens_text(text: str) -> int:
        return len(text) // 4


def truncate(text: str, limit: int = 2000) -> str:
    """Kürzt riesige Tool-Outputs, statt sie ungefiltert anzuhängen."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[{len(text) - limit} Zeichen gekürzt]"


class ShortTermMemory:
    """Die Message-Historie + Context-Engineering darauf."""

    def __init__(self, system: Optional[str] = None):
        self.messages: List[dict] = []
        if system:
            self.messages.append({"role": "system", "content": system})

    def add(self, message: dict) -> None:
        self.messages.append(message)

    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def tokens(self) -> int:
        return sum(count_tokens_text(str(m.get("content") or "")) for m in self.messages)

    def compact(self, llm, keep_last: int = 4) -> bool:
        """Fasst alte Nachrichten zu einer kurzen Notiz zusammen; behält die
        letzten paar im Original. System-Nachricht bleibt erhalten.

        Achtet darauf, dass der behaltene Schwanz nicht mit verwaisten
        `tool`-Nachrichten beginnt (würde das tool_call/tool-Pairing brechen).
        Gibt True zurück, wenn komprimiert wurde.
        """
        system = [m for m in self.messages if m.get("role") == "system"][:1]
        body = [m for m in self.messages if m.get("role") != "system"]
        if len(body) <= keep_last:
            return False

        head, tail = body[:-keep_last], body[-keep_last:]
        while tail and tail[0].get("role") == "tool":
            head.append(tail.pop(0))
        if not head:
            return False

        digest = json.dumps(
            [{"role": m.get("role"), "content": m.get("content")} for m in head],
            ensure_ascii=False,
        )
        summary = llm.complete([{
            "role": "user",
            "content": "Fasse den folgenden Agenten-Verlauf in 3-5 Stichpunkten zusammen "
                       "(wichtige Fakten, Zwischenergebnisse, offene Punkte):\n" + digest,
        }]).content or ""

        self.messages = system + [{
            "role": "system",
            "content": "Bisheriger Verlauf (komprimiert):\n" + summary,
        }] + tail
        return True


class LongTermMemory:
    """Persistentes Langzeitgedächtnis (JSONL-Datei) mit Stichwort-Abruf."""

    def __init__(self, path: str = "agent_memory.jsonl"):
        self.path = Path(path)
        self.items: List[dict] = []
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    self.items.append(json.loads(line))

    def remember(self, text: str, tags: Optional[List[str]] = None) -> str:
        item = {"text": text, "tags": [t.lower() for t in (tags or [])]}
        self.items.append(item)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return "gespeichert."

    def recall(self, query: str, k: int = 3) -> str:
        q = set(query.lower().split())
        scored = []
        for it in self.items:
            words = set(it["text"].lower().split()) | set(it.get("tags", []))
            score = len(q & words)
            if score:
                scored.append((score, it["text"]))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits = [t for _, t in scored[:k]]
        return "\n".join(f"- {h}" for h in hits) if hits else f"(nichts zu '{query}' gefunden)"

    def register_tools(self, registry) -> None:
        """Bietet dem Agenten `remember`/`recall` als Tools an."""
        registry.add(
            "remember",
            "Speichert eine wichtige Information dauerhaft im Langzeitgedächtnis.",
            {"type": "object",
             "properties": {"text": {"type": "string", "description": "Die zu merkende Information."}},
             "required": ["text"]},
            self.remember,
        )
        registry.add(
            "recall",
            "Durchsucht das Langzeitgedächtnis nach relevanten, früher gespeicherten Informationen.",
            {"type": "object",
             "properties": {"query": {"type": "string", "description": "Wonach gesucht wird."}},
             "required": ["query"]},
            self.recall,
        )
