"""Generate docs/rule-review.md, a one-page-per-rule checklist for a DSO to review.

Run: python scripts/rule_review_packet.py
It reads rules/*.yaml directly, so the packet always matches the code being reviewed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def describe_outputs(rule: dict) -> list[str]:
    lines = []
    for out in rule.get("outputs", []):
        label = out.get("label") or out.get("message") or out.get("kind")
        lines.append(f"- **{out['kind']}**: {label}")
    return lines


def main() -> int:
    rules = [yaml.safe_load(p.read_text()) for p in sorted((ROOT / "rules").glob("*.yaml"))]
    md = [
        "# F-1 Copilot: rules for DSO review",
        "",
        "F-1 Copilot computes personal deadlines with fixed rules instead of AI. Each rule below lists",
        "what it computes and the source it relies on. For each one, please mark whether it is correct",
        "**as general guidance** (not for any individual student), and note anything that is wrong,",
        "missing or school-specific. Corrections become new rule versions with your review date.",
        "",
        "Every page in the app tells students to confirm with their DSO before acting.",
        "",
        "| # | Rule | Source | Last verified |",
        "|---|------|--------|---------------|",
    ]
    for i, r in enumerate(rules, 1):
        src = r["source"]
        md.append(f"| {i} | {r['title']} (v{r['version']}) | [{src['verification']}]({src['url']}) | {src['last_verified']} |")
    for i, r in enumerate(rules, 1):
        md += ["", "---", "", f"## {i}. {r['title']}", "",
               f"`{r['id']}` · version {r['version']} · {r.get('category', '')}", "",
               " ".join(str(r.get("summary", "")).split()), "", "**What the app shows**", ""]
        md += describe_outputs(r)
        if r.get("notes"):
            md += ["", "**Caveats shown to students**", ""] + [f"- {n}" for n in r["notes"]]
        md += ["", f"**Source:** {r['source']['url']}", "",
               "**Review**", "",
               "- [ ] Correct as general guidance",
               "- [ ] Needs a change (describe below)",
               "- [ ] Differs at our school (describe below)", "",
               "Notes:", "", "&nbsp;", ""]
    md += ["---", "", "Reviewed by: ______________________  Office: ______________________  Date: __________", ""]
    out = ROOT / "docs" / "rule-review.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)} ({len(rules)} rules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
