"""Nearby care facilities (OpenStreetMap) for a triage level."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from schemas.models import TriageLabel
from services import facilities

router = APIRouter(prefix="/api/facilities", tags=["Facilities"])


@router.get("/nearby")
async def nearby(
    urgency: TriageLabel,
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    place: Optional[str] = Query(None, min_length=2, max_length=120, description="City or area, if no coordinates"),
):
    """Real hospitals/clinics/pharmacies near a point or a named place, nearest first."""
    label = None
    if lat is None or lon is None:
        if not place:
            raise HTTPException(status_code=422, detail="Share your location or type a city or area.")
        try:
            loc = await facilities.geocode(place)
        except Exception:
            raise HTTPException(status_code=502, detail="Couldn't look up that place right now. Please try again.")
        if not loc:
            raise HTTPException(status_code=404, detail=f"Couldn't find '{place}'. Try a city or area name.")
        lat, lon, label = loc["lat"], loc["lon"], loc["label"]
    try:
        data = await facilities.nearby(lat, lon, urgency.value)
    except Exception:
        raise HTTPException(status_code=502, detail="The map service didn't respond. Please try again shortly.")
    return {"urgency": urgency.value, "center": {"lat": lat, "lon": lon, "label": label}, **data}
