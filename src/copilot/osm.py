"""Free restaurant and grocery listings from OpenStreetMap. No API key, no account, no cost.

How it stays within the public servers' usage policies:

* Nominatim (city -> coordinates): each city is geocoded once and cached on disk forever,
  requests are spaced at least 1 second apart, and every request carries a User-Agent
  that identifies this app.
* Overpass (places near a point): one query per city fetches every named restaurant, cafe
  and food shop within 6 km. It is cached on disk for 7 days and split into categories
  locally, so 19 campuses need at most about 19 queries a week, and a daily cap backs that
  up. OpenStreetMap data is ODbL-licensed: caching is allowed, and we show attribution.

OpenStreetMap is edited by volunteers, so coverage varies by town. It has names, addresses,
cuisines, diet tags, hours and websites, but no ratings or photos.
"""

from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from copilot.places import CATEGORIES, NEAR_RE, InvalidRequest, LimitReached, UpstreamError

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Public Overpass servers, tried in order. If one is busy (429/504) or times out, try the next.
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
log = logging.getLogger("copilot.osm")
USER_AGENT = "F1Copilot/0.5 (+https://github.com/mastermind370/f1-copilot)"
RADIUS_M = 6000
TTL_SECONDS = 7 * 24 * 3600
ATTRIBUTION = {"text": "© OpenStreetMap contributors", "url": "https://www.openstreetmap.org/copyright"}

FOOD = {"restaurant", "fast_food", "cafe", "food_court"}
SHOPS = {"supermarket", "convenience", "grocery", "deli", "butcher", "greengrocer", "food", "seafood", "spices"}

OVERPASS_QUERY = """[out:json][timeout:60];
(
  nwr["amenity"~"^({food})$"]["name"](around:{r},{lat},{lon});
  nwr["shop"~"^({shops})$"]["name"](around:{r},{lat},{lon});
);
out center tags;"""


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


def _diet(tags: dict[str, str], key: str) -> bool:
    return tags.get(f"diet:{key}", "").lower() in {"yes", "only"}


Rule = Callable[[dict[str, str]], bool]


def _food(cuisine: str = "", name: str = "") -> Rule:
    c, n = (_rx(cuisine) if cuisine else None), (_rx(name) if name else None)
    return lambda t: t.get("amenity") in FOOD and (
        bool(c and c.search(t.get("cuisine", ""))) or bool(n and n.search(t.get("name", ""))))


def _shop(cuisine: str = "", name: str = "", diet: str = "") -> Rule:
    c, n = (_rx(cuisine) if cuisine else None), (_rx(name) if name else None)
    return lambda t: t.get("shop") in SHOPS and (
        bool(c and c.search(t.get("cuisine", ""))) or bool(n and n.search(t.get("name", "")))
        or bool(diet and _diet(t, diet)))


# A closing time from 11 pm to 4:59 am, or open 24/7, counts as late night.
LATE_RE = re.compile(r"24/7|-\s*(2[3-4]|0[0-4]):\d\d")

RULES: dict[str, Rule] = {
    "dine.indian": _food(r"indian|pakistani|bangladeshi|sri_lankan|punjabi"),
    "dine.chinese": _food(r"chinese|cantonese|sichuan|szechuan|dim_sum|dumpling|taiwanese|hunan"),
    "dine.korean": _food(r"korean"),
    "dine.japanese": _food(r"japanese|sushi|ramen|izakaya|udon"),
    "dine.thai": _food(r"thai"),
    "dine.vietnamese": _food(r"vietnamese|pho"),
    "dine.hotpot": _food(r"hot_?pot|shabu", r"hot ?pot|shabu"),
    "dine.nepali": _food(r"nepal|himalayan|tibetan|momo", r"momo|himalayan|nepal"),
    "dine.mideast": _food(r"middle_eastern|lebanese|arab|syrian|persian|iranian|falafel|shawarma|afghan|israeli|mediterranean"),
    "dine.turkish": _food(r"turkish|kebab|doner"),
    "dine.ethiopian": _food(r"ethiopian|eritrean"),
    "dine.mexican": _food(r"mexican|tex-mex|taco|burrito"),
    "dine.cheap": lambda t: t.get("amenity") in {"fast_food", "food_court"},
    "dine.late": lambda t: t.get("amenity") in FOOD and bool(LATE_RE.search(t.get("opening_hours", ""))),
    "dine.veg": lambda t: t.get("amenity") in FOOD and (_diet(t, "vegetarian") or "vegetarian" in t.get("cuisine", "")),
    "dine.vegan": lambda t: t.get("amenity") in FOOD and (_diet(t, "vegan") or "vegan" in t.get("cuisine", "")),
    "dine.halal": lambda t: t.get("amenity") in FOOD and (
        _diet(t, "halal") or "halal" in t.get("cuisine", "") or "halal" in t.get("name", "").lower()),
    "groc.southasian": _shop(r"indian|pakistani|bangladeshi|nepal", r"india|desi|patel|apna|bazaa?r|spice|sabzi|subzi|masala"),
    "groc.chinese": _shop(r"chinese", r"chinese|china|99 ranch|hong kong|kam man|great wall"),
    "groc.korean": _shop(r"korean", r"h ?mart|korea|lotte|hanahreum"),
    "groc.japanese": _shop(r"japanese", r"japan|mitsuwa|nijiya|marukai|uwajimaya"),
    "groc.sea": _shop(r"thai|vietnam|filipino|indonesian|malaysian", r"thai|viet|saigon|filipino|manila|seafood city|island pacific"),
    "groc.asianmarket": _shop(r"asian", r"asia|oriental|h ?mart|99 ranch|great wall|patel|a-dong"),
    "groc.mideast": _shop(r"middle_eastern|arab|persian|lebanese|turkish", r"middle east|mediterranean|persian|arab|lebanese|turkish|kabul"),
    "groc.african": _shop(r"african|nigerian|ghanaian|ethiopian|caribbean", r"africa|caribbean|nigeria|ghana"),
    "groc.latin": _shop(r"mexican|latin", r"latin|mexic|hispan|tienda|supermercado|carnicer|bodega|el super|placita"),
    "groc.halal": _shop(name=r"halal", diet="halal"),
    "groc.kosher": _shop(name=r"kosher", diet="kosher"),
    "groc.international": lambda t: t.get("shop") in SHOPS and (
        bool(_rx(r"international|world|global|nations").search(t.get("name", ""))) or bool(t.get("cuisine"))),
}
assert set(RULES) == set(CATEGORIES), set(RULES) ^ set(CATEGORIES)

KIND_LABEL = {"restaurant": "Restaurant", "fast_food": "Fast food", "cafe": "Café", "food_court": "Food court",
              "supermarket": "Supermarket", "convenience": "Convenience store", "grocery": "Grocery",
              "deli": "Deli", "butcher": "Butcher", "greengrocer": "Greengrocer", "food": "Food shop",
              "seafood": "Seafood market", "spices": "Spice shop"}
DIETS = ("vegetarian", "vegan", "halal", "kosher", "gluten_free")


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def _pretty(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()


def normalize(el: dict[str, Any], center: tuple[float, float], near: str) -> dict[str, Any] | None:
    t: dict[str, str] = el.get("tags", {})
    lat = el.get("lat", (el.get("center") or {}).get("lat"))
    lon = el.get("lon", (el.get("center") or {}).get("lon"))
    if not t.get("name") or lat is None or lon is None:
        return None
    street = " ".join(x for x in (t.get("addr:housenumber", ""), t.get("addr:street", "")) if x)
    address = ", ".join(x for x in (street, t.get("addr:city", "")) if x)
    website = t.get("website") or t.get("contact:website") or ""
    if not website.startswith(("https://", "http://")):
        website = ""
    kind = t.get("amenity") or t.get("shop") or ""
    cuisines = [c.strip().lower() for c in t.get("cuisine", "").split(";") if c.strip()]
    query = f"{t['name']} {address or near}"
    return {
        "id": f"osm:{el.get('type', 'node')}/{el.get('id', '')}",
        "name": t["name"],
        "address": address,
        "rating": None, "ratingCount": None, "priceLevel": None, "summary": "", "openNow": None, "photo": None,
        "type": KIND_LABEL.get(kind, _pretty(kind)),
        "cuisine": [_pretty(c) for c in cuisines if c not in DIETS][:4],
        "diet": [d for d in DIETS if _diet(t, d) or d in cuisines],
        "hours": t.get("opening_hours", "")[:120],
        "website": website,
        "distanceKm": round(haversine_km(center, (float(lat), float(lon))), 2),
        "mapsUrl": f"https://www.google.com/maps/search/?api=1&query={quote(query)}",
        "osmUrl": f"https://www.openstreetmap.org/{el.get('type', 'node')}/{el.get('id', '')}",
    }


class OsmPlaces:
    """Same interface as PlacesClient (search / photo_uri / status), backed by OpenStreetMap."""

    attribution = ATTRIBUTION
    configured = True

    def __init__(self, cache_path: Path, *, daily_overpass: int = 40, max_results: int = 8,
                 transport: httpx.BaseTransport | None = None, clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.cache_path = cache_path
        self.max_results = max_results
        self.daily_overpass = daily_overpass
        self._clock, self._sleep = clock, sleep
        self._http = httpx.Client(timeout=httpx.Timeout(75.0, connect=10.0), transport=transport, headers={"User-Agent": USER_AGENT})
        self._lock = threading.Lock()
        self._last_nominatim = 0.0
        self._day, self._overpass_today = "", 0
        self._cache: dict[str, Any] = {"geocode": {}, "pois": {}}
        if cache_path.exists():
            try:
                self._cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._cache), encoding="utf-8")
        tmp.replace(self.cache_path)

    def _geocode(self, near: str) -> tuple[float, float]:
        hit = self._cache["geocode"].get(near)
        if hit:
            return float(hit[0]), float(hit[1])
        wait = 1.0 - (self._clock() - self._last_nominatim)  # at most 1 request per second
        if wait > 0:
            self._sleep(wait)
        self._last_nominatim = self._clock()
        try:
            r = self._http.get(NOMINATIM_URL, params={"q": near, "format": "jsonv2", "limit": 1, "countrycodes": "us"})
        except httpx.HTTPError as exc:
            log.warning("Nominatim request for %r failed: %r", near, exc)
            raise UpstreamError("Could not reach OpenStreetMap (Nominatim)") from exc
        if r.status_code != 200:
            log.warning("Nominatim returned HTTP %s for %r", r.status_code, near)
            raise UpstreamError(f"Nominatim returned {r.status_code}")
        if not r.json():
            log.warning("Nominatim found no match for %r", near)
            raise UpstreamError(f"Could not find {near!r} on OpenStreetMap")
        top = r.json()[0]
        center = (float(top["lat"]), float(top["lon"]))
        self._cache["geocode"][near] = list(center)
        self._save()
        return center

    def _pois(self, near: str, center: tuple[float, float]) -> list[dict[str, Any]]:
        hit = self._cache["pois"].get(near)
        if hit and self._clock() - hit["fetched"] < TTL_SECONDS:
            return list(hit["elements"])
        day = time.strftime("%Y-%m-%d", time.gmtime(self._clock()))
        if day != self._day:
            self._day, self._overpass_today = day, 0
        if self._overpass_today >= self.daily_overpass:
            if hit:  # stale but usable beats nothing
                return list(hit["elements"])
            raise LimitReached("Daily OpenStreetMap query limit reached")
        self._overpass_today += 1
        q = OVERPASS_QUERY.format(food="|".join(sorted(FOOD)), shops="|".join(sorted(SHOPS)),
                                  r=RADIUS_M, lat=center[0], lon=center[1])
        data: dict[str, Any] | None = None
        for url in OVERPASS_URLS:
            try:
                r = self._http.get(url, params={"data": q})
            except httpx.HTTPError as exc:
                log.warning("Overpass %s failed for %r: %r", url, near, exc)
                continue
            if r.status_code == 200:
                data = r.json()
                break
            log.warning("Overpass %s returned HTTP %s for %r", url, r.status_code, near)
        if data is None:
            if hit:
                return list(hit["elements"])
            raise UpstreamError("All Overpass servers failed; see the server log")
        keep = ("type", "id", "lat", "lon", "center", "tags")
        elements = [{k: e[k] for k in keep if k in e} for e in data.get("elements", [])]
        log.info("Fetched %d places near %r", len(elements), near)
        self._cache["pois"][near] = {"fetched": self._clock(), "elements": elements}
        self._save()
        return elements

    def search(self, category: str, near: str, lang: str = "en") -> list[dict[str, Any]]:
        if category not in RULES:
            raise InvalidRequest(f"Unknown category {category!r}")
        near = near.strip()
        if not NEAR_RE.match(near):
            raise InvalidRequest("Invalid location")
        with self._lock:  # one fetch per city at a time; also serializes Nominatim calls
            center = self._geocode(near)
            elements = self._pois(near, center)
        rule = RULES[category]
        # The same shop is often mapped twice (a point and a building outline): keep the
        # record with the most information, then sort by distance.
        best: dict[str, tuple[int, dict[str, Any]]] = {}
        for e in elements:
            tags = e.get("tags", {})
            if not rule(tags) or not (p := normalize(e, center, near)):
                continue
            key = p["name"].casefold()
            if key not in best or len(tags) > best[key][0]:
                best[key] = (len(tags), p)
        unique = sorted((p for _, p in best.values()), key=lambda p: p["distanceKm"])
        return unique[: self.max_results]

    def photo_uri(self, name: str, max_px: int = 400) -> str:
        raise InvalidRequest("OpenStreetMap listings have no photos")

    def status(self) -> dict[str, Any]:
        return {"provider": "openstreetmap", "cities": len(self._cache["pois"]),
                "overpassToday": self._overpass_today, "overpassLimit": self.daily_overpass}
