# Evaluation results

- corpus: eval/snapshot/chunks.jsonl  (532 chunks)
- embedding model: intfloat/multilingual-e5-small
- answers: retrieval only
- run at: 2026-11-27T05:19:53+00:00
- items: 50 (42 answerable, 8 should refuse)

## Retrieval

| slice | n | recall@1 | recall@3 | recall@5 | recall@10 | MRR@10 |
|---|---|---|---|---|---|---|
| overall | 41 | 0.756 | 0.878 | 0.902 | 0.927 | 0.827 |
| en | 29 | 0.828 | 0.897 | 0.931 | 0.966 | 0.876 |
| es | 3 | 0.333 | 0.667 | 0.667 | 0.667 | 0.500 |
| hi | 3 | 0.667 | 1.000 | 1.000 | 1.000 | 0.833 |
| ko | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| zh | 3 | 0.333 | 0.667 | 0.667 | 0.667 | 0.500 |

## Cross-lingual gap (same question, English vs. translated; recall@5)

| language | pairs | English | translated | gap |
|---|---|---|---|---|
| es | 3 | 1.000 | 0.667 | 0.333 |
| hi | 3 | 1.000 | 1.000 | 0.000 |
| ko | 3 | 1.000 | 1.000 | 0.000 |
| zh | 3 | 1.000 | 0.667 | 0.333 |

## Refusal (confidence gate)

- configured threshold 0.810: refusal recall 1.000, false refusal rate 0.000, balanced accuracy 1.000
- mean confidence: answerable 0.871, should-refuse 0.762
- **calibrated threshold 0.810**: refusal recall 1.000, false refusal rate 0.000, balanced accuracy 1.000

**Unresolved gold** (excluded from retrieval metrics): en-opt-003
