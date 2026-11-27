# F-1 Compliance Copilot

A tool that helps international students in the US understand F-1 rules. It answers questions using **only official sources** and cites a specific passage for every sentence. Personal deadlines are computed by a **deterministic rules engine**, never by an LLM, and each one comes with a step-by-step explanation and a source link.

> **This is an information tool, not legal advice.** Always confirm with your school's Designated School Official (DSO).

## Status

| Stage | Scope | Status |
|---|---|---|
| 1 | Allowlisted ingestion + hybrid retrieval + grounded, cited Q&A (CLI) | ✅ |
| 2 | Deterministic rules engine + personal timeline | ✅ |
| 3 | Eval harness (faithfulness, refusal, recall@k, multilingual) + CI gates | ⏳ |
| 4 | FastAPI + Next.js UI, on-device user data, source change detection | ⏳ |

## Architecture

```
                 ┌──────────────── Q&A (Stage 1) ────────────────┐
config.yaml ──►  Crawler ─► Store ─► Chunker ─► Embeddings          │
(allowlist)        robots.txt   SQLite   content-addressed IDs      │
                                                                     │
 question ──► BM25 + dense ─► RRF ─► confidence gate ─► LLM ─► citation validator
                                         │ low                       │
                                         └──► refuse + DSO pointer   │
                 └───────────────────────────────────────────────────┘

                 ┌──────────── Timeline (Stage 2) ───────────────┐
 rules/*.yaml ─► schema validator ─► Rule objects                  │
 (versioned,       (fails fast, in CI)        │                    │
  sourced)                                    ▼                    │
 my-facts.yaml ─► fact parser ─► engine: 3-valued conditions       │
 (stays local)     (typos = errors)   + date expressions w/ traces │
                                              │                    │
                                              ▼                    │
                      Timeline: items (date + "how" + source),     │
                      needs_info, not_applicable, stale_rules      │
                 └───────────────────────────────────────────────────┘
```

## Key design decisions

### Q&A (Stage 1)
- **The LLM is an untrusted component.** It only rephrases retrieved text. `validate_citations` removes any sentence that doesn't cite a passage we supplied, strips hallucinated IDs, and refuses if nothing is left.
- **Hybrid retrieval.** BM25 catches exact identifiers ("I-20", "I-765", "STEM OPT") that dense models blur together. Embeddings catch paraphrases. RRF fuses the two by rank, so no score normalization is needed.
- **Confidence gating uses the dense cosine score**, because it's bounded and comparable across queries. The threshold gets calibrated in Stage 3.
- **Content-addressed chunk IDs**, so embeddings are cached and change detection becomes a set diff.
- **Hash the visible text, not the HTML**, to avoid false "page changed" alerts.

### Rules engine (Stage 2)
- **Rules are data, not code.** Each rule is a YAML file with `id`, `version`, a source URL, a `verification` level (`primary` or `secondary`), `last_verified`, optional `effective` dates, and human-readable `notes`. Changing a deadline is a reviewable one-line diff, and the tests pin every shipped rule's output, so a change shows up in code review.
- **Three-valued logic.** Conditions evaluate to True, False or UNKNOWN (the same idea as SQL NULL). A missing fact never silently counts as "no". The rule reports `needs_info` with the exact facts it needs. Rules can opt into a default with `missing_as` when a safe default exists.
- **Explanations are produced by the computation itself.** Every date expression returns its value together with its arithmetic trace (`program_end_date 2027-05-15 + 60 days = 2027-07-14`), so the explanation can never disagree with the date.
- **Pure function.** `evaluate(rules, facts, as_of)` never reads the clock, so it's deterministic and easy to test at any date.
- **Calendar edge cases are isolated** in `dates.py`: month-end clamping (Aug 31 + 6 months = Feb 28) and weekend rolling for IRS dates (holidays are explicitly *not* modeled, and the rule says so).
- **Rules can go stale.** `copilot rules check --strict` fails if any rule hasn't been re-verified within `max_age_days`. That matters: in 2026 a DHS rule that would have cut the F-1 grace period from 60 to 30 days was published, then vacated by a federal court before taking effect. The grace-period rule carries a note explaining this.

## Setup (macOS, Apple Silicon)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

No LLM? `llm.provider: none` in `config.yaml` gives extractive answers (quoted passages with citations). For generated answers, install [Ollama](https://ollama.com) and set `provider: ollama`.

## Usage

### Ask questions
```bash
copilot -v ingest
copilot ask "When can I apply for OPT?"
copilot ask "What is CPT?" --debug
copilot import-html ~/Downloads/page.html --url https://www.uscis.gov/... --source uscis
```

### Compute your timeline
```bash
cp examples/facts.example.yaml my-facts.yaml
copilot timeline --facts my-facts.yaml
copilot timeline --facts my-facts.yaml --set dso_recommendation_date=2027-03-01
copilot timeline --set program_end_date=2027-05-15 --set on_opt=no --as-of 2027-03-01
copilot timeline --facts my-facts.yaml --json
copilot rules check
```
`my-facts.yaml` is git-ignored. Your personal data never leaves your machine.

### Rules shipped (v1, verified 2026-11-27)

| Rule | What it computes |
|---|---|
| `opt-post-completion-filing-window` | I-765 receipt window: 90 days before → min(60 days after program end, 30 days after DSO recommendation) |
| `grace-period-after-completion` | 60 days after program end (or after OPT ends) |
| `stem-opt-extension-filing-window` | 90 days before EAD expiry → min(EAD expiry, 60 days after STEM recommendation) |
| `opt-unemployment-limit` | 90 days (150 with STEM extension) |
| `i20-travel-signature-validity` | 12 months (6 on OPT), capped at program end / EAD expiry |
| `address-change-reporting` | 10 days after a move |
| `opt-employment-change-reporting` | 10 days after an employer change while on OPT |
| `initial-entry-window` | No earlier than 30 days before program start |
| `practical-training-eligibility` | One-academic-year requirement; 12+ months full-time CPT blocks OPT |
| `form-8843-filing` | April 15 with income / June 15 without (weekends rolled) |

Rules marked `secondary` were checked against university international office pages because the primary government page couldn't be fetched automatically. Re-verifying them against the primary source and bumping `last_verified` is part of maintenance.

## Project layout

```
rules/               versioned YAML rules (one file per rule)
examples/            example facts file
src/copilot/
  config.py          typed config from config.yaml
  models.py          Q&A dataclasses
  crawler.py         allowlisted crawler, robots.txt, Fetcher protocol
  parsing.py         HTML -> sections with heading hierarchy
  chunker.py         paragraph-aligned chunks, content-addressed IDs
  store.py           SQLite + embeddings.npy
  bm25.py            Okapi BM25 with an inverted index
  embeddings.py      sentence-transformers wrapper (MPS on Apple Silicon)
  retrieval.py       hybrid search + Reciprocal Rank Fusion
  llm.py             Ollama / OpenAI-compatible clients
  answer.py          prompt, confidence gate, citation validation, refusals
  indexing.py        crawl -> store -> chunk -> embed
  timeline/
    facts.py         StudentFacts + strict parsing
    dates.py         month arithmetic, business-day rolling
    schema.py        rule schema + validator (all errors reported at once)
    engine.py        3-valued conditions, traced date expressions, evaluate()
  cli.py             `copilot` command
tests/               175 tests; offline, no model downloads
```
