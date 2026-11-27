"""Unit tests for the engine's building blocks: dates, facts, conditions, expressions, schema."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from copilot.timeline.dates import add_months, next_business_day, safe_date
from copilot.timeline.engine import MissingFacts, eval_condition, eval_expr
from copilot.timeline.facts import FACT_TYPES, FactError, StudentFacts, parse_facts
from copilot.timeline.schema import RuleValidationError, load_rules

D = date.fromisoformat


# --- dates -----------------------------------------------------------------------------

class TestDates:
    @pytest.mark.parametrize(
        ("start", "months", "expected"),
        [
            ("2027-01-31", 1, "2027-02-28"),  # clamp to month end
            ("2028-01-31", 1, "2028-02-29"),  # leap year
            ("2026-08-31", 6, "2027-02-28"),  # crosses a year boundary and clamps
            ("2026-12-15", 1, "2027-01-15"),  # December -> January
            ("2027-03-31", -1, "2027-02-28"),  # negative months clamp too
            ("2027-05-15", 12, "2028-05-15"),
            ("2027-05-15", 0, "2027-05-15"),
        ],
    )
    def test_add_months(self, start: str, months: int, expected: str) -> None:
        assert add_months(D(start), months) == D(expected)

    @pytest.mark.parametrize(
        ("day", "expected"),
        [
            ("2028-04-15", "2028-04-17"),  # Saturday -> Monday
            ("2029-04-15", "2029-04-16"),  # Sunday -> Monday
            ("2027-04-15", "2027-04-15"),  # Thursday unchanged
        ],
    )
    def test_next_business_day(self, day: str, expected: str) -> None:
        assert next_business_day(D(day)) == D(expected)

    def test_safe_date_clamps(self) -> None:
        assert safe_date(2027, 2, 31) == D("2027-02-28")


# --- facts -----------------------------------------------------------------------------

class TestFacts:
    def test_types_are_derived_from_dataclass(self) -> None:
        assert FACT_TYPES["program_end_date"] is date
        assert FACT_TYPES["on_opt"] is bool
        assert FACT_TYPES["tax_year"] is int
        assert FACT_TYPES["degree_level"] is str

    def test_parses_strings_from_cli(self) -> None:
        f = parse_facts({"program_end_date": "2027-05-15", "on_opt": "yes",
                         "tax_year": "2026", "degree_level": "Master"})
        assert f.program_end_date == D("2027-05-15")
        assert f.on_opt is True and f.tax_year == 2026 and f.degree_level == "master"

    def test_accepts_native_yaml_types(self) -> None:
        f = parse_facts(yaml.safe_load("program_end_date: 2027-05-15\non_opt: false\n"))
        assert f.program_end_date == D("2027-05-15") and f.on_opt is False

    @pytest.mark.parametrize(
        "raw",
        [
            {"program_end_dat": "2027-05-15"},  # typo -> unknown fact
            {"program_end_date": "05/15/2027"},  # wrong date format
            {"on_opt": "maybe"},
            {"tax_year": "twenty"},
            {"tax_year": True},  # bool is not an int here
            {"degree_level": "phd"},
        ],
    )
    def test_rejects_bad_input(self, raw: dict[str, Any]) -> None:
        with pytest.raises(FactError):
            parse_facts(raw)

    def test_everything_optional(self) -> None:
        assert parse_facts({}) == StudentFacts()


# --- conditions (three-valued logic) ---------------------------------------------------

F_OPT = StudentFacts(on_opt=True)
EMPTY = StudentFacts()


class TestConditions:
    def test_simple(self) -> None:
        assert eval_condition({"fact": "on_opt", "eq": True}, F_OPT).value is True
        assert eval_condition({"fact": "on_opt", "eq": False}, F_OPT).value is False

    def test_missing_is_unknown_not_false(self) -> None:
        t = eval_condition({"fact": "on_opt", "eq": False}, EMPTY)
        assert t.value is None and t.missing == {"on_opt"}

    def test_missing_as_default(self) -> None:
        assert eval_condition({"fact": "on_stem_opt", "eq": False, "missing_as": False}, EMPTY).value is True

    def test_all_false_wins_over_unknown(self) -> None:
        c = {"all": [{"fact": "on_opt", "eq": False}, {"fact": "stem_degree", "eq": True}]}
        assert eval_condition(c, F_OPT).value is False  # no need to ask about stem_degree

    def test_all_unknown_when_rest_true(self) -> None:
        c = {"all": [{"fact": "on_opt", "eq": True}, {"fact": "stem_degree", "eq": True}]}
        t = eval_condition(c, F_OPT)
        assert t.value is None and t.missing == {"stem_degree"}

    def test_any_true_wins_over_unknown(self) -> None:
        c = {"any": [{"fact": "on_opt", "eq": True}, {"fact": "stem_degree", "eq": True}]}
        assert eval_condition(c, F_OPT).value is True

    def test_any_unknown_when_rest_false(self) -> None:
        c = {"any": [{"fact": "on_opt", "eq": False}, {"fact": "stem_degree", "eq": True}]}
        assert eval_condition(c, F_OPT).value is None

    def test_not_preserves_unknown(self) -> None:
        assert eval_condition({"not": {"fact": "on_opt", "eq": True}}, EMPTY).value is None
        assert eval_condition({"not": {"fact": "on_opt", "eq": True}}, F_OPT).value is False

    def test_is_set_is_never_unknown(self) -> None:
        assert eval_condition({"fact": "tax_year", "is_set": True}, EMPTY).value is False
        assert eval_condition({"fact": "tax_year", "is_set": False}, EMPTY).value is True

    def test_comparisons(self) -> None:
        f = StudentFacts(full_time_cpt_months=12, degree_level="master",
                         program_end_date=D("2027-05-15"))
        assert eval_condition({"fact": "full_time_cpt_months", "gte": 12}, f).value is True
        assert eval_condition({"fact": "full_time_cpt_months", "gt": 12}, f).value is False
        assert eval_condition({"fact": "degree_level", "in": ["master", "doctorate"]}, f).value is True
        assert eval_condition({"fact": "program_end_date", "lt": D("2027-06-01")}, f).value is True


# --- expressions -----------------------------------------------------------------------

class TestExpressions:
    f = StudentFacts(program_end_date=D("2027-05-15"), dso_recommendation_date=D("2027-06-01"),
                     tax_year=2027)

    def test_offset_and_trace(self) -> None:
        c = eval_expr({"fact": "program_end_date", "days": 60}, self.f)
        assert c.value == D("2027-07-14")
        assert c.trace == ["program_end_date 2027-05-15 + 60 days = 2027-07-14"]

    def test_min_picks_earliest_and_explains(self) -> None:
        c = eval_expr({"min": [{"fact": "program_end_date", "days": 60},
                               {"fact": "dso_recommendation_date", "days": 30}]}, self.f)
        assert c.value == D("2027-07-01")
        assert any("earliest of" in t for t in c.trace)

    def test_optional_missing_term_skipped_with_note(self) -> None:
        c = eval_expr({"min": [{"fact": "program_end_date", "days": 60},
                               {"fact": "opt_ead_end_date", "optional": True}]}, self.f)
        assert c.value == D("2027-07-14")
        assert any("not provided: opt_ead_end_date" in t for t in c.trace)

    def test_required_missing_term_raises(self) -> None:
        with pytest.raises(MissingFacts) as exc:
            eval_expr({"max": [{"fact": "program_end_date"}, {"fact": "opt_ead_end_date"}]}, self.f)
        assert exc.value.names == {"opt_ead_end_date"}

    def test_calendar_with_roll(self) -> None:
        c = eval_expr({"calendar": {"year_fact": "tax_year", "year_offset": 1, "month": 4, "day": 15},
                       "roll": "next_business_day"}, self.f)
        assert c.value == D("2028-04-17")
        assert "Saturday" in c.trace[-1]


# --- schema validation -----------------------------------------------------------------

def _rule(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "test-rule", "version": 1, "title": "T", "category": "test", "summary": "S",
        "source": {"url": "https://example.gov/x", "verification": "primary",
                   "last_verified": "2026-11-27"},
        "outputs": [{"kind": "deadline", "label": "L",
                     "date": {"fact": "program_end_date", "days": 1}}],
    }
    base.update(overrides)
    return base


def _write(tmp_path: Path, rule: dict[str, Any], name: str | None = None) -> Path:
    (tmp_path / f"{name or rule['id']}.yaml").write_text(yaml.safe_dump(rule))
    return tmp_path


class TestSchema:
    def test_valid_rule_loads(self, tmp_path: Path) -> None:
        [r] = load_rules(_write(tmp_path, _rule()))
        assert r.id == "test-rule" and r.source.last_verified == D("2026-11-27")

    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            ({"source": {"url": "http://insecure.gov", "verification": "primary",
                         "last_verified": "2026-11-27"}}, "https"),
            ({"source": {"url": "https://x.gov", "verification": "vibes",
                         "last_verified": "2026-11-27"}}, "verification"),
            ({"source": {"url": "https://x.gov", "verification": "primary"}}, "last_verified"),
            ({"outputs": [{"kind": "deadline", "label": "L",
                           "date": {"fact": "program_end_dat", "days": 1}}]}, "unknown fact"),
            ({"outputs": [{"kind": "deadline", "label": "L",
                           "date": {"fact": "on_opt", "days": 1}}]}, "expected date"),
            ({"outputs": [{"kind": "explode", "label": "L"}]}, "kind"),
            ({"outputs": [{"kind": "limit", "label": "L", "value": -1, "unit": "days"}]}, "non-negative"),
            ({"outputs": []}, "non-empty"),
            ({"when": {"fact": "on_opt", "eq": "yes"}}, "does not match type"),
            ({"when": {"fact": "on_opt", "eq": True, "gt": 1}}, "exactly one operator"),
            ({"outputs": [{"kind": "deadline", "label": "L", "date": {"min": [
                {"fact": "program_end_date", "optional": True},
                {"fact": "opt_ead_end_date", "optional": True}]}}]}, "non-optional"),
            ({"version": 0}, "version"),
            ({"surprise": 1}, "unknown keys"),
        ],
    )
    def test_rejects_invalid(self, tmp_path: Path, overrides: dict[str, Any], message: str) -> None:
        with pytest.raises(RuleValidationError) as exc:
            load_rules(_write(tmp_path, _rule(**overrides)))
        assert message in str(exc.value)

    def test_id_must_match_filename(self, tmp_path: Path) -> None:
        with pytest.raises(RuleValidationError, match="must match file name"):
            load_rules(_write(tmp_path, _rule(), name="other-name"))

    def test_reports_all_errors_at_once(self, tmp_path: Path) -> None:
        _write(tmp_path, _rule(id="a", version=0), name="a")
        _write(tmp_path, _rule(id="b", source={}), name="b")
        with pytest.raises(RuleValidationError) as exc:
            load_rules(tmp_path)
        assert any(e.startswith("a.yaml") for e in exc.value.errors)
        assert any(e.startswith("b.yaml") for e in exc.value.errors)

    def test_missing_dir(self, tmp_path: Path) -> None:
        with pytest.raises(RuleValidationError, match="not found"):
            load_rules(tmp_path / "nope")
