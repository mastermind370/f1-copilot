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
