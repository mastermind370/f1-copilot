"""FastAPI app: a thin HTTP shell over CopilotService.

Run with `copilot serve` (defaults to http://127.0.0.1:8000, local only).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from copilot.api.service import BadRequest, CopilotService, NotReady
from copilot.config import AppConfig


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class TimelineRequest(BaseModel):
    facts: dict[str, Any] = Field(default_factory=dict)
    as_of: str | None = None


def create_app(cfg: AppConfig, service: CopilotService | None = None,
               allowed_origins: list[str] | None = None) -> FastAPI:
    svc = service or CopilotService(cfg)
    app = FastAPI(title="F-1 Compliance Copilot", version="0.4.0",
                  description="Information tool, not legal advice.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or ["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def _call(fn: Any, *args: Any) -> Any:
        try:
            return fn(*args)
        except BadRequest as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except NotReady as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return svc.health()  # type: ignore[no-any-return]

    @app.post("/api/ask")
    def ask(req: AskRequest) -> dict[str, Any]:
        return _call(svc.ask, req.question)  # type: ignore[no-any-return]

    @app.post("/api/timeline")
    def timeline(req: TimelineRequest, response: Response) -> dict[str, Any]:
        # Personal data: tell browsers and proxies never to store this response.
        response.headers["Cache-Control"] = "no-store"
        return _call(svc.timeline, req.facts, req.as_of)  # type: ignore[no-any-return]

    @app.get("/api/facts-schema")
    def schema() -> list[dict[str, Any]]:
        return svc.facts_schema()

    @app.get("/api/rules")
    def rules() -> list[dict[str, Any]]:
        return svc.rules()

    @app.get("/api/changes")
    def changes() -> dict[str, Any]:
        return svc.changes()

    return app
