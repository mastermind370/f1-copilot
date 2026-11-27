"""Loading and validating rule files.

A rule file is data, not code. The YAML is checked against a strict schema at load time,
so a typo in a fact name or a bad source URL fails immediately, in CI, instead of
producing a wrong date for a student later.

Rule file shape (see rules/*.yaml for real examples):

    id: opt-post-completion-filing-window      # must equal the file name
    version: 1                                 # bump on every substantive change
    title: ...
    category: opt
    summary: ...
    source:
      url: https://...                         # https only
      citation: 8 CFR 214.2(f)(11)             # optional
      verification: primary | secondary        # did we check the primary source?
      last_verified: 2026-11-27
    effective: {from: null, until: null}       # optional; for rule changes over time
    notes: [...]                               # optional caveats shown to the user
    when: <condition>                          # optional; rule applies only if true
    outputs: [<output>, ...]

    output kinds:
      deadline  date: <expr>          on or before
      earliest  date: <expr>          on or after
      window    start: <expr>  end: <expr>
      limit     value: <int>  unit: days
      notice    message: <str>
    every output: label (required), when (optional)

    <expr>      := {fact: NAME, days: N, months: N, optional: bool, roll: next_business_day}
                 | {min: [<expr>, ...]} | {max: [<expr>, ...]}
                 | {calendar: {year_fact: NAME, year_offset: N, month: M, day: D}, roll: ...}
    <condition> := {all: [...]} | {any: [...]} | {not: <condition>}
                 | {fact: NAME, <op>: VALUE, missing_as: VALUE}
                   op in eq ne in gt gte lt lte is_set
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from copilot.timeline.facts import FACT_TYPES

OUTPUT_KINDS = {"deadline", "earliest", "window", "limit", "notice"}
COMPARE_OPS = {"eq", "ne", "in", "gt", "gte", "lt", "lte", "is_set"}
ROLLS = {"next_business_day"}
VERIFICATION = {"primary", "secondary"}


class RuleValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("invalid rules:\n  " + "\n  ".join(errors))


@dataclass(frozen=True)
class Source:
    url: str
    verification: str
    last_verified: date
    citation: str | None = None


@dataclass(frozen=True)
class Rule:
    id: str
    version: int
    title: str
    category: str
    summary: str
    source: Source
    outputs: list[dict[str, Any]]
    when: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)
    effective_from: date | None = None
    effective_until: date | None = None
    path: str = ""

    def in_effect(self, as_of: date) -> bool:
        if self.effective_from and as_of < self.effective_from:
            return False
        return not (self.effective_until and as_of > self.effective_until)


class _Validator:
    def __init__(self, where: str) -> None:
        self.where = where
        self.errors: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(f"{self.where}: {msg}")

    def fact(self, name: Any, ctx: str, want: type | None = None) -> None:
        if name not in FACT_TYPES:
            self.err(f"{ctx}: unknown fact {name!r}")
        elif want is not None and FACT_TYPES[name] is not want:
            self.err(f"{ctx}: fact {name!r} is {FACT_TYPES[name].__name__}, expected {want.__name__}")

    def value_type(self, fact: str, value: Any, ctx: str) -> None:
        t = FACT_TYPES.get(fact)
        if t is None or value is None:
            return
        ok = isinstance(value, t) and not (t is int and isinstance(value, bool))
        if not ok:
            self.err(f"{ctx}: value {value!r} does not match type of {fact!r} ({t.__name__})")

    def condition(self, c: Any, ctx: str) -> None:
        if not isinstance(c, dict):
            self.err(f"{ctx}: condition must be a mapping")
            return
        if "all" in c or "any" in c:
            key = "all" if "all" in c else "any"
            items = c[key]
            if not isinstance(items, list) or not items:
                self.err(f"{ctx}.{key}: must be a non-empty list")
                return
            for i, sub in enumerate(items):
                self.condition(sub, f"{ctx}.{key}[{i}]")
            return
        if "not" in c:
            self.condition(c["not"], f"{ctx}.not")
            return
        if "fact" not in c:
            self.err(f"{ctx}: condition needs all/any/not/fact")
            return
        self.fact(c["fact"], ctx)
        ops = [k for k in c if k in COMPARE_OPS]
        extra = set(c) - COMPARE_OPS - {"fact", "missing_as"}
        if len(ops) != 1:
            self.err(f"{ctx}: exactly one operator required from {sorted(COMPARE_OPS)}")
        if extra:
            self.err(f"{ctx}: unknown keys {sorted(extra)}")
        if not ops:
            return
        op = ops[0]
        if op == "is_set":
            if not isinstance(c[op], bool):
                self.err(f"{ctx}: is_set takes true/false")
        elif op == "in":
            if not isinstance(c[op], list):
                self.err(f"{ctx}: 'in' takes a list")
            else:
                for v in c[op]:
                    self.value_type(c["fact"], v, ctx)
        else:
            self.value_type(c["fact"], c[op], ctx)
        if "missing_as" in c:
            self.value_type(c["fact"], c["missing_as"], f"{ctx}.missing_as")

    def expr(self, e: Any, ctx: str) -> None:
        if not isinstance(e, dict):
            self.err(f"{ctx}: date expression must be a mapping")
            return
        if "roll" in e and e["roll"] not in ROLLS:
            self.err(f"{ctx}: roll must be one of {sorted(ROLLS)}")
        if "min" in e or "max" in e:
            key = "min" if "min" in e else "max"
            terms = e[key]
            if not isinstance(terms, list) or len(terms) < 2:
                self.err(f"{ctx}.{key}: needs a list of at least 2 expressions")
                return
            if all(isinstance(t, dict) and t.get("optional") for t in terms):
                self.err(f"{ctx}.{key}: at least one term must be non-optional")
            for i, t in enumerate(terms):
                self.expr(t, f"{ctx}.{key}[{i}]")
            return
        if "calendar" in e:
            cal = e["calendar"]
            if not isinstance(cal, dict):
                self.err(f"{ctx}.calendar: must be a mapping")
                return
            self.fact(cal.get("year_fact"), f"{ctx}.calendar", int)
            for k, lo, hi in (("month", 1, 12), ("day", 1, 31)):
                v = cal.get(k)
                if not isinstance(v, int) or not lo <= v <= hi:
                    self.err(f"{ctx}.calendar.{k}: must be an integer {lo}-{hi}")
            return
        if "fact" not in e:
            self.err(f"{ctx}: expression needs fact, min, max or calendar")
            return
        self.fact(e["fact"], ctx, date)
        for k in ("days", "months"):
            if k in e and (not isinstance(e[k], int) or isinstance(e[k], bool)):
                self.err(f"{ctx}.{k}: must be an integer")
        extra = set(e) - {"fact", "days", "months", "optional", "roll"}
        if extra:
            self.err(f"{ctx}: unknown keys {sorted(extra)}")

    def output(self, o: Any, ctx: str) -> None:
        if not isinstance(o, dict):
            self.err(f"{ctx}: output must be a mapping")
            return
        kind = o.get("kind")
        if kind not in OUTPUT_KINDS:
            self.err(f"{ctx}: kind must be one of {sorted(OUTPUT_KINDS)}")
            return
        if not isinstance(o.get("label"), str) or not o["label"].strip():
            self.err(f"{ctx}: label is required")
        if "when" in o:
            self.condition(o["when"], f"{ctx}.when")
        if kind in {"deadline", "earliest"}:
            self.expr(o.get("date"), f"{ctx}.date")
        elif kind == "window":
            self.expr(o.get("start"), f"{ctx}.start")
            self.expr(o.get("end"), f"{ctx}.end")
        elif kind == "limit":
            if not isinstance(o.get("value"), int) or o["value"] < 0:
                self.err(f"{ctx}: limit needs a non-negative integer value")
            if o.get("unit") != "days":
                self.err(f"{ctx}: limit unit must be 'days'")
        elif kind == "notice" and not isinstance(o.get("message"), str):
            self.err(f"{ctx}: notice needs a message")


def _as_date(v: Any) -> date | None:
    if v is None or isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def parse_rule(raw: Any, path: Path) -> tuple[Rule | None, list[str]]:
    v = _Validator(path.name)
    if not isinstance(raw, dict):
        v.err("file must contain a mapping")
        return None, v.errors

    for key in ("id", "version", "title", "category", "summary", "source", "outputs"):
        if key not in raw:
            v.err(f"missing required key {key!r}")
    known = {"id", "version", "title", "category", "summary", "source", "outputs",
             "when", "notes", "effective", "changelog"}
    if extra := set(raw) - known:
        v.err(f"unknown keys {sorted(extra)}")
    if v.errors:
        return None, v.errors

    if raw["id"] != path.stem:
        v.err(f"id {raw['id']!r} must match file name {path.stem!r}")
    if not isinstance(raw["version"], int) or raw["version"] < 1:
        v.err("version must be a positive integer")

    src = raw["source"] if isinstance(raw["source"], dict) else {}
    url = src.get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        v.err("source.url must be an https URL")
    if src.get("verification") not in VERIFICATION:
        v.err(f"source.verification must be one of {sorted(VERIFICATION)}")
    last_verified = None
    try:
        last_verified = _as_date(src.get("last_verified"))
    except ValueError:
        pass
    if last_verified is None:
        v.err("source.last_verified must be a date (YYYY-MM-DD)")

    if "when" in raw:
        v.condition(raw["when"], "when")
    outputs = raw["outputs"]
    if not isinstance(outputs, list) or not outputs:
        v.err("outputs must be a non-empty list")
        outputs = []
    for i, o in enumerate(outputs):
        v.output(o, f"outputs[{i}]")

    eff = raw.get("effective") or {}
    try:
        eff_from, eff_until = _as_date(eff.get("from")), _as_date(eff.get("until"))
    except ValueError:
        v.err("effective.from/until must be dates")
        eff_from = eff_until = None

    if v.errors:
        return None, v.errors
    assert last_verified is not None
    return Rule(
        id=raw["id"], version=raw["version"], title=raw["title"], category=raw["category"],
        summary=raw["summary"],
        source=Source(url=url, verification=src["verification"],
                      last_verified=last_verified, citation=src.get("citation")),
        outputs=outputs, when=raw.get("when"), notes=list(raw.get("notes") or []),
        effective_from=eff_from, effective_until=eff_until, path=str(path),
    ), []


def load_rules(rules_dir: Path) -> list[Rule]:
    """Load every *.yaml rule. Collects all errors before raising, so CI shows them at once."""
    if not rules_dir.is_dir():
        raise RuleValidationError([f"rules directory not found: {rules_dir}"])
    rules: list[Rule] = []
    errors: list[str] = []
    for path in sorted(rules_dir.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            errors.append(f"{path.name}: YAML parse error: {exc}")
            continue
        rule, errs = parse_rule(raw, path)
        errors.extend(errs)
        if rule:
            rules.append(rule)
    seen: set[str] = set()
    for r in rules:
        if r.id in seen:
            errors.append(f"duplicate rule id {r.id!r}")
        seen.add(r.id)
    if errors:
        raise RuleValidationError(errors)
    return rules
