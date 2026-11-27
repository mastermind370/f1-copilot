"""The facts a student can provide. Every fact is optional.

Missing facts are never guessed. A rule that needs a missing fact reports "needs info"
instead of silently treating the fact as false or zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import date
from typing import Any


class FactError(ValueError):
    pass


@dataclass(frozen=True)
class StudentFacts:
    # Program
    degree_level: str | None = None  # associate | bachelor | master | doctorate | other
    program_start_date: date | None = None
    program_end_date: date | None = None  # from your I-20
    is_initial_student: bool | None = None  # first entry for this program
    completed_one_academic_year: bool | None = None
    full_time_cpt_months: int | None = None

    # OPT / STEM OPT
    on_opt: bool | None = None
    on_stem_opt: bool | None = None
    stem_degree: bool | None = None
    opt_ead_start_date: date | None = None
    opt_ead_end_date: date | None = None
    dso_recommendation_date: date | None = None  # OPT recommendation entered in SEVIS
    stem_dso_recommendation_date: date | None = None

    # Events
    last_travel_signature_date: date | None = None
    address_change_date: date | None = None
    employment_change_date: date | None = None

    # Taxes
    tax_year: int | None = None
    had_us_income: bool | None = None

    def get(self, name: str) -> Any:
        return getattr(self, name)


FACT_TYPES: dict[str, type] = {
    f.name: {"date": date, "bool": bool, "int": int, "str": str}[
        str(f.type).split("|")[0].strip()
    ]
    for f in fields(StudentFacts)
}

DEGREE_LEVELS = {"associate", "bachelor", "master", "doctorate", "other"}
_TRUE = {"true", "yes", "y", "1"}
_FALSE = {"false", "no", "n", "0"}


def _coerce(name: str, value: Any) -> Any:
    if value is None:
        return None
    expected = FACT_TYPES[name]
    if expected is date:
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise FactError(f"{name}: expected YYYY-MM-DD, got {value!r}") from exc
    if expected is bool:
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in _TRUE:
            return True
        if s in _FALSE:
            return False
        raise FactError(f"{name}: expected true/false, got {value!r}")
    if expected is int:
        if isinstance(value, bool):
            raise FactError(f"{name}: expected an integer, got {value!r}")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise FactError(f"{name}: expected an integer, got {value!r}") from exc
    s = str(value).strip()
    if name == "degree_level" and s.lower() not in DEGREE_LEVELS:
        raise FactError(f"degree_level must be one of {sorted(DEGREE_LEVELS)}, got {value!r}")
    return s.lower() if name == "degree_level" else s


def parse_facts(raw: Mapping[str, Any]) -> StudentFacts:
    """Validate and type-convert user input. Unknown keys are errors, which catches typos."""
    unknown = sorted(set(raw) - set(FACT_TYPES))
    if unknown:
        raise FactError(f"unknown fact(s): {', '.join(unknown)}. Known: {', '.join(FACT_TYPES)}")
    return StudentFacts(**{k: _coerce(k, v) for k, v in raw.items()})


# Labels and help text for UIs. The web form is generated from this, so a new fact only
# has to be added in one place.
FACT_HELP: dict[str, tuple[str, str]] = {
    "degree_level": ("Degree level", "The level of the program on your current I-20."),
    "program_start_date": ("Program start date", "From your I-20."),
    "program_end_date": ("Program end date", "From your I-20 (not necessarily your graduation ceremony)."),
    "is_initial_student": ("Starting a new program and entering the US for it?", ""),
    "completed_one_academic_year": ("Completed one full academic year of full-time study?", ""),
    "full_time_cpt_months": ("Months of full-time CPT used at this degree level", "Part-time CPT doesn't count."),
    "on_opt": ("Currently on post-completion OPT?", ""),
    "on_stem_opt": ("Currently on the STEM OPT extension?", ""),
    "stem_degree": ("Is your degree on the STEM-designated list?", "Ask your DSO if unsure."),
    "opt_ead_start_date": ("OPT EAD start date", "From your EAD card."),
    "opt_ead_end_date": ("OPT EAD end date", "From your EAD card."),
    "dso_recommendation_date": ("OPT recommendation date", "When your DSO entered the OPT recommendation in SEVIS (on your new I-20)."),
    "stem_dso_recommendation_date": ("STEM OPT recommendation date", "From your STEM OPT I-20."),
    "last_travel_signature_date": ("Date of your most recent travel signature", "Page 2 of your I-20."),
    "address_change_date": ("Date you moved (if you moved recently)", ""),
    "employment_change_date": ("Date your employment changed (if on OPT)", ""),
    "tax_year": ("Tax year", "The calendar year you were in the US, e.g. 2026."),
    "had_us_income": ("Did you have US income in that tax year?", "Wages, taxable scholarships, etc."),
}

assert set(FACT_HELP) == set(FACT_TYPES), "every fact needs UI help text"


def facts_schema() -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for name, t in FACT_TYPES.items():
        label, help_text = FACT_HELP[name]
        entry: dict[str, object] = {"name": name, "type": t.__name__, "label": label, "help": help_text}
        if name == "degree_level":
            entry["options"] = sorted(DEGREE_LEVELS)
        out.append(entry)
    return out
