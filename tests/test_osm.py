"""OpenStreetMap listings: category rules, caching, polite rate limits. Network is mocked."""

import json

import pytest

httpx = pytest.importorskip("httpx")

from copilot.osm import LATE_RE, RULES, USER_AGENT, OsmPlaces, normalize  # noqa: E402
from copilot.places import CATEGORIES, InvalidRequest, LimitReached  # noqa: E402

CENTER = (40.5008, -74.4474)


def el(i, lat, lon, **tags):
    return {"type": "node", "id": i, "lat": lat, "lon": lon, "tags": tags}


ELEMENTS = [
    el(1, 40.4990, -74.4460, name="Curry Corner", amenity="restaurant", cuisine="indian;vegetarian",
       **{"diet:vegetarian": "yes", "addr:housenumber": "12", "addr:street": "Easton Avenue", "addr:city": "New Brunswick",
          "opening_hours": "Mo-Su 11:00-23:30", "website": "https://example.com"}),
    el(2, 40.5300, -74.4500, name="Far Tandoor", amenity="restaurant", cuisine="indian"),
    el(3, 40.5010, -74.4480, name="Patel Brothers", shop="supermarket"),
    el(4, 40.5020, -74.4490, name="Hot Pot Palace", amenity="restaurant", cuisine="chinese"),
    el(5, 40.5030, -74.4495, name="H Mart", shop="supermarket", cuisine="korean"),
    el(6, 40.5040, -74.4470, name="Burger Spot", amenity="fast_food", opening_hours="Mo-Su 10:00-02:00"),
    el(7, 40.5050, -74.4471, name="Halal Guys", amenity="fast_food", **{"diet:halal": "yes"}),
    {"type": "way", "id": 8, "center": {"lat": 40.5001, "lon": -74.4470}, "tags": {"name": "curry corner", "amenity": "restaurant", "cuisine": "indian"}},
    el(9, 40.5, -74.44, amenity="restaurant", cuisine="indian"),  # no name: skipped
]


class FakeNet:
    def __init__(self):
        self.calls = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        assert req.headers["User-Agent"] == USER_AGENT
        if "nominatim" in str(req.url):
            return httpx.Response(200, json=[{"lat": str(CENTER[0]), "lon": str(CENTER[1])}])
        return httpx.Response(200, json={"elements": ELEMENTS})


def make(tmp_path, net=None, clock=None, **kw):
    net = net or FakeNet()
    t = {"now": 1_800_000_000.0}
    sleeps = []
    osm = OsmPlaces(tmp_path / "osm.json", transport=httpx.MockTransport(net),
                    clock=clock or (lambda: t["now"]), sleep=sleeps.append, **kw)
    return osm, net, t, sleeps


def test_every_category_has_a_rule():
    assert set(RULES) == set(CATEGORIES)


def test_search_filters_sorts_dedupes_and_normalizes(tmp_path):
    osm, net, _, _ = make(tmp_path)
    out = osm.search("dine.indian", "New Brunswick, NJ")
    assert [p["name"] for p in out] == ["Curry Corner", "Far Tandoor"]  # nearest first, duplicate way dropped
    first = out[0]
    assert first["address"] == "12 Easton Avenue, New Brunswick"
    assert first["cuisine"] == ["Indian"] and first["diet"] == ["vegetarian"]  # no duplicate chip
    assert first["website"] == "https://example.com" and first["rating"] is None and first["photo"] is None
    assert first["mapsUrl"].startswith("https://www.google.com/maps/search/?api=1&query=Curry%20Corner")
    assert first["osmUrl"] == "https://www.openstreetmap.org/node/1"
    assert first["distanceKm"] < out[1]["distanceKm"]


@pytest.mark.parametrize("category,names", [
    ("groc.southasian", ["Patel Brothers"]),
    ("groc.korean", ["H Mart"]),
    ("dine.hotpot", ["Hot Pot Palace"]),
    ("dine.late", ["Curry Corner", "Burger Spot"]),
    ("dine.halal", ["Halal Guys"]),
    ("dine.veg", ["Curry Corner"]),
    ("dine.cheap", ["Burger Spot", "Halal Guys"]),
])
def test_category_rules(tmp_path, category, names):
    osm, _, _, _ = make(tmp_path)
    assert sorted(p["name"] for p in osm.search(category, "New Brunswick, NJ")) == sorted(names)


def test_late_night_regex():
    assert LATE_RE.search("Mo-Su 11:00-23:30") and LATE_RE.search("24/7") and LATE_RE.search("Fr-Sa 18:00-02:00")
    assert not LATE_RE.search("Mo-Fr 07:00-21:00") and not LATE_RE.search("Mo-Su 00:30-22:00")


def test_one_query_per_city_cached_on_disk(tmp_path):
    osm, net, t, _ = make(tmp_path)
    osm.search("dine.indian", "New Brunswick, NJ")
    osm.search("groc.korean", "New Brunswick, NJ")
    assert len(net.calls) == 2  # one geocode + one Overpass for the whole city
    again, net2, _, _ = make(tmp_path, clock=lambda: t["now"] + 3600)  # restart: disk cache reused
    again.search("dine.thai", "New Brunswick, NJ")
    assert net2.calls == []
    stale, net3, _, _ = make(tmp_path, clock=lambda: t["now"] + 8 * 86400)  # after 7 days: refresh places only
    stale.search("dine.thai", "New Brunswick, NJ")
    assert len(net3.calls) == 1 and "overpass" in str(net3.calls[0].url)
    assert "New Brunswick, NJ" in json.loads((tmp_path / "osm.json").read_text())["geocode"]


def test_nominatim_spacing_and_daily_cap(tmp_path):
    osm, net, t, sleeps = make(tmp_path, daily_overpass=1)
    osm.search("dine.indian", "New Brunswick, NJ")
    with pytest.raises(LimitReached):
        osm.search("dine.indian", "Ann Arbor, MI")  # second city on the same day exceeds the cap of 1
    assert sleeps and 0 < sleeps[0] <= 1.0  # second geocode waited to stay under 1 request/second


def test_rejects_bad_input(tmp_path):
    osm, _, _, _ = make(tmp_path)
    with pytest.raises(InvalidRequest):
        osm.search("dine.pizza", "New Brunswick, NJ")
    with pytest.raises(InvalidRequest):
        osm.search("dine.indian", "<script>")
    with pytest.raises(InvalidRequest):
        osm.photo_uri("places/x/photos/y")


def test_normalize_rejects_bad_websites():
    p = normalize(el(1, 40.5, -74.4, name="X", amenity="cafe", website="javascript:alert(1)"), CENTER, "Town")
    assert p is not None and p["website"] == ""


def test_falls_back_to_second_overpass_server(tmp_path):
    seen = []

    def net(req):
        seen.append(str(req.url))
        if "nominatim" in str(req.url):
            return httpx.Response(200, json=[{"lat": "40.5", "lon": "-74.45"}])
        if "overpass-api.de" in str(req.url):
            return httpx.Response(504, json={})
        return httpx.Response(200, json={"elements": ELEMENTS})

    osm, _, _, _ = make(tmp_path, net=net)
    assert osm.search("dine.indian", "New Brunswick, NJ")
    assert any("private.coffee" in u for u in seen)
