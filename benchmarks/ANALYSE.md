# Performance-Analyse: Rust vs. Python (agentkit)

**Frage:** Wie performen die beiden Implementierungen (`agent_framework` in Python,
`agent_framework_rs` in Rust) — und lohnt sich ein Umstieg auf Rust?

**Kurzantwort:** Rust ist beim **reinen Framework-Overhead** durchgängig
**~2,4–5,9× schneller** (geometrisches Mittel **≈ 3,9×**). Für einen **echten,
LLM-getriebenen Agenten ist dieser Vorteil jedoch praktisch unsichtbar**, weil
die Laufzeit zu >99,9 % von der LLM-/Netzwerk-Latenz bestimmt wird — und die ist
in beiden Sprachen identisch. Ein Umstieg lohnt sich daher **nicht** wegen der
Antwortlatenz, sondern **nur in spezifischen Szenarien** (sehr hoher Durchsatz /
viele parallele Agenten pro Host, CPU-lastige In-Process-Verarbeitung, knappe
Cold-Start-/Memory-Budgets am Edge). Details und Schwellen unten.

- Datum: 2026-06-21 · Plattform: Linux x86_64, 4× Xeon @ 2,80 GHz · Python 3.11.15 · Rust 1.94.1
- Methode & Reproduktion: siehe [`README.md`](README.md) · Rohzahlen: [`RESULTS.md`](RESULTS.md)

---

## 1. Was gemessen wurde — und was nicht

Gemessen wird der **Framework-Overhead** mit einem `FakeLLM` (kein Netz,
deterministische Streaming-Chunks). Das isoliert bewusst genau den Teil, den die
*Sprache/Implementierung* kostet: Agent-Loop, Tool-Dispatch, parallele Tools,
Token-Zählung, JSON- und Skill-Parsing.

**Nicht** gemessen (und das ist der entscheidende Kontext): der eigentliche
LLM-Call. In `agent_framework/agentkit/llm.py` geht jeder Schritt über einen
OpenAI-/Azure-kompatiblen HTTP-Client zum Modell. Diese Latenz — Netzwerk +
Inferenz — ist sprach­unabhängig und um **Größenordnungen** höher als alles, was
das Framework selbst verbraucht.

---

## 2. Messergebnisse (frisch reproduziert, 2026-06-21)

| Szenario | Python | Rust | Speedup |
|---|---:|---:|---:|
| Agent-Loop (1 Tool + Antwort) | 23,30 µs | 6,10 µs | **3,8×** |
| 8 parallele Tool-Calls | 1,25 ms | 428,6 µs | **2,9×** |
| Tool-Dispatch (`Registry.call`) | 381,8 ns | 156,9 ns | **2,4×** |
| Token-Zählung (20 Msgs) | 3,25 µs | 610,2 ns | **5,3×** |
| Skill-Frontmatter parsen | 1,62 µs | 275,6 ns | **5,9×** |
| JSON dump+parse | 5,82 µs | 1,45 µs | **4,0×** |
| **Geometrisches Mittel** | | | **≈ 3,9×** |

**Muster:** Rechenlastige, allokationsarme Pfade (Token-Zählung, Frontmatter-,
JSON-Parsing) profitieren am stärksten (4–6×). Der volle Agent-Loop und die
parallelen Tools weniger (≈ 3×), weil dort auf beiden Seiten JSON-Value-Allokation
und Thread-Aufbau anfallen.

> Hinweis: Absolutwerte schwanken auf der geteilten Cloud-CPU (v. a. der
> Parallel-Test). Die **Verhältnisse** sind stabil; der Vorlauf vom 2026-06-20 lag
> beim Geomean bei 3,6×, dieser bei 3,9×.

---

## 3. Einordnung: Overhead vs. LLM-Latenz (der entscheidende Punkt)

Ein Agent-Loop-Durchlauf kostet das **Framework** rund **23 µs (Python)** bzw.
**6 µs (Rust)** — Differenz **≈ 17 µs**. Dem steht **ein realer LLM-Schritt**
gegenüber. Selbst optimistisch gerechnet:

| Realer LLM-Schritt (Wall-Clock) | Framework-Anteil (Python) | Ersparnis durch Rust |
|---|---:|---:|
| 100 ms (sehr schnell, kurze Antwort) | 0,023 % | ~17 µs → **0,017 %** |
| 1 s (typisch, mittlere Antwort) | 0,0023 % | **0,0017 %** |
| 5 s (lange/Tool-schwere Antwort) | 0,0005 % | **0,0003 %** |

**Folgerung (Amdahl):** Bei einem nutzerseitigen Agenten ist der 3,9×-Vorteil des
Frameworks **im Rauschen der LLM-Latenz nicht wahrnehmbar**. Eine Antwort, die mit
Python 1,000023 s braucht, braucht mit Rust 1,000006 s — kein Mensch und kein SLA
sieht den Unterschied. **Für Antwortzeit lohnt der Umstieg nicht.**

---

## 4. Wo Rust real etwas bringt — und wo nicht

**Rust hilft messbar, wenn der Engpass NICHT das LLM ist:**

- **Durchsatz / Dichte pro Host:** Bei sehr vielen gleichzeitigen Agenten zählt
  CPU-Zeit pro Operation und echte Parallelität. Python ist hier durch den **GIL**
  bei CPU-Anteilen limitiert (die parallelen Tools laufen via `ThreadPoolExecutor`,
  agent.py:177) — Rust nutzt echte Threads ohne GIL. Effekt: mehr Agenten pro
  Kern, niedrigere Cloud-Rechnung. *Aber:* LLM-Calls sind **I/O-gebunden**, und
  dafür skaliert auch Python (async / Threads) gut — der GIL beißt nur bei
  CPU-Arbeit.
- **CPU-lastige In-Process-Verarbeitung:** Token-Zählung über sehr große
  Historien, massenhaftes Parsing, lokale Embeddings/Reranking, lokale Inferenz.
  *Caveat:* Sobald in Python `tiktoken` oder ein lokales Modell im Spiel ist,
  läuft das ohnehin in einer C-/Rust-Extension — der reine-Python-Nachteil
  schrumpft dann.
- **Cold-Start & Speicher (Serverless/Edge):** Ein Rust-Binary startet in
  Millisekunden und braucht wenige MB; ein Python-Interpreter samt Abhängigkeiten
  ist träger und schwerer. Relevant bei Lambda-artigen, häufig kalt startenden
  Deployments oder ressourcenarmen Edge-Geräten.

**Rust hilft kaum bis gar nicht, wenn:**

- Es ein **klassischer Chat-/Assistenz-Agent** ist (1 User, sequenzielle Schritte)
  — hier dominiert die LLM-Latenz vollständig.
- Der Durchsatz ohnehin durch **Rate-Limits / Token-Kosten des LLM-Anbieters**
  gedeckelt ist (was meist der Fall ist).

---

## 5. Faktoren jenseits der reinen Performance

„Lohnt sich ein Umstieg" ist eine Geschäfts-, keine reine Benchmark-Frage:

| Kriterium | Python | Rust |
|---|---|---|
| Ökosystem KI/LLM (SDKs, Frameworks, Notebooks) | sehr reif, Standard | dünn, vieles selbst zu bauen |
| Entwicklungs­geschwindigkeit / Prototyping | hoch | langsamer (Typen, Borrow-Checker) |
| Verfügbarkeit von Entwickler:innen | groß | kleiner / teurer |
| Laufzeit-Robustheit (Memory-Safety, kein GIL) | gut | sehr gut |
| Ressourcen­verbrauch / Betriebs­kosten bei Skalierung | höher | niedriger |
| Migrations­risiko & -aufwand (Port + Test pflegen) | — | erheblich (zwei Codebasen!) |

Der Port hält beide Implementierungen funktional gleich — das ist gut für den
Vergleich, bedeutet im Dauerbetrieb aber **doppelte Pflege**, solange beide leben.

---

## 6. Handlungsempfehlung

1. **Standardfall (LLM-getriebener Agent, Latenz im Vordergrund): bei Python
   bleiben.** Der Rust-Vorteil verschwindet hinter der LLM-Latenz; das reifere
   Ökosystem und die höhere Entwicklungs­geschwindigkeit überwiegen klar.

2. **Rust gezielt erwägen, wenn mindestens einer dieser Trigger zutrifft:**
   - **Sehr hohe Dichte/Durchsatz** (tausende gleichzeitige Agenten pro Host) und
     die **Cloud-Kosten** sind ein spürbarer Posten → Rusts geringerer
     CPU-/Speicherbedarf senkt die Rechnung.
   - **CPU-gebundene In-Process-Arbeit** ohne fertige Python-C-Extension.
   - **Cold-Start-/Memory-Budgets** am Edge oder in Serverless sind kritisch.

3. **Vor einer Migration zuerst messen, was zählt:** Diese Benchmarks messen
   Framework-Overhead, nicht euren realen Engpass. **Empfohlener nächster Schritt
   für MSN:** ein End-to-End-Lasttest mit echten (oder realitätsnah simulierten)
   LLM-Antwortzeiten und Ziel-Concurrency — und Vergleich von **$/1000 Requests**
   sowie **Agenten/Kern** statt ns/op. Erst diese Zahlen rechtfertigen (oder
   widerlegen) den Migrationsaufwand.

4. **Pragmatischer Mittelweg statt Komplett-Port:** Falls sich ein konkreter
   CPU-Hotspot zeigt, diesen als Rust-Modul (z. B. via PyO3) in die Python-Basis
   einbinden — der Großteil bleibt in Python, der heiße Pfad wird nativ. Das holt
   den Performance-Gewinn dort ab, wo er zählt, ohne zwei volle Codebasen zu pflegen.

**Fazit:** Rust ist hier sauber 3–6× schneller im Framework — ein reales, aber für
die *Antwortzeit* irrelevantes Ergebnis, weil das LLM den Takt vorgibt. Ein
vollständiger Umstieg lohnt sich nur unter klaren Durchsatz-, Kosten- oder
Edge-Bedingungen; für den typischen Agenten bleibt Python die wirtschaftlichere Wahl.
</content>
</invoke>
