"""Deterministic rules engine that computes a student's personal F-1 timeline.

No LLM is involved anywhere in this package. Every date it produces comes from a
versioned YAML rule with a source URL, and it carries a step-by-step explanation.
"""

from copilot.timeline.engine import Timeline, TimelineItem, evaluate
from copilot.timeline.facts import FACT_TYPES, StudentFacts, parse_facts
from copilot.timeline.schema import Rule, RuleValidationError, load_rules

__all__ = [
    "FACT_TYPES",
    "Rule",
    "RuleValidationError",
    "StudentFacts",
    "Timeline",
    "TimelineItem",
    "evaluate",
    "load_rules",
    "parse_facts",
]
