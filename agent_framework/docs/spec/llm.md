---
feature: llm
status: shipped
since: 2026-06-20
last_verified: 2026-06-22
owner:
adr:
---

# LLM — der einzige Draht zum Modell

Ein LLM ist Text rein, Text raus. Diese dünne Hülle kapselt genau das: ein Call
für eine fertige Antwort (`complete`, für Compaction und Nicht-Streaming) und
derselbe Call als Chunk-Iterator (`stream`, für den Agent-Loop). Bewusst **keine**
eigene Abstraktion über die OpenAI-Chunks — der Loop arbeitet direkt mit dem
Provider-Format. Das hält das Framework klein und kompatibel zu OpenAI und Azure
OpenAI. Zwei Helfer bauen den LLM aus Umgebungsvariablen.

## Fähigkeiten (was der Nutzer tun kann)

- Jeden OpenAI-kompatiblen Client mit Modellnamen als LLM kapseln
- Eine vollständige Antwort in einem Call holen (`complete`)
- Dieselbe Anfrage als Token-Stream beziehen (`stream`)
- Einen Azure-OpenAI- oder Standard-OpenAI-LLM aus `.env`-Variablen bauen

## Invarianten (was immer gelten muss)

- Werden Tools übergeben, werden sie samt `tool_choice="auto"` an das Modell gereicht; ohne Tools enthält die Anfrage keine Tool-Felder.
- `complete` liefert genau die `message` der ersten Choice (mit `.content` und `.tool_calls`); `stream` liefert den rohen Chunk-Iterator des Providers.
- Es findet keine Umformung der Provider-Chunks statt — der Agent-Loop sieht das native OpenAI-Format.
- Jeder Client mit `client.chat.completions.create(...)` ist nutzbar (OpenAI, AzureOpenAI oder ein kompatibler Stub).
- Die `from_env`-Helfer lesen Pflichtvariablen hart und scheitern laut, wenn sie fehlen.

## API-/Schnittstellen-Vertrag (worauf sich Aufrufer verlassen)

- `LLM(client, model).complete(messages, tools=None) -> message`
- `LLM(client, model).stream(messages, tools=None) -> Iterable[chunk]`
- `azure_from_env() -> LLM` — aus `AZURE_OPENAI_*`
- `openai_from_env() -> LLM` — aus `OPENAI_API_KEY` (+ optional `OPENAI_MODEL`)

## Konfigurationsfläche (Schalter/Parameter)

- `AZURE_OPENAI_API_KEY` — Pflicht für `azure_from_env`
- `AZURE_OPENAI_ENDPOINT` — Pflicht für `azure_from_env`
- `AZURE_OPENAI_DEPLOYMENT` — Pflicht, das Azure-Deployment (= Modell)
- `AZURE_OPENAI_API_VERSION` — optional (Default `2024-10-21`)
- `OPENAI_API_KEY` — Pflicht für `openai_from_env`
- `OPENAI_MODEL` — optional (Default `gpt-4o-mini`)

## Tests (müssen existieren und bestehen)

- (keine direkten) — in den Loop-Tests wird ein `DummyLLM`-Stub mit derselben Schnittstelle genutzt

## Bekannte Lücken

- Keine eigenen Tests für `complete`/`stream` oder die `from_env`-Helfer; die Schnittstelle ist nur indirekt über die Agent-Tests via Stub abgesichert.
- Keine eingebaute Retry-/Rate-Limit-Behandlung auf dieser Ebene — Retries beim Stream-Aufbau liegen im [agentic-loop](agentic-loop.md).

## Querverweise

- verwandte Spec: [agentic-loop](agentic-loop.md), [memory](memory.md)
- Code: agentkit/llm.py
