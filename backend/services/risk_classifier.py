"""
Risk Classifier + Explainability Module
----------------------------------------
- Gemini API-based intelligent triage (Emergency / Urgent / HomeCare)
- Context-aware analysis of symptoms, answers, and patient info
- Falls back to simple heuristics if API unavailable
"""

import json
import httpx
from typing import List, Dict, Optional
from core.config import settings
from core.logging import app_logger

LABELS = ["HomeCare", "Urgent", "Emergency"]


def classify_triage_gemini(
    symptoms: List[str],
    severity: Optional[float],
    duration_hours: Optional[float],
    age: Optional[int],
    gender: Optional[str],
    comorbidities: List[str],
    answers: Dict[str, str],
    chief_complaint: str = "",
) -> Optional[Dict]:
    """Use Gemini API for intelligent triage classification."""
    if not settings.GEMINI_API_KEY:
        return None
    
    # Build context for Gemini
    symptom_text = ", ".join(s.replace("_", " ") for s in symptoms)
    
    answers_text = ""
    if answers:
        answers_text = "\n".join(f"- {k}: {v}" for k, v in answers.items())
    
    patient_info = []
    if age:
        patient_info.append(f"Age: {age}")
    if gender:
        patient_info.append(f"Gender: {gender}")
    if comorbidities:
        patient_info.append(f"Pre-existing conditions: {', '.join(comorbidities)}")
    if severity:
        patient_info.append(f"Pain/severity rating: {severity}/10")
    if duration_hours:
        if duration_hours < 24:
            patient_info.append(f"Duration: {int(duration_hours)} hours")
        else:
            patient_info.append(f"Duration: {int(duration_hours/24)} days")
    
    prompt = f"""You are a medical triage AI assistant. Analyze the following patient information and provide a triage recommendation.

Chief Complaint: {chief_complaint or 'Not specified'}

Symptoms identified: {symptom_text or 'None identified'}

Patient Information:
{chr(10).join(patient_info) if patient_info else 'Not provided'}

Follow-up Q&A:
{answers_text if answers_text else 'No follow-up questions answered yet'}

Based on this information, provide a triage classification. You must respond in this exact JSON format:
{{
    "triage_label": "HomeCare" or "Urgent" or "Emergency",
    "confidence": 0.0 to 1.0,
    "probabilities": {{"HomeCare": 0.0-1.0, "Urgent": 0.0-1.0, "Emergency": 0.0-1.0}},
    "explanation": "2-3 sentence explanation of your reasoning",
    "recommended_action": "Specific action the patient should take",
    "key_factors": ["factor1", "factor2", "factor3"]
}}

Classification guidelines:
- HomeCare: Minor symptoms, can be managed with rest/OTC medication, no red flags
- Urgent: Needs medical attention within 24 hours, but not immediately life-threatening
- Emergency: Potentially life-threatening, needs immediate medical attention

Be conservative but not alarmist. Most common symptoms without severe indicators should be HomeCare.
Consider that many patients report symptoms that resolve on their own.
Only recommend Emergency for truly concerning presentations with multiple warning signs.

Respond ONLY with the JSON object, no additional text."""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.GEMINI_API_KEY}"
        response = httpx.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 500}
            },
            timeout=15.0
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
            
            result = json.loads(result_text.strip())
            
            # Validate and normalize response
            label = result.get("triage_label", "HomeCare")
            if label not in LABELS:
                label = "HomeCare"
            
            app_logger.info(f"Gemini triage: {label} with confidence {result.get('confidence', 0.7)}")
            
            return {
                "triage_label": label,
                "confidence": float(result.get("confidence", 0.7)),
                "probabilities": result.get("probabilities", {"HomeCare": 0.7, "Urgent": 0.2, "Emergency": 0.1}),
                "explanation_text": result.get("explanation", ""),
                "recommended_action": result.get("recommended_action", ""),
                "shap_features": [{"feature": f, "human_label": f} for f in result.get("key_factors", [])],
                "model_used": "gemini",
            }
        else:
            app_logger.warning(f"Gemini API error: {response.status_code}")
            return None
    except Exception as e:
        app_logger.warning(f"Gemini triage failed: {e}")
        return None


def _simple_heuristic_classify(
    symptoms: List[str],
    severity: Optional[float],
    duration_hours: Optional[float],
) -> Dict:
    """Simple fallback when Gemini API is unavailable."""
    
    # Simple scoring
    score = 0
    reasons = []
    
    high_risk_symptoms = {"chest_pain", "shortness_of_breath", "bleeding", "palpitations"}
    medium_risk_symptoms = {"fever", "headache", "abdominal_pain", "dizziness"}
    
    for s in symptoms:
        if s in high_risk_symptoms:
            score += 2
            reasons.append(f"{s.replace('_', ' ')} present")
        elif s in medium_risk_symptoms:
            score += 1
    
    if severity and severity >= 8:
        score += 2
        reasons.append(f"high severity ({severity}/10)")
    elif severity and severity >= 5:
        score += 1
    
    if duration_hours and duration_hours > 168:  # > 1 week
        score += 1
        reasons.append("prolonged duration")
    
    if score >= 5:
        label = "Emergency"
        probs = {"HomeCare": 0.1, "Urgent": 0.2, "Emergency": 0.7}
        conf = 0.7
    elif score >= 2:
        label = "Urgent"
        probs = {"HomeCare": 0.2, "Urgent": 0.6, "Emergency": 0.2}
        conf = 0.6
    else:
        label = "HomeCare"
        probs = {"HomeCare": 0.7, "Urgent": 0.25, "Emergency": 0.05}
        conf = 0.7
    
    symptom_text = ", ".join(s.replace("_", " ") for s in symptoms[:3]) or "reported symptoms"
    
    if label == "Emergency":
        explanation = f"Based on {symptom_text}, immediate medical evaluation is recommended."
        action = "Call emergency services (112) or go to the nearest emergency room."
    elif label == "Urgent":
        explanation = f"Based on {symptom_text}, prompt medical attention is advised."
        action = "Visit an urgent care clinic or your doctor within 24 hours."
    else:
        explanation = f"Based on {symptom_text}, this can likely be managed at home with rest and care."
        action = "Rest, stay hydrated, and monitor symptoms. See a doctor if symptoms worsen."
    
    return {
        "triage_label": label,
        "confidence": conf,
        "probabilities": probs,
        "explanation_text": explanation,
        "recommended_action": action,
        "shap_features": [{"feature": r, "human_label": r} for r in reasons[:3]],
        "model_used": "heuristic",
    }


def classify_triage(
    symptoms: List[str],
    severity: Optional[float],
    duration_hours: Optional[float],
    age: Optional[int],
    comorbidities: List[str],
    bayesian_urgency: str,
    answers: Dict[str, str],
    red_flag_count: int = 0,
    chief_complaint: str = "",
    gender: Optional[str] = None,
) -> Dict:
    """Main classification interface. Uses Gemini API with fallback to heuristics."""
    
    # Try Gemini first
    result = classify_triage_gemini(
        symptoms=symptoms,
        severity=severity,
        duration_hours=duration_hours,
        age=age,
        gender=gender,
        comorbidities=comorbidities,
        answers=answers,
        chief_complaint=chief_complaint,
    )
    
    if result:
        return result
    
    # Fallback to simple heuristics
    return _simple_heuristic_classify(symptoms, severity, duration_hours)
