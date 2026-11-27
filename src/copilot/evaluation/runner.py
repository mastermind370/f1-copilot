"""Runs the eval dataset through retrieval (and optionally full answering) and summarizes it."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from copilot.answer import QAPipeline
from copilot.evaluation.dataset import EvalItem, Resolution
from copilot.evaluation.faithfulness import Judge, faithfulness
from copilot.evaluation.metrics import (
    KS,
    calibrate,
    hit_at_k,
    mean,
    refusal_stats,
    retrieval_metrics,
)
from copilot.retrieval import HybridRetriever


@dataclass
class ItemResult:
    id: str
    language: str
    group: str
    should_refuse: bool
    translation_of: str | None
    question: str
    gold_ids: list[str]
    ranked_ids: list[str]
    confidence: float
    unresolved: bool
    first_gold_rank: int | None = None
    answer: str | None = None
    refused: bool | None = None
    refusal_reason: str | None = None
    cited_ids: list[str] = field(default_factory=list)
    cites_gold: bool | None = None
    faithfulness: float | None = None


def run_items(
    items: list[EvalItem],
    resolution: Resolution,
    retriever: HybridRetriever,
    pipeline: QAPipeline | None = None,
    judge: Judge | None = None,
) -> list[ItemResult]:
    results: list[ItemResult] = []
    depth = max(KS)
    for item in items:
        gold = resolution.gold_ids.get(item.id, set())
        search = retriever.search(item.question, top_k=depth)
        ranked = [h.chunk.chunk_id for h in search.hits]
        first = next((r for r, cid in enumerate(ranked, start=1) if cid in gold), None)
        res = ItemResult(
            id=item.id, language=item.language, group=item.group, should_refuse=item.should_refuse,
            translation_of=item.translation_of, question=item.question, gold_ids=sorted(gold),
            ranked_ids=ranked, confidence=search.confidence,
            unresolved=(not item.should_refuse and not gold), first_gold_rank=first,
        )
        if pipeline is not None:
            ans = pipeline.ask(item.question)
            res.answer, res.refused, res.refusal_reason = ans.text, ans.refused, ans.reason
            res.cited_ids = [c.chunk_id for c in ans.citations]
            if not ans.refused and gold:
                res.cites_gold = any(c in gold for c in res.cited_ids)
            if judge is not None and not ans.refused and item.language == "en":
                texts = {c.chunk_id: c.text for c in ans.citations}
                res.faithfulness = faithfulness(ans.text, texts, judge)
        results.append(res)
    return results


def _retrieval_rows(results: list[ItemResult]) -> list[tuple[list[str], set[str]]]:
    return [(r.ranked_ids, set(r.gold_ids)) for r in results if not r.should_refuse and not r.unresolved]


def summarize(results: list[ItemResult], threshold: float) -> dict[str, Any]:
    by_lang: dict[str, list[ItemResult]] = defaultdict(list)
    for r in results:
        by_lang[r.language].append(r)

    retrieval = {
        "overall": retrieval_metrics(_retrieval_rows(results)),
        "by_language": {lang: retrieval_metrics(_retrieval_rows(rs)) for lang, rs in sorted(by_lang.items())},
    }

    # Cross-lingual gap: the same question asked in English vs. translated.
    by_id = {r.id: r for r in results}
    gap: dict[str, Any] = {}
    for lang, rs in sorted(by_lang.items()):
        pairs = [(by_id[r.translation_of], r) for r in rs
                 if r.translation_of in by_id and not r.unresolved and not r.should_refuse]
        if pairs:
            en = mean([hit_at_k(e.ranked_ids, set(e.gold_ids), 5) for e, _ in pairs])
            tr = mean([hit_at_k(t.ranked_ids, set(t.gold_ids), 5) for _, t in pairs])
            assert en is not None and tr is not None
            gap[lang] = {"pairs": len(pairs), "en_recall@5": en, f"{lang}_recall@5": tr, "gap": en - tr}

    conf_rows = [(r.confidence, r.should_refuse) for r in results if not r.unresolved]
    best, table = calibrate(conf_rows)
    refusal = {
        "configured": refusal_stats(conf_rows, threshold).as_dict(),
        "by_language": {
            lang: refusal_stats([(r.confidence, r.should_refuse) for r in rs if not r.unresolved],
                                threshold).as_dict()
            for lang, rs in sorted(by_lang.items())
        },
        "calibration": {
            "best": best.as_dict() if best else None,
            "table": [s.as_dict() for s in table[:: 5]],
        },
        "confidence": {
            "answerable_mean": mean([r.confidence for r in results if not r.should_refuse]),
            "refuse_mean": mean([r.confidence for r in results if r.should_refuse]),
        },
    }

    summary: dict[str, Any] = {
        "n_items": len(results),
        "n_answerable": sum(not r.should_refuse for r in results),
        "n_should_refuse": sum(r.should_refuse for r in results),
        "unresolved": [r.id for r in results if r.unresolved],
        "retrieval": retrieval,
        "cross_lingual": gap,
        "refusal": refusal,
    }

    answered = [r for r in results if r.refused is not None]
    if answered:
        answerable = [r for r in answered if not r.should_refuse]
        refuse = [r for r in answered if r.should_refuse]
        faith = [r.faithfulness for r in answered if r.faithfulness is not None]
        summary["answers"] = {
            "n": len(answered),
            "answer_rate_answerable": mean([0.0 if r.refused else 1.0 for r in answerable]),
            "refusal_recall": mean([1.0 if r.refused else 0.0 for r in refuse]),
            "citation_gold_hit_rate": mean([1.0 if r.cites_gold else 0.0 for r in answerable
                                            if r.cites_gold is not None]),
            "faithfulness_en": mean(faith),
            "faithfulness_n": len(faith),
            "refusal_reasons": _count([r.refusal_reason for r in answered if r.refused]),
        }
    return summary


def _count(xs: list[str | None]) -> dict[str, int]:
    out: dict[str, int] = {}
    for x in xs:
        out[str(x)] = out.get(str(x), 0) + 1
    return out


def results_as_dicts(results: list[ItemResult]) -> list[dict[str, Any]]:
    return [asdict(r) for r in results]
