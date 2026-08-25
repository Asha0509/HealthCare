import pytest
from services import facilities as f

ELEMENTS = [
    {"type": "node", "id": 1, "lat": 17.40, "lon": 78.40, "tags": {"amenity": "hospital", "name": "Far Hospital",
                                                                   "emergency": "yes"}},
    {"type": "way", "id": 2, "center": {"lat": 17.385, "lon": 78.487},
     "tags": {"amenity": "hospital", "name": "Near Hospital", "addr:street": "MG Road", "phone": "+91 40 1234"}},
    {"type": "node", "id": 3, "lat": 17.386, "lon": 78.486, "tags": {"amenity": "clinic"}},  # no name -> dropped
    {"type": "node", "id": 4, "lat": 17.385, "lon": 78.487, "tags": {"amenity": "hospital", "name": "Near Hospital"}},
]


def test_haversine():
    assert f.haversine_km(17.385, 78.4867, 17.385, 78.4867) == 0
    assert 500 < f.haversine_km(17.385, 78.4867, 13.0827, 80.2707) < 530  # Hyderabad -> Chennai, ~515 km


def test_parse_sorts_dedupes_and_drops_unnamed():
    out = f.parse_elements(ELEMENTS, 17.385, 78.4867, "Urgent")
    assert [x["name"] for x in out] == ["Near Hospital", "Far Hospital"]
    assert out[0]["address"] == "MG Road" and out[0]["phone"] == "+91 40 1234"
    assert out[0]["directions_url"].endswith("destination=17.385,78.487")


def test_emergency_prefers_emergency_departments():
    out = f.parse_elements(ELEMENTS, 17.385, 78.4867, "Emergency")
    assert out[0]["name"] == "Far Hospital" and out[0]["emergency_department"] is True


def test_query_uses_amenities_for_level():
    q = f.build_query(1.0, 2.0, f.AMENITIES["HomeCare"], 3000)
    assert "pharmacy" in q and "around:3000,1.0,2.0" in q


@pytest.mark.asyncio
async def test_nearby_widens_radius_and_caches(monkeypatch):
    calls = []

    async def fake_overpass(query):
        calls.append(query)
        return ELEMENTS[:2] if "around:3000" in query else [*ELEMENTS[:2],
            {"type": "node", "id": 9, "lat": 17.39, "lon": 78.49, "tags": {"amenity": "hospital", "name": "Third"}}]

    monkeypatch.setattr(f, "_overpass", fake_overpass)
    f._cache.clear()
    r1 = await f.nearby(17.385, 78.4867, "Urgent")
    assert len(calls) == 2 and r1["radius_km"] == 8 and len(r1["facilities"]) == 3
    r2 = await f.nearby(17.3851, 78.4868, "Urgent")
    assert len(calls) == 2 and r2 == r1
