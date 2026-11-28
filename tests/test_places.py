"""Places proxy: allowlist, budgets, normalization and HTTP mapping, with Google mocked."""

import json
import re
from pathlib import Path

import pytest

httpx = pytest.importorskip("httpx")

from copilot.places import (
    CATEGORIES, FIELD_MASK, InvalidRequest, LimitReached, NotConfigured, PlacesClient, normalize_place,
)

ROOT = Path(__file__).resolve().parents[1]

PLACE = {
    "id": "abc123",
    "displayName": {"text": "Curry Corner"},
    "formattedAddress": "1 Easton Ave, New Brunswick, NJ",
    "rating": 4.6,
    "userRatingCount": 812,
    "priceLevel": "PRICE_LEVEL_MODERATE",
    "primaryTypeDisplayName": {"text": "Indian Restaurant"},
    "editorialSummary": {"text": "Known for butter chicken and dosas."},
    "googleMapsUri": "https://maps.google.com/?cid=1",
    "currentOpeningHours": {"openNow": True},
    "photos": [{"name": "places/abc123/photos/PH0T0", "authorAttributions": [
        {"displayName": "A. Diner", "uri": "https://maps.google.com/contrib/1"}]}],
}


def client(handler, **kw):
    return PlacesClient("test-key", transport=httpx.MockTransport(handler), **kw)


def test_search_sends_allowlisted_query_and_field_mask():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        seen["headers"] = req.headers
        return httpx.Response(200, json={"places": [PLACE]})

    out = client(handler).search("dine.indian", "New Brunswick, NJ", "zh-CN")
    assert seen["body"]["textQuery"] == "Indian restaurant near New Brunswick, NJ"
    assert seen["body"]["languageCode"] == "zh-CN"
    assert seen["headers"]["X-Goog-FieldMask"] == FIELD_MASK
    assert seen["headers"]["X-Goog-Api-Key"] == "test-key"
    assert out[0]["name"] == "Curry Corner" and out[0]["priceLevel"] == 2
    assert out[0]["summary"].startswith("Known for") and out[0]["openNow"] is True
    assert out[0]["photo"]["attributions"] == [{"name": "A. Diner", "uri": "https://maps.google.com/contrib/1"}]


def test_rejects_unknown_category_bad_location_and_missing_key():
    c = client(lambda r: httpx.Response(200, json={}))
    with pytest.raises(InvalidRequest):
        c.search("anything goes", "New Brunswick, NJ")
    with pytest.raises(InvalidRequest):
        c.search("dine.indian", "<script>")
    with pytest.raises(InvalidRequest):
        c.photo_uri("../../v1/places:searchText")
    with pytest.raises(NotConfigured):
        PlacesClient(None).search("dine.indian", "New Brunswick, NJ")


def test_daily_budget_stops_spending():
    calls = []
    c = client(lambda r: calls.append(1) or httpx.Response(200, json={"places": []}), daily_searches=2)
    c.search("groc.korean", "Ann Arbor, MI")
    c.search("groc.korean", "Ann Arbor, MI")
    with pytest.raises(LimitReached):
        c.search("groc.korean", "Ann Arbor, MI")
    assert len(calls) == 2  # the third request never reached Google


def test_photo_uri_uses_json_response_without_exposing_key():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/places/abc123/photos/PH0T0/media"
        assert req.url.params["skipHttpRedirect"] == "true"
        return httpx.Response(200, json={"photoUri": "https://lh3.googleusercontent.com/p/x"})

    assert client(handler).photo_uri("places/abc123/photos/PH0T0") == "https://lh3.googleusercontent.com/p/x"


def test_normalize_handles_missing_fields():
    p = normalize_place({"id": "x", "displayName": {"text": "Shop"}})
    assert p["rating"] is None and p["photo"] is None and p["summary"] == "" and p["priceLevel"] is None


def test_web_categories_match_backend_allowlist():
    ids = set()
    for page in ["web/app/dining/page.tsx", "web/app/groceries/page.tsx"]:
        ids |= set(re.findall(r'key: "((?:dine|groc)\.[a-z]+)"', (ROOT / page).read_text()))
    ids.discard("dine.campus")
    assert ids == set(CATEGORIES), ids ^ set(CATEGORIES)


def test_http_endpoints_map_errors(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from copilot.api.app import create_app
    from copilot.config import load_config

    cfg = load_config(ROOT / "config.yaml")
    ok = client(lambda r: httpx.Response(200, json={"places": [PLACE]}) if "searchText" in r.url.path
                else httpx.Response(200, json={"photoUri": "https://lh3.googleusercontent.com/p/x"}), daily_searches=1)
    api = TestClient(create_app(cfg, service=object(), places=ok))  # type: ignore[arg-type]
    r = api.get("/api/places", params={"category": "dine.indian", "near": "New Brunswick, NJ"})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert r.json()["places"][0]["mapsUrl"].startswith("https://")
    assert api.get("/api/places", params={"category": "dine.indian", "near": "New Brunswick, NJ"}).json()["detail"] == "places_daily_limit"
    assert api.get("/api/places", params={"category": "nope", "near": "x y"}).status_code == 422
    photo = api.get("/api/places/photo", params={"name": "places/abc123/photos/PH0T0"}, follow_redirects=False)
    assert photo.status_code == 302 and photo.headers["location"].startswith("https://lh3.")
    off = TestClient(create_app(cfg, service=object(), places=PlacesClient(None)))  # type: ignore[arg-type]
    r = off.get("/api/places", params={"category": "dine.indian", "near": "New Brunswick, NJ"})
    assert r.status_code == 503 and r.json()["detail"] == "places_not_configured"
