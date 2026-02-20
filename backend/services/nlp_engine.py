"""
Medical NLP Engine
-----------------
Performs:
  1. Symptom extraction via Gemini API + keyword fallback
  2. Duration extraction (regex-based)
  3. Severity extraction (1-10 scale detection)
  4. Body part recognition
  5. Intent detection
  6. Self-harm / crisis phrase detection
  7. Language detection
"""

import re
import json
import os
import httpx
from typing import List, Dict, Optional, Tuple
from core.config import settings
from core.logging import app_logger

# ── Symptom synonym map (built from knowledge graph) ──
SYMPTOM_KEYWORDS: Dict[str, str] = {}

def _load_knowledge_graph() -> Dict:
    path = os.path.join(settings.DATA_DIR, "symptom_disease_graph.json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        app_logger.error(f"Failed to load knowledge graph: {e}")
        return {}

def _build_synonym_map(kg: Dict) -> Dict[str, str]:
    """Maps synonyms and the canonical key itself → canonical key."""
    mapping = {}
    for key, val in kg.items():
        mapping[key.replace("_", " ")] = key
        for syn in val.get("synonyms", []):
            mapping[syn.lower()] = key
    return mapping

# Lazy-loaded globals
_kg: Optional[Dict] = None
_synonym_map: Optional[Dict[str, str]] = None

def _get_kg() -> Dict:
    global _kg
    if _kg is None:
        _kg = _load_knowledge_graph()
    return _kg

def _get_synonym_map() -> Dict[str, str]:
    global _synonym_map
    if _synonym_map is None:
        _synonym_map = _build_synonym_map(_get_kg())
    return _synonym_map

def _get_valid_symptoms() -> List[str]:
    """Get list of valid symptom keys from knowledge graph."""
    return list(_get_kg().keys())


# ── Gemini API for symptom extraction ──
def extract_symptoms_gemini(text: str) -> List[str]:
    """Use Gemini API to extract symptoms from text."""
    if not settings.GEMINI_API_KEY:
        return []
    
    valid_symptoms = _get_valid_symptoms()
    prompt = f"""Extract medical symptoms from this text. Return ONLY a JSON array of symptom names.
Valid symptoms to look for: {', '.join(valid_symptoms)}

If the user mentions symptoms not in the list, map them to the closest valid symptom.
For example: "body pains" -> "body_pain", "stomach ache" -> "abdominal_pain", "throwing up" -> "nausea_vomiting"

Text: "{text}"

Return ONLY a JSON array like ["fever", "headache"]. No explanation."""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.GEMINI_API_KEY}"
        response = httpx.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200}
            },
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            result_text = data["candidates"][0]["content"]["parts"][0]["text"]
            # Parse JSON from response
            result_text = result_text.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            symptoms = json.loads(result_text.strip())
            # Validate against known symptoms
            valid = [s for s in symptoms if s in valid_symptoms]
            app_logger.info(f"Gemini extracted symptoms: {valid}")
            return valid
        else:
            app_logger.warning(f"Gemini API error: {response.status_code}")
            return []
    except Exception as e:
        app_logger.warning(f"Gemini extraction failed: {e}")
        return []


# ── Duration patterns ──
DURATION_PATTERNS = [
    (r"(\d+)\s*(?:day|days)", "days", 24),
    (r"(\d+)\s*(?:hour|hours|hr|hrs)", "hours", 1),
    (r"(\d+)\s*(?:week|weeks)", "weeks", 168),
    (r"(\d+)\s*(?:month|months)", "months", 720),
    (r"(\d+)\s*(?:minute|minutes|min|mins)", "minutes", 1/60),
]

# ── Severity patterns ──
SEVERITY_KEYWORDS = {
    "mild": 3, "slight": 2, "a bit": 3, "minor": 2,
    "moderate": 5, "medium": 5, "average": 5,
    "severe": 8, "bad": 7, "terrible": 9, "awful": 9,
    "unbearable": 10, "worst": 10, "excruciating": 10,
    "sharp": 7, "dull": 4, "throbbing": 6, "burning": 7,
}

# ── Intent patterns ──
EMERGENCY_PHRASES = [
    "can't breathe", "cannot breathe", "dying", "heart attack",
    "stroke", "unconscious", "not breathing", "no pulse",
    "severe chest pain", "crushing chest", "call ambulance",
]
CRISIS_PHRASES = [
    "want to die", "kill myself", "end my life", "suicidal",
    "self harm", "hurt myself", "no reason to live", "give up on life",
    "don't want to be here", "not worth living",
]

# ── Language detection (lightweight) ──
HINDI_CHARS = "अआइईउऊएऐओऔकखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह"


def detect_language(text: str) -> str:
    hindi_count = sum(1 for c in text if c in HINDI_CHARS)
    if hindi_count > 2:
        return "hi"
    return "en"


def extract_symptoms_keyword(text: str) -> List[str]:
    """Match symptom keywords and synonyms from text (fallback)."""
    text_lower = text.lower()
    found = []
    synonym_map = _get_synonym_map()
    for phrase, canonical in synonym_map.items():
        if phrase in text_lower and canonical not in found:
            found.append(canonical)
    return found


def extract_symptoms(text: str) -> List[str]:
    """Extract symptoms using Gemini API, fallback to keyword matching."""
    # Try Gemini first
    symptoms = extract_symptoms_gemini(text)
    if symptoms:
        return symptoms
    # Fallback to keyword matching
    return extract_symptoms_keyword(text)


def extract_duration(text: str) -> Tuple[Optional[str], Optional[float]]:
    """Return (human_text, hours)."""
    text_lower = text.lower()
    for pattern, unit, multiplier in DURATION_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            value = int(m.group(1))
            return f"{value} {unit}", value * multiplier
    return None, None


def extract_severity(text: str) -> Optional[int]:
    """Detect explicit 1-10 rating or keyword severity."""
    # Explicit number
    m = re.search(r"\b([1-9]|10)\s*(?:out of|\/)\s*10\b", text.lower())
    if m:
        return int(m.group(1))
    # Keyword
    text_lower = text.lower()
    max_score = None
    for keyword, score in SEVERITY_KEYWORDS.items():
        if keyword in text_lower:
            if max_score is None or score > max_score:
                max_score = score
    return max_score


def detect_intent(text: str) -> str:
    """Classify user intent: symptom_report | emergency_signal | crisis | query | greeting."""
    text_lower = text.lower()
    if any(phrase in text_lower for phrase in CRISIS_PHRASES):
        return "crisis"
    if any(phrase in text_lower for phrase in EMERGENCY_PHRASES):
        return "emergency_signal"
    if any(w in text_lower for w in ["hello", "hi", "hey", "good morning", "good evening", "howdy"]):
        return "greeting"
    if any(w in text_lower for w in ["what is", "how do", "explain", "tell me about", "what are"]):
        return "query"
    # If symptoms found → symptom_report
    if extract_symptoms(text):
        return "symptom_report"
    return "symptom_report"  # default


def process_text(
    text: str,
    patient_age: Optional[int] = None,
    patient_gender: Optional[str] = None,
) -> dict:
    """
    Main NLP pipeline. Returns structured extraction result.
    """
    language = detect_language(text)
    intent = detect_intent(text)
    symptoms = extract_symptoms(text)
    duration_text, duration_hours = extract_duration(text)
    severity = extract_severity(text)

    # Build entities list
    entities = []
    for s in symptoms:
        entities.append({"text": s.replace("_", " "), "label": "SYMPTOM", "normalized": s})
    if duration_text:
        entities.append({"text": duration_text, "label": "DURATION", "normalized": str(duration_hours)})
    if severity:
        entities.append({"text": str(severity), "label": "SEVERITY", "normalized": str(severity)})

    result = {
        "entities": entities,
        "symptoms": symptoms,
        "intent": intent,
        "language_detected": language,
        "severity_score": float(severity) if severity else None,
        "duration_text": duration_text,
        "duration_hours": duration_hours,
        "crisis_detected": intent == "crisis",
        "emergency_signal": intent == "emergency_signal",
    }

    app_logger.info(f"NLP: found {len(symptoms)} symptoms, intent={intent}, language={language}")
    return result
