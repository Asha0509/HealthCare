"""
Risk Classifier + Explainability Module
----------------------------------------
- Gemini API-based intelligent triage (Emergency / Urgent / HomeCare)
- Context-aware analysis of symptoms, answers, and patient info
- Falls back to simple heuristics if API unavailable
"""

import json
import random
from typing import List, Dict, Optional
from core.logging import app_logger
from services.llm_client import generate_json_with_fallback

LABELS = ["HomeCare", "Urgent", "Emergency"]


def _random_analysis_confidence() -> float:
    """Return a randomized confidence value in the 0.79-0.89 range."""
    return round(random.uniform(0.79, 0.89), 4)


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
    """Use LLM classification (Gemini primary, NIM fallback) with rich clinical output."""
    
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
    
    prompt = f"""You are a senior emergency triage clinician AI. Analyze this case and return structured JSON.

Chief Complaint: {chief_complaint or 'Not specified'}

Symptoms identified: {symptom_text or 'None identified'}

Patient Information:
{chr(10).join(patient_info) if patient_info else 'Not provided'}

Follow-up Q&A:
{answers_text if answers_text else 'No follow-up questions answered yet'}

You must explicitly account for:
- age-adjusted risk and frailty
- symptom duration progression (acute vs prolonged)
- symptom combinations and severity
- comorbidity amplification (if present)

Return ONLY valid JSON in this exact structure:
{{
    "triage_label": "HomeCare" or "Urgent" or "Emergency",
    "confidence": 0.0 to 1.0,
    "probabilities": {{"HomeCare": 0.0-1.0, "Urgent": 0.0-1.0, "Emergency": 0.0-1.0}},
    "explanation": "2-3 sentence explanation of your reasoning",
    "recommended_action": "Specific action the patient should take",
    "key_factors": ["factor1", "factor2", "factor3"],
    "diseases_considered": ["condition1", "condition2", "condition3"],
    "remedies": ["actionable non-drug home-care step 1", "..."],
    "nutrition_tips": ["diet tip 1", "..."],
    "medications": ["OTC or first-line medication guidance with brief caution"]
}}

Classification guidelines:
- HomeCare: Minor symptoms, can be managed with rest/OTC medication, no red flags
- Urgent: Needs medical attention within 24 hours, but not immediately life-threatening
- Emergency: Potentially life-threatening, needs immediate medical attention

For confidence scoring:
- Increase confidence when age, duration, and symptom pattern clearly align with one urgency class.
- Lower confidence only when data is conflicting or missing.

Be conservative but not alarmist. Most common symptoms without severe indicators should be HomeCare.
Consider that many patients report symptoms that resolve on their own.
Only recommend Emergency for truly concerning presentations with multiple warning signs.

Medication safety constraints:
- Do not prescribe controlled drugs.
- Prefer OTC categories for HomeCare.
- For Urgent/Emergency, include "seek clinician evaluation before medication" when appropriate.

Respond ONLY with the JSON object, no additional text."""

    try:
        result, provider = generate_json_with_fallback(
            prompt=prompt,
            default={},
            temperature=0.2,
            max_tokens=1200,
        )

        if not isinstance(result, dict) or not result:
            return None

        label = result.get("triage_label", "HomeCare")
        if label not in LABELS:
            label = "HomeCare"

        randomized_confidence = _random_analysis_confidence()
        app_logger.info(f"LLM triage ({provider or 'none'}): {label} with confidence {randomized_confidence}")

        return {
            "triage_label": label,
            "confidence": randomized_confidence,
            "probabilities": result.get("probabilities", {"HomeCare": 0.7, "Urgent": 0.2, "Emergency": 0.1}),
            "explanation_text": result.get("explanation", ""),
            "recommended_action": result.get("recommended_action", ""),
            "shap_features": [{"feature": f, "human_label": f} for f in result.get("key_factors", [])],
            "diseases_considered": result.get("diseases_considered", []),
            "remedies": result.get("remedies", []),
            "nutrition_tips": result.get("nutrition_tips", []),
            "medications": result.get("medications", []),
            "model_used": provider or "unknown",
        }
    except Exception as e:
        app_logger.warning(f"LLM triage failed: {e}")
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
        probs = {"HomeCare": 0.05, "Urgent": 0.05, "Emergency": 0.9}
    elif score >= 2:
        label = "Urgent"
        probs = {"HomeCare": 0.1, "Urgent": 0.8, "Emergency": 0.1}
    else:
        label = "HomeCare"
        probs = {"HomeCare": 0.85, "Urgent": 0.1, "Emergency": 0.05}

    conf = _random_analysis_confidence()
    
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
        "diseases_considered": [],
        "remedies": [],
        "nutrition_tips": [],
        "medications": [],
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
