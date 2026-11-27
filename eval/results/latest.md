# Evaluation results

- corpus: live index  (927 chunks)
- embedding model: intfloat/multilingual-e5-small
- answers: retrieval only
- run at: 2026-11-27T05:15:55+00:00
- items: 50 (42 answerable, 8 should refuse)

## Retrieval

| slice | n | recall@1 | recall@3 | recall@5 | recall@10 | MRR@10 |
|---|---|---|---|---|---|---|
| overall | 42 | 0.810 | 0.857 | 0.881 | 0.929 | 0.846 |
| en | 30 | 0.800 | 0.867 | 0.900 | 0.967 | 0.851 |
| es | 3 | 0.667 | 0.667 | 0.667 | 0.667 | 0.667 |
| hi | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| ko | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| zh | 3 | 0.667 | 0.667 | 0.667 | 0.667 | 0.667 |

## Cross-lingual gap (same question, English vs. translated; recall@5)

| language | pairs | English | translated | gap |
|---|---|---|---|---|
| es | 3 | 1.000 | 0.667 | 0.333 |
| hi | 3 | 1.000 | 1.000 | 0.000 |
| ko | 3 | 1.000 | 1.000 | 0.000 |
| zh | 3 | 1.000 | 0.667 | 0.333 |

## Refusal (confidence gate)

- configured threshold 0.800: refusal recall 0.875, false refusal rate 0.000, balanced accuracy 0.938
- mean confidence: answerable 0.873, should-refuse 0.779
- **calibrated threshold 0.810**: refusal recall 1.000, false refusal rate 0.000, balanced accuracy 1.000
