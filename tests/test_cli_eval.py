from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from copilot import cli
from copilot.evaluation.dataset import write_snapshot
from copilot.models import Chunk

from .conftest import FakeEmbedder

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup(tmp_path: Path, corpus: list[Chunk], monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setattr(cli, "_embedder", lambda cfg: FakeEmbedder())
    raw = yaml.safe_load((REPO / "config.yaml").read_text())
    raw["data_dir"] = str(tmp_path / "data")
    raw["rules"]["dir"] = str(REPO / "rules")
    raw["retrieval"]["min_confidence"] = 0.3
    raw["evaluation"]["results_dir"] = str(tmp_path / "results")
    gates = tmp_path / "gates.yaml"
    gates.write_text(yaml.safe_dump({"min": {"retrieval.overall.recall@5": 0.5}}))
    raw["evaluation"]["thresholds"] = str(gates)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(raw))

    snap = tmp_path / "chunks.jsonl"
    write_snapshot(corpus, snap)
    data = tmp_path / "d.jsonl"
    data.write_text("\n".join(json.dumps(r) for r in [
        {"id": "en-1", "language": "en", "question": "OPT employment authorization Form I-765",
         "should_refuse": False, "gold": [{"phrases": ["I-765"]}]},
        {"id": "en-r", "language": "en", "question": "chocolate cake recipe",
         "should_refuse": True, "gold": []},
    ]) + "\n")
    return {"cfg": cfg, "snap": snap, "data": data, "gates": gates, "tmp": tmp_path}


def _run(setup: dict[str, Path], *extra: str) -> int:
    return cli.main(["--config", str(setup["cfg"]), "eval", "run", "--corpus", str(setup["snap"]),
                     "--dataset", str(setup["data"]), *extra])


def test_eval_run_writes_results_and_passes_gates(setup: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(setup, "--check", str(setup["gates"])) == 0
    out = capsys.readouterr().out
    assert "All quality gates passed" in out
    data = json.loads((setup["tmp"] / "results" / "latest.json").read_text())
    assert data["summary"]["retrieval"]["overall"]["recall@1"] == 1.0
    assert (setup["tmp"] / "results" / "latest.md").exists()


def test_eval_gate_failure_exits_1(setup: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    setup["gates"].write_text(yaml.safe_dump({"min": {"retrieval.overall.recall@5": 1.01}}))
    assert _run(setup, "--check", str(setup["gates"])) == 1
    assert "QUALITY GATE FAILED" in capsys.readouterr().out


def test_update_thresholds(setup: dict[str, Path]) -> None:
    assert _run(setup, "--update-thresholds") == 0
    gates = yaml.safe_load(setup["gates"].read_text())
    assert gates["min"]["retrieval.overall.recall@5"] == 0.95


def test_answers_mode(setup: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(setup, "--answers") == 0
    assert "End-to-end answers" in capsys.readouterr().out


def test_resolve(setup: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["--config", str(setup["cfg"]), "eval", "resolve", "--corpus", str(setup["snap"]),
                     "--dataset", str(setup["data"])])
    assert code == 0
    assert "en-1" in capsys.readouterr().out


def test_sample_drafts(setup: dict[str, Path]) -> None:
    out = setup["tmp"] / "drafts.jsonl"
    code = cli.main(["--config", str(setup["cfg"]), "eval", "sample", "--corpus", str(setup["snap"]),
                     "--dataset", str(setup["data"]), "--n", "2", "--out", str(out)])
    assert code == 0
    # fixture chunks are short (< 25 words), so nothing qualifies, but the file is still written
    assert out.exists()
