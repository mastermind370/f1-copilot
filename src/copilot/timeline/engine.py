"""Evaluates rules against a student's facts and produces an explained timeline.

Two ideas to understand here:

1. Three-valued conditions. A condition is True, False or UNKNOWN (a fact it needs is
   missing). `all` is False if any part is False, and UNKNOWN if none is False but one
   is UNKNOWN. `any` is the mirror image. This is Kleene logic, the same as SQL NULLs.
   Missing information never quietly counts as "no": the rule reports which facts it needs.

2. Explanations are built while computing, not afterwards. Every date expression returns
   its value together with the arithmetic that produced it, so the explanation can't drift
   from the computation.

The engine is pure: `as_of` is passed in, nothing reads the clock, and the same inputs
always give the same output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from copilot.timeline.dates import add_months, next_business_day, safe_date
from copilot.timeline.facts import StudentFacts
from copilot.timeline.schema import Rule


class MissingFacts(Exception):
    def __init__(self, names: set[str]) -> None:
        self.names = names
        super().__init__(", ".join(sorted(names)))


# --- conditions --------------------------------------------------------------------

@dataclass(frozen=True)
class Truth:
    value: bool | None  # None = unknown
    missing: frozenset[str] = frozenset()


def _compare(op: str, actual: Any, expected: Any) -> bool:
    if op == "eq":
        return bool(actual == expected)
    if op == "ne":
        return bool(actual != expected)
    if op == "in":
        return actual in expected
    if op == "gt":
        return bool(actual > expected)
    if op == "gte":
        return bool(actual >= expected)
    if op == "lt":
        return bool(actual < expected)
    if op == "lte":
        return bool(actual <= expected)
    raise ValueError(op)


def eval_condition(cond: dict[str, Any], facts: StudentFacts) -> Truth:
    if "all" in cond:
        parts = [eval_condition(c, facts) for c in cond["all"]]
        if any(p.value is False for p in parts):
            return Truth(False)
        missing = frozenset().union(*(p.missing for p in parts))
        return Truth(None, missing) if missing else Truth(True)
    if "any" in cond:
        parts = [eval_condition(c, facts) for c in cond["any"]]
        if any(p.value is True for p in parts):
            return Truth(True)
        missing = frozenset().union(*(p.missing for p in parts))
        return Truth(None, missing) if missing else Truth(False)
    if "not" in cond:
        inner = eval_condition(cond["not"], facts)
        return inner if inner.value is None else Truth(not inner.value)

    name = cond["fact"]
    actual = facts.get(name)
    if "is_set" in cond:
        return Truth((actual is not None) == cond["is_set"])
    if actual is None:
        if "missing_as" not in cond:
            return Truth(None, frozenset({name}))
        actual = cond["missing_as"]
    op = next(k for k in cond if k not in {"fact", "missing_as"})
    return Truth(_compare(op, actual, cond[op]))


# --- date expressions --------------------------------------------------------------

@dataclass(frozen=True)
class Computed:
    value: date
    trace: list[str]


def _offset_text(days: int, months: int) -> str:
    parts = []
    if months:
        parts.append(f"{'+' if months > 0 else '-'} {abs(months)} month{'s' if abs(months) != 1 else ''}")
    if days:
        parts.append(f"{'+' if days > 0 else '-'} {abs(days)} day{'s' if abs(days) != 1 else ''}")
    return " ".join(parts)


def _roll(e: dict[str, Any], c: Computed) -> Computed:
    if e.get("roll") != "next_business_day":
        return c
    rolled = next_business_day(c.value)
    if rolled == c.value:
        return c
    return Computed(rolled, [*c.trace, f"{c.value} is a {c.value:%A}, moved to next business day {rolled}"])


def eval_expr(e: dict[str, Any], facts: StudentFacts) -> Computed:
    if "min" in e or "max" in e:
        key = "min" if "min" in e else "max"
        results: list[Computed] = []
        skipped: list[str] = []
        missing: set[str] = set()
        for term in e[key]:
            try:
                results.append(eval_expr(term, facts))
            except MissingFacts as mf:
                if term.get("optional"):
                    skipped.append(", ".join(sorted(mf.names)))
                else:
                    missing |= mf.names
        if missing:
            raise MissingFacts(missing)
        chosen = (min if key == "min" else max)(results, key=lambda c: c.value)
        word = "earliest" if key == "min" else "latest"
        trace = [line for r in results for line in r.trace]
        if len(results) > 1:
            trace.append(f"{word} of {', '.join(str(r.value) for r in results)} = {chosen.value}")
        for s in skipped:
            trace.append(f"not provided: {s} (this date may be {'earlier' if key == 'min' else 'later'} "
                         "once you add it)")
        return _roll(e, Computed(chosen.value, trace))

    if "calendar" in e:
        cal = e["calendar"]
        year = facts.get(cal["year_fact"])
        if year is None:
            raise MissingFacts({cal["year_fact"]})
        y = int(year) + int(cal.get("year_offset", 0))
        d = safe_date(y, cal["month"], cal["day"])
        return _roll(e, Computed(d, [f"{cal['year_fact']} {year} -> {d:%B} {d.day}, {y}"]))

    name = e["fact"]
    base = facts.get(name)
    if base is None:
        raise MissingFacts({name})
    months, days = int(e.get("months", 0)), int(e.get("days", 0))
    d = add_months(base, months) + timedelta(days=days)
    offset = _offset_text(days, months)
    line = f"{name} {base} {offset} = {d}" if offset else f"{name} = {d}"
    return _roll(e, Computed(d, [line]))


# --- timeline ------------------------------------------------------------------------

@dataclass(frozen=True)
class TimelineItem:
    rule_id: str
    rule_version: int
    title: str
    kind: str
    label: str
    status: str  # upcoming | active | past | info
    explanation: list[str]
    source_url: str
    verification: str
    last_verified: date
    citation: str | None = None
    date: date | None = None
    start: date | None = None
    end: date | None = None
    value: int | None = None
    unit: str | None = None
    message: str | None = None
    days_until: int | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def sort_key(self) -> tuple[int, date]:
        anchor = self.date or self.start
        return (0, anchor) if anchor else (1, date.max)


@dataclass(frozen=True)
class NeedsInfo:
    rule_id: str
    title: str
    missing: list[str]


@dataclass
class Timeline:
    as_of: date
    items: list[TimelineItem] = field(default_factory=list)
    needs_info: list[NeedsInfo] = field(default_factory=list)
    not_applicable: list[str] = field(default_factory=list)
    not_in_effect: list[str] = field(default_factory=list)
    stale_rules: list[str] = field(default_factory=list)


def _status(kind: str, as_of: date, d: date | None, start: date | None, end: date | None) -> str:
    if kind in {"limit", "notice"}:
        return "info"
    if kind == "deadline":
        assert d is not None
        return "past" if as_of > d else "upcoming"
    if kind == "earliest":
        assert d is not None
        return "upcoming" if as_of < d else "active"
    assert start is not None and end is not None
    if as_of < start:
        return "upcoming"
    return "past" if as_of > end else "active"


def _evaluate_output(rule: Rule, out: dict[str, Any], facts: StudentFacts, as_of: date) -> TimelineItem:
    kind = out["kind"]
    common: dict[str, Any] = {
        "rule_id": rule.id, "rule_version": rule.version, "title": rule.title, "kind": kind,
        "label": out["label"], "source_url": rule.source.url,
        "verification": rule.source.verification, "last_verified": rule.source.last_verified,
        "citation": rule.source.citation, "notes": rule.notes,
    }
    if kind in {"deadline", "earliest"}:
        c = eval_expr(out["date"], facts)
        return TimelineItem(**common, date=c.value, explanation=c.trace,
                            status=_status(kind, as_of, c.value, None, None),
                            days_until=(c.value - as_of).days)
    if kind == "window":
        s, e = eval_expr(out["start"], facts), eval_expr(out["end"], facts)
        expl = [f"opens: {t}" for t in s.trace] + [f"closes: {t}" for t in e.trace]
        if e.value < s.value:
            expl.append("WARNING: this window closed before it opened; talk to your DSO now")
        return TimelineItem(**common, start=s.value, end=e.value, explanation=expl,
                            status=_status(kind, as_of, None, s.value, e.value),
                            days_until=(s.value - as_of).days)
    if kind == "limit":
        return TimelineItem(**common, value=out["value"], unit=out["unit"], status="info",
                            explanation=[f"limit set by rule {rule.id} v{rule.version}"])
    return TimelineItem(**common, message=out["message"], status="info",
                        explanation=[f"applies because of rule {rule.id} v{rule.version}"])


def evaluate(
    rules: list[Rule], facts: StudentFacts, as_of: date, max_age_days: int = 180
) -> Timeline:
    tl = Timeline(as_of=as_of)
    for rule in rules:
        if (as_of - rule.source.last_verified).days > max_age_days:
            tl.stale_rules.append(rule.id)
        if not rule.in_effect(as_of):
            tl.not_in_effect.append(rule.id)
            continue

        if rule.when is not None:
            t = eval_condition(rule.when, facts)
            if t.value is False:
                tl.not_applicable.append(rule.id)
                continue
            if t.value is None:
                tl.needs_info.append(NeedsInfo(rule.id, rule.title, sorted(t.missing)))
                continue

        missing: set[str] = set()
        produced = 0
        for out in rule.outputs:
            if "when" in out:
                t = eval_condition(out["when"], facts)
                if t.value is False:
                    continue
                if t.value is None:
                    missing |= t.missing
                    continue
            try:
                tl.items.append(_evaluate_output(rule, out, facts, as_of))
                produced += 1
            except MissingFacts as mf:
                missing |= mf.names
        if missing:
            tl.needs_info.append(NeedsInfo(rule.id, rule.title, sorted(missing)))
        elif produced == 0:
            tl.not_applicable.append(rule.id)

    tl.items.sort(key=lambda i: (i.sort_key, i.rule_id, i.label))
    return tl
