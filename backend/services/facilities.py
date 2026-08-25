"""
Nearby care facilities from OpenStreetMap.

Replaces the old hardcoded / LLM-suggested hospital list (an LLM can invent
hospitals and phone numbers). Real places come from the Overpass API; a city
name can be geocoded with Nominatim. No API keys needed. Results are cached
for an hour per rounded location so we stay polite to the public servers.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from core.logging import app_logger

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "HealthAI-Triage/2.0 (portfolio demo)"}
CACHE_TTL = 3600

AMENITIES = {
    "Emergency": ["hospital"],
    "Urgent": ["hospital", "clinic", "doctors"],
    "HomeCare": ["pharmacy", "clinic", "doctors"],
}

_cache: Dict[Tuple, Tuple[float, Any]] = {}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_query(lat: float, lon: float, amenities: List[str], radius_m: int) -> str:
    pattern = "|".join(amenities)
    return (f'[out:json][timeout:15];nwr["amenity"~"^({pattern})$"](around:{radius_m},{lat},{lon});'
            "out center tags 60;")


def _address(tags: Dict[str, str]) -> str:
    parts = [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:suburb"),
             tags.get("addr:city") or tags.get("addr:district")]
    addr = ", ".join(p for p in parts if p)
    return addr or tags.get("addr:full", "")


def parse_elements(elements: List[Dict], lat: float, lon: float, urgency: str) -> List[Dict]:
    out = []
    seen = set()
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("name:en")
        if not name:
            continue
        plat = el.get("lat") or (el.get("center") or {}).get("lat")
        plon = el.get("lon") or (el.get("center") or {}).get("lon")
        if plat is None or plon is None:
            continue
        key = (name.lower(), round(plat, 3), round(plon, 3))
        if key in seen:
            continue
        seen.add(key)
        emergency = tags.get("emergency")
        out.append({
            "name": name,
            "kind": tags.get("amenity"),
            "lat": plat,
            "lon": plon,
            "distance_km": round(haversine_km(lat, lon, plat, plon), 2),
            "address": _address(tags),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "emergency_department": True if emergency == "yes" else (False if emergency == "no" else None),
            "osm_url": f"https://www.openstreetmap.org/{el.get('type', 'node')}/{el.get('id')}",
            "directions_url": f"https://www.google.com/maps/dir/?api=1&destination={plat},{plon}",
        })
    # For emergencies, hospitals known to have an emergency department come first.
    if urgency == "Emergency":
        out.sort(key=lambda f: (f["emergency_department"] is not True, f["distance_km"]))
    else:
        out.sort(key=lambda f: f["distance_km"])
    return out


async def _overpass(query: str) -> List[Dict]:
    last_error: Optional[Exception] = None
    async with httpx.AsyncClient(timeout=20.0, headers=HEADERS) as client:
        for url in OVERPASS_URLS:
            try:
                resp = await client.post(url, data={"data": query})
                resp.raise_for_status()
                return resp.json().get("elements", [])
            except Exception as exc:
                last_error = exc
                app_logger.warning(f"Overpass {url} failed: {exc}")
    raise RuntimeError(f"all Overpass servers failed: {last_error}")


async def geocode(query: str) -> Optional[Dict]:
    async with httpx.AsyncClient(timeout=10.0, headers=HEADERS) as client:
        resp = await client.get(NOMINATIM_URL, params={"q": query, "format": "json", "limit": 1})
        resp.raise_for_status()
        data = resp.json()
    if not data:
        return None
    return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"]), "label": data[0].get("display_name", query)}


async def nearby(lat: float, lon: float, urgency: str, limit: int = 6) -> Dict:
    amenities = AMENITIES.get(urgency, AMENITIES["Urgent"])
    key = (round(lat, 2), round(lon, 2), urgency)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    results: List[Dict] = []
    radius = 3000
    for radius in (3000, 8000, 20000):
        elements = await _overpass(build_query(lat, lon, amenities, radius))
        results = parse_elements(elements, lat, lon, urgency)
        if len(results) >= 3:
            break
    payload = {"facilities": results[:limit], "radius_km": radius / 1000, "amenities": amenities,
               "source": "OpenStreetMap contributors (Overpass API)"}
    _cache[key] = (time.time(), payload)
    return payload
