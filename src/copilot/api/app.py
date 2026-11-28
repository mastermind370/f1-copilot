"""FastAPI app: a thin HTTP shell over CopilotService.

Run with `copilot serve` (defaults to http://127.0.0.1:8000, local only).
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from copilot.api.service import BadRequest, CopilotService, NotReady
from copilot.config import AppConfig
from copilot.employers import EmployerDB, EmployersNotLoaded
from copilot.osm import OsmPlaces
from copilot.places import PlacesClient, PlacesError


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    school: str | None = Field(default=None, max_length=40)


class TimelineRequest(BaseModel):
    facts: dict[str, Any] = Field(default_factory=dict)
    as_of: str | None = None


def places_from_env(cfg: AppConfig) -> Any:
    """Free OpenStreetMap listings by default; Google Places only if a key is set."""
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if key:
        return PlacesClient(
            key,
            daily_searches=int(os.environ.get("PLACES_DAILY_SEARCHES", "30")),
            daily_photos=int(os.environ.get("PLACES_DAILY_PHOTOS", "60")),
        )
    return OsmPlaces(cfg.data_dir / "osm_cache.json")


def create_app(cfg: AppConfig, service: CopilotService | None = None,
               allowed_origins: list[str] | None = None, places: Any = None) -> FastAPI:
    svc = service or CopilotService(cfg)
    places_client = places or places_from_env(cfg)
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
        return _call(svc.ask, req.question, req.school)  # type: ignore[no-any-return]

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

    def _places(fn: Any, *args: Any) -> Any:
        try:
            return fn(*args)
        except PlacesError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.code) from exc

    @app.get("/api/places")
    def places(response: Response, category: str = Query(max_length=40), near: str = Query(max_length=80),
               lang: str = Query(default="en", max_length=8)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"  # Google's terms: don't cache place content
        results = _places(places_client.search, category, near, lang)
        return {"places": results, "attribution": places_client.attribution}

    @app.get("/api/places/photo")
    def place_photo(name: str = Query(max_length=300)) -> RedirectResponse:
        # Redirect to Google's short-lived image URL, which contains no API key.
        uri = _places(places_client.photo_uri, name)
        return RedirectResponse(uri, status_code=302, headers={"Cache-Control": "no-store"})

    employers = EmployerDB(cfg.data_dir / "employers.db")

    def _employers(fn: Any, *args: Any) -> Any:
        try:
            return fn(*args)
        except EmployersNotLoaded as exc:
            raise HTTPException(status_code=503, detail="employers_not_loaded") from exc

    @app.get("/api/employers/status")
    def employers_status() -> dict[str, Any]:
        return employers.status()

    @app.get("/api/employers/search")
    def employers_search(q: str = Query(min_length=1, max_length=80),
                         state: str = Query(default="", max_length=2)) -> dict[str, Any]:
        return {"results": _employers(employers.search, q, state)}

    @app.get("/api/employers/{key}")
    def employer_detail(key: str) -> dict[str, Any]:
        d = _employers(employers.detail, key[:120])
        if d is None:
            raise HTTPException(status_code=404, detail="employer_not_found")
        return d  # type: ignore[no-any-return]

    @app.get("/api/places/status")
    def places_status() -> dict[str, Any]:
        return places_client.status()

    return app
