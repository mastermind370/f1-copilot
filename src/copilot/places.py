"""Live restaurant and grocery listings from Google Places API (New).

The browser never sees the API key: the web app calls `/api/places` and `/api/places/photo`
on our server, which calls Google. Three rules keep this safe and cheap:

* Only allowlisted categories can be searched (`CATEGORIES`), so the key can't be used as a
  general-purpose search proxy.
* A daily budget (searches and photos counted separately) stops spending before it starts.
  The defaults stay under Google's free monthly usage for these SKUs.
* Nothing Google returns is stored. Google's terms only allow caching place IDs, so every
  dropdown open is a fresh request.
"""

from __future__ import annotations

import datetime as dt
import re
import threading
from dataclasses import dataclass, field
from typing import Any

import httpx

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PHOTO_URL = "https://places.googleapis.com/v1/{name}/media"

# Asking for editorialSummary ("what it's known for") puts each search in Google's
# Text Search Enterprise + Atmosphere SKU; the other fields are covered by it.
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.rating",
        "places.userRatingCount",
        "places.priceLevel",
        "places.primaryTypeDisplayName",
        "places.editorialSummary",
        "places.googleMapsUri",
        "places.photos",
        "places.currentOpeningHours.openNow",
    ]
)

# Category id (the web app's message key) -> English search phrase. English keeps Google's
# category matching reliable; results come back in the student's language.
CATEGORIES: dict[str, str] = {
    "dine.indian": "Indian restaurant",
    "dine.chinese": "Chinese restaurant",
    "dine.korean": "Korean restaurant",
    "dine.japanese": "Japanese restaurant",
    "dine.thai": "Thai restaurant",
    "dine.vietnamese": "Vietnamese pho restaurant",
    "dine.hotpot": "hot pot restaurant",
    "dine.nepali": "Nepali restaurant",
    "dine.mideast": "Middle Eastern restaurant",
    "dine.turkish": "Turkish restaurant",
    "dine.ethiopian": "Ethiopian restaurant",
    "dine.mexican": "Mexican restaurant",
    "dine.cheap": "cheap eats",
    "dine.late": "late night food",
    "dine.veg": "vegetarian restaurant",
    "dine.vegan": "vegan restaurant",
    "dine.halal": "halal restaurant",
    "groc.southasian": "Indian grocery store",
    "groc.chinese": "Chinese supermarket",
    "groc.korean": "Korean grocery store",
    "groc.japanese": "Japanese grocery store",
    "groc.sea": "Southeast Asian grocery store",
    "groc.asianmarket": "Asian supermarket",
    "groc.mideast": "Middle Eastern grocery store",
    "groc.african": "African grocery store",
    "groc.latin": "Latin American grocery store",
    "groc.halal": "halal meat market",
    "groc.kosher": "kosher grocery",
    "groc.international": "international grocery store",
}

PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

LANGUAGES = {"en", "zh-CN", "hi", "ko", "vi", "es", "bn"}
NEAR_RE = re.compile(r"^[\w .,'\-–]{2,80}$")
PHOTO_NAME_RE = re.compile(r"^places/[A-Za-z0-9_-]+/photos/[A-Za-z0-9_-]+$")


class PlacesError(Exception):
    """Base class; `code` is a stable string the web app translates."""

    code = "places_error"
    status = 502


class NotConfigured(PlacesError):
    code, status = "places_not_configured", 503


class LimitReached(PlacesError):
    code, status = "places_daily_limit", 429


class InvalidRequest(PlacesError):
    code, status = "places_invalid", 422


class UpstreamError(PlacesError):
    code, status = "places_upstream", 502


@dataclass
class DailyBudget:
    """Counts calls per UTC day. In-memory: a restart resets it, which errs on the side of
    a few extra free calls, never on unbounded spending, since the cap applies per process."""

    limit: int
    _day: dt.date | None = None
    _used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def take(self, today: dt.date) -> None:
        with self._lock:
            if self._day != today:
                self._day, self._used = today, 0
            if self._used >= self.limit:
                raise LimitReached("Daily limit for live listings reached")
            self._used += 1

    def used(self, today: dt.date) -> int:
        with self._lock:
            return self._used if self._day == today else 0


def _today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def normalize_place(p: dict[str, Any]) -> dict[str, Any]:
    photos = p.get("photos") or []
    photo = None
    if photos and PHOTO_NAME_RE.match(photos[0].get("name", "")):
        photo = {
            "name": photos[0]["name"],
            "attributions": [
                {"name": a.get("displayName", ""), "uri": a.get("uri", "")}
                for a in photos[0].get("authorAttributions", [])
                if a.get("displayName")
            ],
        }
    return {
        "id": p.get("id", ""),
        "name": (p.get("displayName") or {}).get("text", ""),
        "address": p.get("formattedAddress", ""),
        "rating": p.get("rating"),
        "ratingCount": p.get("userRatingCount"),
        "priceLevel": PRICE_LEVELS.get(p.get("priceLevel", "")),
        "type": (p.get("primaryTypeDisplayName") or {}).get("text", ""),
        "summary": (p.get("editorialSummary") or {}).get("text", ""),
        "mapsUrl": p.get("googleMapsUri", ""),
        "openNow": (p.get("currentOpeningHours") or {}).get("openNow"),
        "photo": photo,
    }


class PlacesClient:
    attribution = {"text": "Google Maps", "url": ""}

    def __init__(self, api_key: str | None, *, daily_searches: int = 30, daily_photos: int = 60,
                 max_results: int = 5, transport: httpx.BaseTransport | None = None) -> None:
        self.api_key = api_key or None
        self.max_results = max_results
        self.searches = DailyBudget(daily_searches)
        self.photos = DailyBudget(daily_photos)
        self._http = httpx.Client(timeout=10.0, transport=transport)

    @property
    def configured(self) -> bool:
        return self.api_key is not None

    def _require_key(self) -> str:
        if not self.api_key:
            raise NotConfigured("Set GOOGLE_PLACES_API_KEY to enable live listings")
        return self.api_key

    def search(self, category: str, near: str, lang: str = "en") -> list[dict[str, Any]]:
        if category not in CATEGORIES:
            raise InvalidRequest(f"Unknown category {category!r}")
        near = near.strip()
        if not NEAR_RE.match(near):
            raise InvalidRequest("Invalid location")
        if lang not in LANGUAGES:
            lang = "en"
        key = self._require_key()
        self.searches.take(_today())
        body = {
            "textQuery": f"{CATEGORIES[category]} near {near}",
            "languageCode": lang,
            "regionCode": "US",
            "pageSize": self.max_results,
        }
        headers = {"X-Goog-Api-Key": key, "X-Goog-FieldMask": FIELD_MASK}
        try:
            r = self._http.post(SEARCH_URL, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise UpstreamError("Could not reach Google Places") from exc
        if r.status_code != 200:
            raise UpstreamError(f"Google Places returned {r.status_code}")
        places = r.json().get("places", [])[: self.max_results]
        return [normalize_place(p) for p in places]

    def photo_uri(self, name: str, max_px: int = 400) -> str:
        if not PHOTO_NAME_RE.match(name):
            raise InvalidRequest("Invalid photo name")
        key = self._require_key()
        self.photos.take(_today())
        try:
            r = self._http.get(
                PHOTO_URL.format(name=name),
                params={"maxWidthPx": max_px, "maxHeightPx": max_px, "skipHttpRedirect": "true"},
                headers={"X-Goog-Api-Key": key},
            )
        except httpx.HTTPError as exc:
            raise UpstreamError("Could not reach Google Places") from exc
        if r.status_code != 200:
            raise UpstreamError(f"Google Places returned {r.status_code}")
        uri = r.json().get("photoUri", "")
        if not uri.startswith("https://"):
            raise UpstreamError("Unexpected photo response")
        return str(uri)

    def status(self) -> dict[str, Any]:
        today = _today()
        return {
            "configured": self.configured,
            "searchesToday": self.searches.used(today),
            "searchLimit": self.searches.limit,
            "photosToday": self.photos.used(today),
            "photoLimit": self.photos.limit,
        }
