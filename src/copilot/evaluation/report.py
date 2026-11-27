"""Renders an eval summary as Markdown, for the README and for CI logs."""

from __future__ import annotations

from typing import Any


def _f(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def to_markdown(summary: dict[str, Any], meta: dict[str, Any]) -> str:
    lines = [
        "# Evaluation results",
        "",
        f"- corpus: {meta.get('corpus')}  ({meta.get('n_chunks')} chunks)",
        f"- embedding model: {meta.get('embedding_model')}",
        f"- answers: {meta.get('answers')}",
        f"- run at: {meta.get('run_at')}",
        f"- items: {summary['n_items']} ({summary['n_answerable']} answerable, "
        f"{summary['n_should_refuse']} should refuse)",
        "",
        "## Retrieval",
        "",
        "| slice | n | recall@1 | recall@3 | recall@5 | recall@10 | MRR@10 |",
        "|---|---|---|---|---|---|---|",
    ]
    rows = [("overall", summary["retrieval"]["overall"])]
    rows += list(summary["retrieval"]["by_language"].items())
    for name, m in rows:
        lines.append(f"| {name} | {m['n']} | {_f(m['recall@1'])} | {_f(m['recall@3'])} | "
                     f"{_f(m['recall@5'])} | {_f(m['recall@10'])} | {_f(m['mrr@10'])} |")

    if summary["cross_lingual"]:
        lines += ["", "## Cross-lingual gap (same question, English vs. translated; recall@5)", "",
                  "| language | pairs | English | translated | gap |", "|---|---|---|---|---|"]
        for lang, g in summary["cross_lingual"].items():
            lines.append(f"| {lang} | {g['pairs']} | {_f(g['en_recall@5'])} | "
                         f"{_f(g[f'{lang}_recall@5'])} | {_f(g['gap'])} |")

    ref = summary["refusal"]
    c = ref["configured"]
    best = ref["calibration"]["best"]
    lines += [
        "", "## Refusal (confidence gate)", "",
        f"- configured threshold {_f(c['threshold'])}: refusal recall {_f(c['refusal_recall'])}, "
        f"false refusal rate {_f(c['false_refusal_rate'])}, balanced accuracy {_f(c['balanced_accuracy'])}",
        f"- mean confidence: answerable {_f(ref['confidence']['answerable_mean'])}, "
        f"should-refuse {_f(ref['confidence']['refuse_mean'])}",
    ]
    if best:
        lines.append(f"- **calibrated threshold {_f(best['threshold'])}**: refusal recall "
                     f"{_f(best['refusal_recall'])}, false refusal rate {_f(best['false_refusal_rate'])}, "
                     f"balanced accuracy {_f(best['balanced_accuracy'])}")

    if "answers" in summary:
        a = summary["answers"]
        lines += [
            "", "## End-to-end answers", "",
            f"- answered (answerable questions): {_f(a['answer_rate_answerable'])}",
            f"- refused (should-refuse questions): {_f(a['refusal_recall'])}",
            f"- answers citing a gold passage: {_f(a['citation_gold_hit_rate'])}",
            f"- faithfulness, English, NLI-judged: {_f(a['faithfulness_en'])} (n={a['faithfulness_n']})",
            f"- refusal reasons: {a['refusal_reasons']}",
        ]
    if summary["unresolved"]:
        lines += ["", f"**Unresolved gold** (excluded from retrieval metrics): {', '.join(summary['unresolved'])}"]
    return "\n".join(lines) + "\n"
