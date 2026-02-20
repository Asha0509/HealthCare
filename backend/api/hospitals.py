"""Hospital recommendation API."""
import json
import httpx
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from schemas.models import HospitalRecommendation, Hospital, TriageLabel
from core.config import settings
from core.logging import app_logger

router = APIRouter(prefix="/api/hospitals", tags=["Hospitals"])

SPECIALIST_MAP = {
    "chest_pain": "Cardiologist",
    "shortness_of_breath": "Pulmonologist",
    "headache": "Neurologist",
    "joint_pain": "Rheumatologist / Orthopedist",
    "abdominal_pain": "Gastroenterologist",
    "skin_rash": "Dermatologist",
    "fever": "General Physician / Infectious Disease Specialist",
    "fatigue": "General Physician / Endocrinologist",
}


async def reverse_geocode(lat: float, lon: float) -> str:
    """Convert coordinates to city/area name using free Nominatim API."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat,
                    "lon": lon,
                    "format": "json",
                    "zoom": 10,  # City level
                },
                headers={"User-Agent": "HealthAI-Triage/1.0"}
            )
            resp.raise_for_status()
            data = resp.json()
            
            # Extract location info
            address = data.get("address", {})
            city = address.get("city") or address.get("town") or address.get("village") or address.get("suburb")
            state = address.get("state", "")
            country = address.get("country", "")
            
            if city:
                return f"{city}, {state}, {country}".strip(", ")
            return data.get("display_name", "").split(",")[0]
            
    except Exception as e:
        app_logger.warning(f"Reverse geocoding failed: {e}")
        return ""


async def get_hospitals_from_gemini(
    urgency: str,
    lat: Optional[float],
    lon: Optional[float],
    symptom: Optional[str]
) -> List[Hospital]:
    """Use Gemini to get hospital recommendations based on location."""
    
    # Get actual location name from coordinates
    location_name = ""
    if lat and lon:
        location_name = await reverse_geocode(lat, lon)
        app_logger.info(f"Resolved location: ({lat}, {lon}) -> {location_name}")
    
    if location_name:
        location_desc = f"in {location_name}"
    else:
        location_desc = "in Hyderabad, India"  # Default fallback
    
    care_type = {
        "Emergency": "emergency rooms and trauma centers",
        "Urgent": "urgent care clinics and specialist hospitals",
        "HomeCare": "nearby pharmacies, clinics, or telemedicine services"
    }.get(urgency, "clinics")
    
    symptom_context = f" for someone with {symptom.replace('_', ' ')}" if symptom else ""
    
    prompt = f"""You are a healthcare location assistant. Suggest 3 REAL hospitals/clinics {location_desc}{symptom_context}.

IMPORTANT: Only suggest hospitals that actually exist in {location_name or 'Hyderabad, India'}. Use your knowledge of real healthcare facilities.

Urgency level: {urgency}
Care type needed: {care_type}

Return a JSON array with exactly 3 hospitals. Each hospital should have:
- name: Real hospital name that exists in this city
- address: Actual address of this hospital
- distance_km: Estimated distance from city center (number)
- phone: Real phone number if known, or reasonable format
- type: "emergency", "specialist", or "clinic"
- maps_url: Google Maps search URL (https://maps.google.com/?q=Hospital+Name+City+encoded)

Return ONLY the JSON array, no other text."""

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.GEMINI_API_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}]}
            )
            resp.raise_for_status()
            result = resp.json()
            text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            # Parse JSON from response
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            
            hospitals_data = json.loads(text)
            hospitals = []
            for h in hospitals_data:
                hospitals.append(Hospital(
                    name=h.get("name", "Unknown Hospital"),
                    address=h.get("address", ""),
                    distance_km=float(h.get("distance_km", 0)),
                    phone=h.get("phone", ""),
                    type=h.get("type", "clinic"),
                    maps_url=h.get("maps_url", "https://maps.google.com")
                ))
            return hospitals
            
    except Exception as e:
        app_logger.warning(f"Gemini hospital lookup failed: {e}")
        return get_fallback_hospitals(urgency)


def get_fallback_hospitals(urgency: str) -> List[Hospital]:
    """Return fallback hospitals if Gemini fails."""
    fallback = {
        "Emergency": [
            Hospital(name="KIMS Hospital", address="Minister Road, Secunderabad, Hyderabad", distance_km=1.5,
                     phone="040-44885000", type="emergency",
                     maps_url="https://maps.google.com/?q=KIMS+Hospital+Hyderabad"),
            Hospital(name="Apollo Hospitals Jubilee Hills", address="Jubilee Hills, Hyderabad", distance_km=3.0,
                     phone="040-23607777", type="emergency",
                     maps_url="https://maps.google.com/?q=Apollo+Hospitals+Jubilee+Hills+Hyderabad"),
        ],
        "Urgent": [
            Hospital(name="Care Hospitals Banjara Hills", address="Banjara Hills, Hyderabad", distance_km=2.0,
                     phone="040-30418888", type="specialist",
                     maps_url="https://maps.google.com/?q=Care+Hospitals+Banjara+Hills+Hyderabad"),
        ],
        "HomeCare": [
            Hospital(name="MedPlus Pharmacy", address="Ameerpet, Hyderabad", distance_km=0.5,
                     phone="040-67006700", type="clinic",
                     maps_url="https://maps.google.com/?q=MedPlus+Ameerpet+Hyderabad"),
            Hospital(name="Practo Teleconsultation", address="Online", distance_km=0.0,
                     phone="1800-123-8080", type="clinic",
                     maps_url="https://practo.com"),
        ],
    }
    return fallback.get(urgency, fallback["HomeCare"])


@router.get("/nearby", response_model=HospitalRecommendation)
async def get_hospitals(
    urgency: TriageLabel,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    symptom: Optional[str] = None,
):
    """Get hospital recommendations based on urgency and location."""
    
    # Use Gemini to get location-aware hospitals
    hospitals = await get_hospitals_from_gemini(
        urgency.value, lat, lon, symptom
    )
    
    specialist = SPECIALIST_MAP.get(symptom, "General Physician") if symptom else None

    return HospitalRecommendation(
        urgency=urgency,
        hospitals=hospitals,
        recommended_specialist=specialist,
    )
