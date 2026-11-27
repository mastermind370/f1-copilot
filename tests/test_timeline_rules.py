"""Tests against the real, shipped rule files in rules/.

These pin down the actual deadlines a student would see. If someone edits a rule, a test
here changes too. That makes the change visible in code review, which is the point.
"""

from __future__ import annotations

from datetime import date
from itertools import product
from pathlib import Path
from typing import Any

import pytest
import yaml

from copilot.timeline import Rule, Timeline, TimelineItem, evaluate, load_rules, parse_facts

RULES_DIR = Path(__file__).resolve().parents[1] / "rules"
AS_OF = date(2026, 11, 27)
D = date.fromisoformat


@pytest.fixture(scope="module")
def rules() -> list[Rule]:
    return load_rules(RULES_DIR)


def run(rules: list[Rule], as_of: date = AS_OF, **facts: Any) -> Timeline:
    return evaluate(rules, parse_facts(facts), as_of)


def item(tl: Timeline, rule_id: str, label_contains: str = "") -> TimelineItem:
    matches = [i for i in tl.items if i.rule_id == rule_id and label_contains in i.label]
    assert len(matches) == 1, f"expected one item for {rule_id!r}, got {[i.label for i in matches]}"
    return matches[0]


def ids(tl: Timeline) -> set[str]:
    return {i.rule_id for i in tl.items}


class TestShippedRules:
    def test_all_rules_valid(self, rules: list[Rule]) -> None:
        assert len(rules) >= 10

    def test_every_rule_has_source_and_recent_verification(self, rules: list[Rule]) -> None:
        for r in rules:
            assert r.source.url.startswith("https://")
            assert (AS_OF - r.source.last_verified).days <= 180, r.id

    def test_example_facts_file_parses(self) -> None:
        raw = yaml.safe_load((RULES_DIR.parent / "examples" / "facts.example.yaml").read_text())
        parse_facts(raw)


class TestOptFilingWindow:
    def test_basic_window(self, rules: list[Rule]) -> None:
        it = item(run(rules, program_end_date="2027-05-15"), "opt-post-completion-filing-window")
        assert (it.start, it.end) == (D("2027-02-14"), D("2027-07-14"))
        assert it.status == "upcoming" and it.days_until == 79

    def test_dso_recommendation_shortens_window(self, rules: list[Rule]) -> None:
        it = item(run(rules, program_end_date="2027-05-15", dso_recommendation_date="2027-06-01"),
                  "opt-post-completion-filing-window")
        assert it.end == D("2027-07-01")  # 30 days after recommendation beats 60 after program end

    def test_late_dso_recommendation_cannot_extend_window(self, rules: list[Rule]) -> None:
        it = item(run(rules, program_end_date="2027-05-15", dso_recommendation_date="2027-07-10"),
                  "opt-post-completion-filing-window")
        assert it.end == D("2027-07-14")

    def test_status_transitions(self, rules: list[Rule]) -> None:
        f = {"program_end_date": "2027-05-15"}
        assert item(run(rules, D("2027-02-13"), **f), "opt-post-completion-filing-window").status == "upcoming"
        assert item(run(rules, D("2027-02-14"), **f), "opt-post-completion-filing-window").status == "active"
        assert item(run(rules, D("2027-07-14"), **f), "opt-post-completion-filing-window").status == "active"
        assert item(run(rules, D("2027-07-15"), **f), "opt-post-completion-filing-window").status == "past"

    def test_needs_program_end_date(self, rules: list[Rule]) -> None:
        tl = run(rules)
        need = {n.rule_id: n.missing for n in tl.needs_info}
        assert need["opt-post-completion-filing-window"] == ["program_end_date"]


class TestGracePeriod:
    def test_not_on_opt(self, rules: list[Rule]) -> None:
        it = item(run(rules, program_end_date="2027-05-15", on_opt=False), "grace-period-after-completion")
        assert it.date == D("2027-07-14")
        assert any("vacated" in n for n in it.notes)

    def test_on_opt_uses_ead_end(self, rules: list[Rule]) -> None:
        it = item(run(rules, on_opt=True, opt_ead_end_date="2028-06-30"), "grace-period-after-completion")
        assert it.date == D("2028-08-29")

    def test_unknown_opt_status_asks(self, rules: list[Rule]) -> None:
        tl = run(rules, program_end_date="2027-05-15")
        assert "grace-period-after-completion" not in ids(tl)
        assert any(n.rule_id == "grace-period-after-completion" and "on_opt" in n.missing
                   for n in tl.needs_info)


class TestStemOpt:
    base = {"on_opt": True, "stem_degree": True, "opt_ead_end_date": "2028-06-30"}

    def test_window(self, rules: list[Rule]) -> None:
        it = item(run(rules, **self.base), "stem-opt-extension-filing-window")
        assert (it.start, it.end) == (D("2028-04-01"), D("2028-06-30"))

    def test_recommendation_limits_end(self, rules: list[Rule]) -> None:
        it = item(run(rules, **self.base, stem_dso_recommendation_date="2028-04-10"),
                  "stem-opt-extension-filing-window")
        assert it.end == D("2028-06-09")

    def test_not_applicable_without_stem_degree(self, rules: list[Rule]) -> None:
        tl = run(rules, **{**self.base, "stem_degree": False})
        assert "stem-opt-extension-filing-window" in tl.not_applicable

    def test_not_applicable_when_already_on_stem(self, rules: list[Rule]) -> None:
        tl = run(rules, **self.base, on_stem_opt=True)
        assert "stem-opt-extension-filing-window" in tl.not_applicable


class TestUnemployment:
    def test_regular_opt(self, rules: list[Rule]) -> None:
        assert item(run(rules, on_opt=True), "opt-unemployment-limit").value == 90

    def test_stem_opt(self, rules: list[Rule]) -> None:
        assert item(run(rules, on_opt=True, on_stem_opt=True), "opt-unemployment-limit").value == 150

    def test_not_on_opt(self, rules: list[Rule]) -> None:
        assert "opt-unemployment-limit" in run(rules, on_opt=False).not_applicable


class TestTravelSignature:
    def test_student_12_months(self, rules: list[Rule]) -> None:
        it = item(run(rules, on_opt=False, last_travel_signature_date="2026-08-20"),
                  "i20-travel-signature-validity")
        assert it.date == D("2027-08-20")

    def test_capped_by_program_end(self, rules: list[Rule]) -> None:
        it = item(run(rules, on_opt=False, last_travel_signature_date="2026-08-20",
                      program_end_date="2027-05-15"), "i20-travel-signature-validity")
        assert it.date == D("2027-05-15")

    def test_opt_6_months_with_month_end_clamp(self, rules: list[Rule]) -> None:
        it = item(run(rules, on_opt=True, last_travel_signature_date="2026-08-31"),
                  "i20-travel-signature-validity")
        assert it.date == D("2027-02-28")

    def test_expired_signature_is_past(self, rules: list[Rule]) -> None:
        it = item(run(rules, on_opt=False, last_travel_signature_date="2025-01-01"),
                  "i20-travel-signature-validity")
        assert it.status == "past"

    def test_no_signature_date_means_not_applicable(self, rules: list[Rule]) -> None:
        assert "i20-travel-signature-validity" in run(rules, on_opt=False).not_applicable


class TestReporting:
    def test_address_change(self, rules: list[Rule]) -> None:
        it = item(run(rules, address_change_date="2026-11-25"), "address-change-reporting")
        assert it.date == D("2026-12-05") and it.days_until == 8

    def test_employment_change_only_on_opt(self, rules: list[Rule]) -> None:
        it = item(run(rules, on_opt=True, employment_change_date="2027-08-01"),
                  "opt-employment-change-reporting")
        assert it.date == D("2027-08-11")
        tl = run(rules, on_opt=False, employment_change_date="2027-08-01")
        assert "opt-employment-change-reporting" in tl.not_applicable

    def test_no_event_no_nagging(self, rules: list[Rule]) -> None:
        tl = run(rules)
        asked = {n.rule_id for n in tl.needs_info}
        assert "address-change-reporting" not in asked
        assert "opt-employment-change-reporting" not in asked


class TestEntryAndEligibility:
    def test_initial_entry(self, rules: list[Rule]) -> None:
        it = item(run(rules, is_initial_student=True, program_start_date="2027-08-25"),
                  "initial-entry-window")
        assert it.date == D("2027-07-26") and it.kind == "earliest"

    def test_cpt_12_months_blocks_opt(self, rules: list[Rule]) -> None:
        tl = run(rules, full_time_cpt_months=12, completed_one_academic_year=True)
        assert "Twelve months" in item(tl, "practical-training-eligibility").message  # type: ignore[operator]

    def test_eleven_months_cpt_is_fine(self, rules: list[Rule]) -> None:
        tl = run(rules, full_time_cpt_months=11, completed_one_academic_year=True)
        assert "practical-training-eligibility" in tl.not_applicable


class TestForm8843:
    def test_no_income_june(self, rules: list[Rule]) -> None:
        assert item(run(rules, tax_year=2026, had_us_income=False), "form-8843-filing").date == D("2027-06-15")

    def test_income_april_rolled_off_weekend(self, rules: list[Rule]) -> None:
        # April 15, 2028 is a Saturday
        assert item(run(rules, tax_year=2027, had_us_income=True), "form-8843-filing").date == D("2028-04-17")

    def test_june_sunday_rolls(self, rules: list[Rule]) -> None:
        # June 15, 2031 is a Sunday
        assert item(run(rules, tax_year=2030, had_us_income=False), "form-8843-filing").date == D("2031-06-16")

    def test_no_tax_year_not_applicable(self, rules: list[Rule]) -> None:
        assert "form-8843-filing" in run(rules).not_applicable


class TestEngineInvariants:
    @pytest.mark.parametrize(
        ("on_opt", "on_stem_opt", "stem_degree", "had_us_income"),
        list(product([True, False, None], [True, False, None], [True, False], [True, False])),
    )
    def test_every_item_is_explained_and_sourced(
        self, rules: list[Rule], on_opt: bool | None, on_stem_opt: bool | None,
        stem_degree: bool, had_us_income: bool,
    ) -> None:
        facts = {
            "program_start_date": "2023-09-01", "program_end_date": "2027-05-15",
            "opt_ead_start_date": "2027-07-01", "opt_ead_end_date": "2028-06-30",
            "last_travel_signature_date": "2026-08-20", "address_change_date": "2026-11-20",
            "employment_change_date": "2027-08-01", "tax_year": 2026,
            "is_initial_student": False, "completed_one_academic_year": True,
            "full_time_cpt_months": 0, "stem_degree": stem_degree, "had_us_income": had_us_income,
        }
        if on_opt is not None:
            facts["on_opt"] = on_opt
        if on_stem_opt is not None:
            facts["on_stem_opt"] = on_stem_opt
        tl = run(rules, **facts)
        for it in tl.items:
            assert it.explanation, it.rule_id
            assert it.source_url.startswith("https://")
            if it.kind == "window":
                assert it.start is not None and it.end is not None
        # Every rule ends up in exactly one bucket (or produces items).
        produced = ids(tl)
        buckets = [produced, set(tl.not_applicable), {n.rule_id for n in tl.needs_info}]
        assert set().union(*buckets) == {r.id for r in rules}

    def test_deterministic(self, rules: list[Rule]) -> None:
        f = {"program_end_date": "2027-05-15", "on_opt": False, "tax_year": 2026, "had_us_income": False}
        assert run(rules, **f) == run(rules, **f)

    def test_items_sorted_by_date(self, rules: list[Rule]) -> None:
        tl = run(rules, program_end_date="2027-05-15", on_opt=False, tax_year=2026,
                 had_us_income=False, last_travel_signature_date="2026-08-20")
        dated = [i.date or i.start for i in tl.items if (i.date or i.start)]
        assert dated == sorted(dated)  # type: ignore[type-var]

    def test_stale_and_effective_dates(self, rules: list[Rule], tmp_path: Path) -> None:
        later = D("2027-12-01")  # > 180 days after last_verified
        tl = evaluate(rules, parse_facts({}), later, max_age_days=180)
        assert set(tl.stale_rules) == {r.id for r in rules}

        rule = yaml.safe_load((RULES_DIR / "address-change-reporting.yaml").read_text())
        rule["effective"] = {"from": None, "until": "2026-12-31"}
        (tmp_path / "address-change-reporting.yaml").write_text(yaml.safe_dump(rule))
        expired = load_rules(tmp_path)
        tl = evaluate(expired, parse_facts({"address_change_date": "2027-02-01"}), D("2027-02-05"))
        assert tl.not_in_effect == ["address-change-reporting"] and tl.items == []
