"""Every school-tagged source must match a school the web app knows, and stay on its own site."""

import re
from pathlib import Path

from copilot.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_school_sources_match_web_school_ids() -> None:
    cfg = load_config(ROOT / "config.yaml")
    web_ids = set(re.findall(r'id: "([a-z-]+)"', (ROOT / "web/lib/schools.ts").read_text()))
    tagged = {s.school for s in cfg.sources if s.school}
    assert tagged <= web_ids, tagged - web_ids
    assert tagged == web_ids, f"schools without an office source: {web_ids - tagged}"


def test_school_sources_stay_on_https_and_inside_prefixes() -> None:
    cfg = load_config(ROOT / "config.yaml")
    for s in cfg.sources:
        assert s.allowed_prefixes, s.name
        for seed in s.seeds:
            assert seed.startswith("https://"), seed
            assert any(seed.startswith(p) for p in s.allowed_prefixes), (s.name, seed)
    names = [s.name for s in cfg.sources]
    assert len(names) == len(set(names))
