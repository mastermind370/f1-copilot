# F-1 Compliance Copilot

A tool that helps international students in the US understand F-1 rules. It answers questions using **only official sources**, cites a specific passage for every sentence, and **refuses rather than guesses**.

> **This is an information tool, not legal advice.** Always confirm with your school's Designated School Official (DSO).

## Status

| Stage | Scope | Status |
|---|---|---|
| 1 | Allowlisted ingestion + hybrid retrieval + grounded, cited Q&A (CLI) | ✅ |
| 2 | Deterministic rules engine + personal timeline | ⏳ |
| 3 | Eval harness (faithfulness, refusal, recall@k, multilingual) + CI gates | ⏳ |
| 4 | FastAPI + Next.js UI, on-device user data, source change detection | ⏳ |

## Architecture (Stage 1)

```
config.yaml (allowlist)
      │
      ▼
 Crawler ──robots.txt, https-only, prefix allowlist, politeness delay
      │   FetchedPage(url, fetched_at, content_hash = sha256(visible text))
      ▼
 Store (SQLite: documents, chunks  +  raw HTML on disk)
      │
      ▼
 Parser → Sections(heading path) → Chunker (paragraph-aligned, ≤220 words)
      │   chunk_id = sha256(url, heading, text)[:12]   ← content-addressed
      ▼
 Embeddings (multilingual-e5-small, cached by chunk_id) → embeddings.npy
      │
 query ─┬─ BM25 (own implementation) ──┐
        └─ dense cosine ───────────────┴─ Reciprocal Rank Fusion → top-k
                                             │
                          confidence < threshold? ──yes──► refuse + DSO pointer
                                             │ no
                                             ▼
                          LLM (Ollama / OpenAI-compatible / none)
                                             │
                          citation validator: drop uncited sentences,
                          strip hallucinated IDs, refuse if nothing survives
```

## Key design decisions

- **The LLM is an untrusted component.** It only rephrases retrieved text. Its output passes through `validate_citations`, which removes any sentence that doesn't cite a passage we actually supplied. Dates and eligibility will come from a deterministic rules engine (Stage 2), never from the LLM.
- **Hybrid retrieval.** Students type exact identifiers ("I-20", "I-765", "STEM OPT") that dense models blur together, and phrase things casually in ways keyword search misses. BM25 + embeddings handles both. RRF fuses the two rankings without score normalization.
- **Confidence gating uses the dense cosine score**, because it's bounded and comparable across queries. RRF scores aren't. The threshold is calibrated against the eval set in Stage 3.
- **Content-addressed chunk IDs** mean unchanged text keeps its ID across re-crawls. Embeddings are reused, and change detection (Stage 4) becomes a set diff.
- **Hash the visible text, not the HTML.** Raw HTML changes on every request (tokens, cache-busters), which would cause false "page changed" alerts.
- **Brute-force vector search instead of FAISS.** At a few thousand chunks, a numpy matrix-vector product takes under a millisecond and needs no native dependency. It sits behind the `Store` interface, so it's swappable.
- **Respect site rules.** robots.txt is honored and bot protection is never bypassed. If a site returns 403, save the page in your browser and use `copilot import-html`.

## Setup (macOS, Apple Silicon)

```bash
python3.11 -m venv .venv          # or python3.12 / 3.13
source .venv/bin/activate
pip install -e ".[dev]"
pytest                            # 46 tests, no network or model download needed
```

Optional local LLM (free):

```bash
brew install ollama
ollama serve &                    # or open the Ollama app
ollama pull qwen2.5:7b
```

No LLM? Set `llm.provider: none` in `config.yaml` to get extractive answers (quoted passages with citations).

## Usage

```bash
copilot -v ingest                          # crawl + chunk + embed (first run downloads ~470 MB model)
copilot stats
copilot ask "When can I apply for OPT?"
copilot ask "What is CPT?" --debug         # also shows sentences dropped for missing citations
copilot ask "What is CPT?" --json
copilot import-html ~/Downloads/page.html --url https://www.uscis.gov/... --source uscis
copilot reindex                            # after changing chunking settings (offline)
```

## Project layout

```
src/copilot/
  config.py      typed config from config.yaml
  models.py      dataclasses: FetchedPage, Chunk, ScoredChunk, Answer
  crawler.py     allowlisted crawler, robots.txt, Fetcher protocol (fake-able)
  parsing.py     HTML -> sections with heading hierarchy
  chunker.py     sections -> paragraph-aligned chunks with content-addressed IDs
  store.py       SQLite + embeddings.npy
  bm25.py        Okapi BM25 with an inverted index
  embeddings.py  sentence-transformers wrapper (MPS on Apple Silicon)
  retrieval.py   hybrid search + Reciprocal Rank Fusion
  llm.py         Ollama / OpenAI-compatible clients
  answer.py      prompt, confidence gate, citation validation, refusals
  indexing.py    crawl -> store -> chunk -> embed orchestration
  cli.py         `copilot` command
tests/           pytest; fake fetcher + fake embedder, so tests are offline and fast
```
