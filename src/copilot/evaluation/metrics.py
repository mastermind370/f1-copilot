"""Pure metric functions. No models, no I/O, and easy to verify by hand.

Definitions:
- recall@k: fraction of answerable questions with at least one gold chunk in the top k
  (the "hit rate" form of recall, standard for single-answer QA retrieval).
- MRR@10: mean of 1/rank of the first gold chunk, 0 if none in the top 10.
- Refusal is treated as binary classification where "should refuse" is the positive class:
    refusal_recall      = refused / should_refuse         (did we catch off-topic questions?)
    false_refusal_rate  = refused / answerable            (how often did we stonewall a real question?)
    balanced_accuracy   = mean(refusal_recall, 1 - false_refusal_rate)
  Balanced accuracy is used for calibration because the classes are imbalanced.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

KS = (1, 3, 5, 10)


def hit_at_k(ranked: Sequence[str], gold: set[str], k: int) -> float:
    return 1.0 if any(cid in gold for cid in ranked[:k]) else 0.0


def reciprocal_rank(ranked: Sequence[str], gold: set[str], k: int = 10) -> float:
    for rank, cid in enumerate(ranked[:k], start=1):
        if cid in gold:
            return 1.0 / rank
    return 0.0


def mean(xs: Sequence[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def retrieval_metrics(rows: Sequence[tuple[Sequence[str], set[str]]]) -> dict[str, float | int | None]:
    """rows: (ranked chunk ids, gold ids) for answerable items with resolved gold."""
    out: dict[str, float | int | None] = {"n": len(rows)}
    for k in KS:
        out[f"recall@{k}"] = mean([hit_at_k(r, g, k) for r, g in rows])
    out["mrr@10"] = mean([reciprocal_rank(r, g) for r, g in rows])
    return out


@dataclass(frozen=True)
class RefusalStats:
    threshold: float
    true_refusals: int  # should refuse, did refuse
    missed_refusals: int  # should refuse, answered
    false_refusals: int  # answerable, refused
    correct_answers: int  # answerable, answered

    @property
    def refusal_recall(self) -> float | None:
        n = self.true_refusals + self.missed_refusals
        return self.true_refusals / n if n else None

    @property
    def false_refusal_rate(self) -> float | None:
        n = self.false_refusals + self.correct_answers
        return self.false_refusals / n if n else None

    @property
    def balanced_accuracy(self) -> float | None:
        r, f = self.refusal_recall, self.false_refusal_rate
        if r is None or f is None:
            return None
        return (r + (1 - f)) / 2

    def as_dict(self) -> dict[str, float | int | None]:
        d: dict[str, float | int | None] = dict(asdict(self))
        d.update(refusal_recall=self.refusal_recall, false_refusal_rate=self.false_refusal_rate,
                 balanced_accuracy=self.balanced_accuracy)
        return d


def refusal_stats(rows: Sequence[tuple[float, bool]], threshold: float) -> RefusalStats:
    """rows: (confidence, should_refuse). The gate refuses when confidence < threshold."""
    tr = mr = fr = ca = 0
    for conf, should in rows:
        refused = conf < threshold
        if should:
            tr += refused
            mr += not refused
        else:
            fr += refused
            ca += not refused
    return RefusalStats(threshold, tr, mr, fr, ca)


def calibrate(
    rows: Sequence[tuple[float, bool]], lo: float = 0.50, hi: float = 0.99, step: float = 0.01
) -> tuple[RefusalStats | None, list[RefusalStats]]:
    """Sweep thresholds and pick the best balanced accuracy.

    Ties go to the lower false-refusal rate, then the lower threshold: when two
    thresholds are equally good, prefer answering real questions.
    """
    table: list[RefusalStats] = []
    t = lo
    while t <= hi + 1e-9:
        table.append(refusal_stats(rows, round(t, 4)))
        t += step
    scored = [s for s in table if s.balanced_accuracy is not None]
    if not scored:
        return None, table
    best = max(scored, key=lambda s: (s.balanced_accuracy, -(s.false_refusal_rate or 0), -s.threshold))
    return best, table


def lookup(summary: dict[str, object], dotted: str) -> object:
    cur: object = summary
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(dotted)
        cur = cur[part]
    return cur


def check_thresholds(summary: dict[str, object], thresholds: dict[str, dict[str, float]]) -> list[str]:
    """Returns human-readable failures. A metric that is missing (None) counts as a failure."""
    failures: list[str] = []
    for direction in ("min", "max"):
        for key, limit in (thresholds.get(direction) or {}).items():
            try:
                value = lookup(summary, key)
            except KeyError:
                failures.append(f"{key}: metric not found")
                continue
            if not isinstance(value, int | float):
                failures.append(f"{key}: no value (got {value!r})")
            elif direction == "min" and value < limit:
                failures.append(f"{key} = {value:.3f} is below the minimum {limit:.3f}")
            elif direction == "max" and value > limit:
                failures.append(f"{key} = {value:.3f} is above the maximum {limit:.3f}")
    return failures


def ratchet_thresholds(
    summary: dict[str, object], thresholds: dict[str, dict[str, float]], margin: float = 0.05
) -> dict[str, dict[str, float]]:
    """Set each gate to the measured value minus a margin, so CI catches regressions
    without being flaky. Only existing keys are updated. Gates only ever move with data."""
    import math

    # round() before floor/ceil: (0.10 + 0.05) * 100 == 15.000000000000002 in floating point.
    out: dict[str, dict[str, float]] = {"min": {}, "max": {}}
    for key in thresholds.get("min") or {}:
        v = lookup(summary, key)
        if isinstance(v, int | float):
            out["min"][key] = max(0.0, math.floor(round((v - margin) * 100, 6)) / 100)
    for key in thresholds.get("max") or {}:
        v = lookup(summary, key)
        if isinstance(v, int | float):
            out["max"][key] = min(1.0, math.ceil(round((v + margin) * 100, 6)) / 100)
    return out
