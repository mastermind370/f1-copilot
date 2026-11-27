"""HTTP-level tests. Skipped automatically if FastAPI isn't installed."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from copilot.api.app import create_app  # noqa: E402
from copilot.api.service import CopilotService  # noqa: E402
from copilot.config import AppConfig  # noqa: E402

from .conftest import FakeEmbedder  # noqa: E402
from .test_api_service import cfg  # noqa: E402,F401  (fixture)


@pytest.fixture
def client(cfg: AppConfig) -> TestClient:  # noqa: F811
    svc = CopilotService(cfg, embedder_factory=FakeEmbedder, llm=None)
    return TestClient(create_app(cfg, svc))


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"]


def test_ask(client: TestClient) -> None:
    r = client.post("/api/ask", json={"question": "Do I need an I-20 travel signature?"})
    assert r.status_code == 200
    body = r.json()
    assert "citations" in body and "disclaimer" in body


def test_ask_validation(client: TestClient) -> None:
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
    assert client.post("/api/ask", json={}).status_code == 422
    assert client.post("/api/ask", json={"question": "   "}).status_code == 422


def test_timeline_no_store(client: TestClient) -> None:
    r = client.post("/api/timeline", json={"facts": {"program_end_date": "2027-05-15"}, "as_of": "2026-11-27"})
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    assert any(i["rule_id"] == "opt-post-completion-filing-window" for i in r.json()["items"])


def test_timeline_bad_fact(client: TestClient) -> None:
    r = client.post("/api/timeline", json={"facts": {"program_end": "2027-05-15"}})
    assert r.status_code == 422 and "unknown fact" in r.json()["detail"]


def test_metadata_endpoints(client: TestClient) -> None:
    assert len(client.get("/api/facts-schema").json()) >= 18
    assert len(client.get("/api/rules").json()) >= 10
    assert client.get("/api/changes").json() == {"report": None}


def test_cors_allows_local_ui_only(client: TestClient) -> None:
    ok = client.options("/api/ask", headers={"Origin": "http://localhost:3000",
                                             "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.options("/api/ask", headers={"Origin": "https://evil.example",
                                              "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers
