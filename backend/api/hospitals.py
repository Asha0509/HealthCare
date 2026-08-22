"""Hospital recommendation API."""
import json
import httpx
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from schemas.models import HospitalRecommendation, Hospital, TriageLabel
from core.config import settings
from core.logging import app_logger
from services.llm_client import generate_json_with_fallback

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
    """Use LLM (Gemini primary, NIM fallback) for location-aware hospital recommendations."""
    
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
Clinical focus: prioritize facilities that are most suitable for the urgency and symptom profile.

Return a JSON array with exactly 3 hospitals. Each hospital should have:
- name: Real hospital name that exists in this city
- address: Actual address of this hospital
- distance_km: Estimated distance from city center (number)
- phone: Real phone number if known, or reasonable format
- type: "emergency", "specialist", or "clinic"
- maps_url: Google Maps search URL (https://maps.google.com/?q=Hospital+Name+City+encoded)

Return ONLY the JSON array, no other text."""

    try:
        hospitals_data, provider = generate_json_with_fallback(
            prompt=prompt,
            default=[],
            temperature=0.2,
            max_tokens=900,
        )
        if not isinstance(hospitals_data, list) or not hospitals_data:
            return get_fallback_hospitals(urgency)

        hospitals = []
        for h in hospitals_data[:3]:
            hospitals.append(Hospital(
                name=h.get("name", "Unknown Hospital"),
                address=h.get("address", ""),
                distance_km=float(h.get("distance_km", 0) or 0),
                phone=h.get("phone", ""),
                type=h.get("type", "clinic"),
                maps_url=h.get("maps_url", "https://maps.google.com")
            ))
        app_logger.info(f"Hospital recommendations generated via {provider or 'llm'}")
        return hospitals
    except Exception as e:
        app_logger.warning(f"LLM hospital lookup failed: {e}")
        return get_fallback_hospitals(urgency)


def get_fallback_hospitals(urgency: str) -> List[Hospital]:
    """Return fallback hospitals if Gemini fails."""
    fallback = {
        "Emergency": [
            Hospital(name="LandMark Hospitals", address="Nizampet, Hyderabad", distance_km=1.5,
                     phone="040-44885000", type="emergency",
                     maps_url="https://www.google.com/maps?sca_esv=a7c356437a2f7860&output=search&q=landmark+hospital&source=lnms&fbs=ADc_l-aN0CWEZBOHjofHoaMMDiKpaEWjvZ2Py1XXV8d8KvlI3kj_s5Jds98_ubVRf0unUVuttyzNArKNIU5GZzx4Y5djOSi5iUTuvdmR-KzdLKnPc8J97gJtmVeaOWsKOxlqo4TcVZ7ft1dMtClAqeNC9y2mJ8P_pAdCMwFy46j5j2tvTqUS2_V68iNK_vv2E5tQyCDxasV3OS5zCGOxACnsQOGmKPQxbA&entry=mc&ved=1t:200715&ictx=111"),
            Hospital(name="Nexgen Hospital", address="Bachupally, Hyderabad", distance_km=3.0,
                     phone="040-23607777", type="emergency",
                     maps_url="https://www.google.com/maps/place/NextGen+Hospitals/@17.4892069,78.3776512,15z/data=!3m1!4b1!4m6!3m5!1s0x3bcb916e5cb65dfb:0x8a5b7a7934adf5a9!8m2!3d17.4891873!4d78.3961053!16s%2Fg%2F11spvwvkb9?entry=ttu&g_ep=EgoyMDI2MDMyNC4wIKXMDSoASAFQAw%3D%3D"),
        ],
        "Urgent": [
            Hospital(name="Sri Sri Holistic Hospitals", address="Nizampet, Hyderabad", distance_km=2.0,
                     phone="040-30418888", type="specialist",
                     maps_url="https://www.google.com/maps/place/Sri+Sri+Holistic%C2%AE%EF%B8%8F+Hospitals/@17.5022314,78.3863263,17z/data=!3m1!4b1!4m6!3m5!1s0x3bcb9a090b3018fd:0x7a60b593fe53fde9!8m2!3d17.5022263!4d78.3889012!16s%2Fg%2F11x9gsqf3?entry=ttu&g_ep=EgoyMDI2MDMyNC4wIKXMDSoASAFQAw%3D%3D"),
        ],
        "HomeCare": [
            Hospital(name="MedPlus Pharmacy", address="Bachupally, Hyderabad", distance_km=0.5,
                     phone="040-67006700", type="clinic",
                     maps_url="https://www.google.com/maps/dir//G%2F1,+Plot+No+84,+MedPlus+Bachupally+Pharmacy+%26+Lab,+Hill+Side,+Rangareddy,+Sy+No+272+To+275+%26+277,+Medchal+Malkajgiri,+Bachupally,+Hyderabad,+Telangana+500118/data=!4m6!4m5!1m1!4e2!1m2!1m1!1s0x3bcb8dee2b938045:0x65ebdaaf778c3048?sa=X&ved=1t:57443&ictx=111"),
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
