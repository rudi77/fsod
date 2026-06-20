"""Der einzige Draht zum Modell.

Ein LLM ist *Text rein -> Text raus*. Diese dünne Hülle kapselt genau das:
- `complete()` : ein Call, eine fertige Antwort (für Compaction & Nicht-Streaming).
- `stream()`   : derselbe Call mit `stream=True` -> Iterator über Chunks.

Bewusst KEINE eigene Abstraktion über die OpenAI-Chunks: der Agent-Loop arbeitet
direkt mit dem OpenAI-Format (`choices[0].delta...`). Das hält das Framework klein
und kompatibel zu Azure OpenAI / OpenAI.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, List, Optional


class LLM:
    """Wickelt einen OpenAI-kompatiblen Client + Modellnamen.

    `client` muss `client.chat.completions.create(...)` anbieten
    (AzureOpenAI, OpenAI oder ein kompatibler Stub).
    """

    def __init__(self, client: Any, model: str):
        self.client = client
        self.model = model

    def _kwargs(self, messages, tools, stream):
        kw = dict(model=self.model, messages=messages)
        if tools:
            kw["tools"] = tools
            kw["tool_choice"] = "auto"
        if stream:
            kw["stream"] = True
        return kw

    def complete(self, messages: List[dict], tools: Optional[list] = None):
        """Ein Call -> EINE fertige `message` (mit `.content` und `.tool_calls`)."""
        resp = self.client.chat.completions.create(**self._kwargs(messages, tools, False))
        return resp.choices[0].message

    def stream(self, messages: List[dict], tools: Optional[list] = None) -> Iterable:
        """Derselbe Call mit `stream=True` -> Iterator über Chunks (Deltas)."""
        return self.client.chat.completions.create(**self._kwargs(messages, tools, True))


def azure_from_env() -> "LLM":
    """Baut einen Azure-OpenAI-LLM aus den .env-Variablen (wie in den Notebooks)."""
    from openai import AzureOpenAI

    client = AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    )
    return LLM(client, os.environ["AZURE_OPENAI_DEPLOYMENT"])


def openai_from_env() -> "LLM":
    """Baut einen Standard-OpenAI-LLM (OPENAI_API_KEY, optional OPENAI_MODEL)."""
    from openai import OpenAI

    client = OpenAI()
    return LLM(client, os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
