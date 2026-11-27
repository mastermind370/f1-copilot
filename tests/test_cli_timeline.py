from __future__ import annotations

import json
from pathlib import Path

import pytest

from copilot.cli import main

CONFIG = str(Path(__file__).resolve().parents[1] / "config.yaml")


def test_timeline_text(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--config", CONFIG, "timeline", "--as-of", "2026-11-27",
                 "--set", "program_end_date=2027-05-15", "--set", "on_opt=no"])
    out = capsys.readouterr().out
    assert code == 0
    assert "2027-02-14 -> 2027-07-14" in out
    assert "how: opens: program_end_date 2027-05-15 - 90 days = 2027-02-14" in out
    assert "not legal advice" in out


def test_timeline_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--config", CONFIG, "timeline", "--as-of", "2026-11-27", "--json",
                 "--set", "program_end_date=2027-05-15"])
    data = json.loads(capsys.readouterr().out)
    assert code == 0
    assert any(i["rule_id"] == "opt-post-completion-filing-window" for i in data["items"])


def test_timeline_rejects_bad_fact(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--config", CONFIG, "timeline", "--set", "program_end=2027-05-15"])
    assert code == 2
    assert "unknown fact" in capsys.readouterr().err


def test_rules_check(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--config", CONFIG, "rules", "check"]) == 0
    assert "rules valid" in capsys.readouterr().out
