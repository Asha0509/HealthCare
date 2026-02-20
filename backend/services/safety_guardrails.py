"""
Safety Guardrails Engine
------------------------
Uses Gemini API for intelligent crisis and emergency detection.
Only intervenes for true emergencies (self-harm, life-threatening conditions).
"""

import json
import httpx
from typing import List, Dict, Optional, Tuple
from core.config import settings
from core.logging import app_logger

CRISIS_HOTLINES = {
    "en": {
        "message": "I'm very concerned about what you've shared. You are not alone and help is available right now.",
        "resources": [
            {"name": "iCall (India)", "number": "9152987821", "available": "Mon-Sat 8am-10pm"},
            {"name": "Vandrevala Foundation", "number": "1860-2662-345", "available": "24/7"},
            {"name": "AASRA", "number": "9820466627", "available": "24/7"},
        ],
    },
    "hi": {
        "message": "आपकी बात सुनकर मैं बहुत चिंतित हूं। आप अकेले नहीं हैं, मदद उपलब्ध है।",
        "resources": [
            {"name": "iCall", "number": "9152987821", "available": "सोम-शनि सुबह 8 बजे से रात 10 बजे"},
            {"name": "Vandrevala Foundation", "number": "1860-2662-345", "available": "24/7"},
        ],
    },
}


def check_crisis_gemini(text: str, intent: str, symptoms: List[str]) -> Optional[Dict]:
    """Use Gemini to intelligently detect crisis situations."""
    if not settings.GEMINI_API_KEY:
        # Fallback to keyword detection
        crisis_keywords = ["suicide", "kill myself", "want to die", "end my life", "self harm"]
        text_lower = text.lower()
        if any(kw in text_lower for kw in crisis_keywords) or intent == "crisis":
            return {"is_crisis": True, "reason": "Crisis indicators detected"}
        return None
    
    prompt = f"""Analyze this text for mental health crisis indicators.

Text: "{text}"
Detected intent: {intent}
Symptoms mentioned: {', '.join(symptoms) if symptoms else 'none'}

Is this person expressing:
1. Suicidal thoughts or intentions
2. Self-harm ideation
3. Immediate danger to themselves

Respond ONLY with JSON:
{{"is_crisis": true/false, "reason": "brief explanation if crisis detected"}}

Be careful not to over-flag. Only return is_crisis=true for genuine self-harm or suicidal expressions.
Medical symptoms (even severe ones) should NOT be flagged as crisis - that's handled separately."""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.GEMINI_API_KEY}"
        response = httpx.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100}
            },
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            result_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            
            result = json.loads(result_text.strip())
            if result.get("is_crisis"):
                return result
        return None
    except Exception as e:
        app_logger.warning(f"Crisis check failed: {e}")
        return None


def apply_guardrails(
    symptoms: List[str],
    intent: str,
    severity: Optional[float] = None,
    age: Optional[int] = None,
    temperature: Optional[float] = None,
    answers: Optional[Dict] = None,
    language: str = "en",
    chief_complaint: str = "",
) -> Tuple[Optional[Dict], str]:
    """
    Check for crisis situations only.
    Medical triage is handled by the classifier, not guardrails.
    """
    # Only check for mental health crisis - let the classifier handle medical triage
    crisis = check_crisis_gemini(chief_complaint, intent, symptoms)
    
    if crisis and crisis.get("is_crisis"):
        lang = language if language in CRISIS_HOTLINES else "en"
        return {
            "is_crisis": True,
            "triage_label": "Emergency",
            "confidence": 1.0,
            "reason": crisis.get("reason", "Crisis situation detected"),
            "crisis_info": CRISIS_HOTLINES[lang],
            "action": "Please reach out to a crisis helpline immediately. You are not alone.",
        }, "crisis_detected"

    # No guardrail override - let normal triage flow proceed
    return None, "none"
