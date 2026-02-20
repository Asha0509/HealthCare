"""
Adaptive Questioning Engine
---------------------------
Implements the dynamic follow-up questioning system using:
  - Decision tree per symptom (from knowledge graph)
  - Bayesian posterior update as answers accumulate
  - Session state tracked in Redis
  - Gemini-based intelligent question filtering

This is the Adaptive Questioning Engine from the system architecture.
"""

import json
import os
import httpx
from typing import List, Dict, Optional
from core.config import settings
from core.logging import app_logger

_kg: Optional[Dict] = None


def _get_kg() -> Dict:
    global _kg
    if _kg is None:
        path = os.path.join(settings.DATA_DIR, "symptom_disease_graph.json")
        with open(path, "r") as f:
            _kg = json.load(f)
    return _kg


async def filter_questions_with_gemini(
    questions: List[Dict],
    chief_complaint: str,
    answered: Dict[str, str],
    symptoms: List[str]
) -> List[Dict]:
    """
    Use Gemini to filter out questions that are redundant or already answered
    based on the user's chief complaint and previous answers.
    """
    if not questions or not settings.GEMINI_API_KEY:
        return questions

    # Build context of what's already known
    answered_summary = ""
    if answered:
        answered_items = [f"Q: {qid} → A: {ans}" for qid, ans in answered.items()]
        answered_summary = "\n".join(answered_items)

    question_texts = [f"{i+1}. [{q['id']}] {q['text']}" for i, q in enumerate(questions)]
    
    prompt = f"""You are a medical triage assistant filtering follow-up questions.

Patient's initial complaint: "{chief_complaint}"
Identified symptoms: {', '.join(symptoms)}

Previous Q&A:
{answered_summary if answered_summary else "None yet"}

Candidate questions to ask:
{chr(10).join(question_texts)}

Task: Return ONLY the question IDs that should still be asked. Skip questions if:
1. The answer is already obvious from the chief complaint (e.g., don't ask "do you have fever?" if they said "I have a fever")
2. The question asks about something the patient already described
3. The question is redundant with something already answered

Return a JSON array of question IDs to KEEP (not skip). Example: ["cp_duration", "cp_radiation"]
Only return the JSON array, nothing else."""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.GEMINI_API_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}]}
            )
            resp.raise_for_status()
            result = resp.json()
            text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            # Parse JSON array from response
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            
            keep_ids = json.loads(text)
            
            # Filter questions to only keep the ones Gemini approved
            filtered = [q for q in questions if q["id"] in keep_ids]
            app_logger.info(f"Gemini filtered {len(questions)} questions to {len(filtered)}")
            return filtered
            
    except Exception as e:
        app_logger.warning(f"Gemini question filtering failed: {e}, using original questions")
        return questions


def get_questions_for_symptoms(symptoms: List[str], chief_complaint: str = "") -> List[Dict]:
    """
    Get ordered follow-up questions for the given list of symptoms.
    Prioritizes red-flag symptoms first.
    Deduplicates questions across multiple active symptoms.
    Skips questions asking about symptoms already reported.
    """
    kg = _get_kg()
    questions = []
    seen_ids = set()
    
    # Convert symptoms and chief complaint to searchable terms
    symptom_terms = set()
    for s in symptoms:
        symptom_terms.add(s.replace("_", " ").lower())
        # Add common variations
        if s == "fever":
            symptom_terms.update(["fever", "temperature", "hot", "feverish"])
        elif s == "nausea_vomiting":
            symptom_terms.update(["nausea", "vomiting", "nauseous", "vomit", "throwing up"])
        elif s == "headache":
            symptom_terms.update(["headache", "head pain", "head ache", "head hurts"])
        elif s == "shortness_of_breath":
            symptom_terms.update(["breath", "breathing", "breathless", "short of breath"])
        elif s == "cough":
            symptom_terms.update(["cough", "coughing"])
        elif s == "body_pain":
            symptom_terms.update(["body pain", "body ache", "body aches", "body hurts", "aching"])
    
    # Also extract terms from chief complaint
    if chief_complaint:
        complaint_lower = chief_complaint.lower()
        symptom_terms.add(complaint_lower)

    # Sort: red-flag symptoms first
    def is_red_flag(s):
        return kg.get(s, {}).get("red_flag", False)

    sorted_symptoms = sorted(symptoms, key=lambda s: (0 if is_red_flag(s) else 1))

    for symptom in sorted_symptoms:
        node = kg.get(symptom, {})
        for q in node.get("follow_up_questions", []):
            if q["id"] in seen_ids:
                continue
                
            # Skip questions that ask about symptoms already mentioned
            q_text = q["text"].lower()
            is_redundant = False
            
            for term in symptom_terms:
                # Check various question patterns that would be redundant
                if len(term) > 3:  # Only check meaningful terms
                    if f"do you have {term}" in q_text:
                        is_redundant = True
                        break
                    if f"have {term}" in q_text and "how long" not in q_text:
                        is_redundant = True
                        break
                    if f"any {term}" in q_text:
                        is_redundant = True
                        break
                    if f"experiencing {term}" in q_text:
                        is_redundant = True
                        break
                    # Check if the term is in the chief complaint and question asks about it
                    if chief_complaint and term in chief_complaint.lower() and term in q_text:
                        if "how long" not in q_text and "when" not in q_text and "how severe" not in q_text:
                            is_redundant = True
                            break
            
            if not is_redundant:
                seen_ids.add(q["id"])
                questions.append({**q, "symptom": symptom})

    return questions


async def get_next_question_async(
    symptoms: List[str],
    answered: Dict[str, str],
    question_index: int,
    chief_complaint: str = ""
) -> Optional[Dict]:
    """
    Return the next unanswered question, using Gemini to filter redundant ones.
    """
    all_questions = get_questions_for_symptoms(symptoms, chief_complaint)
    unanswered = [q for q in all_questions if q["id"] not in answered]

    if not unanswered:
        return None

    # Use Gemini to further filter questions
    if chief_complaint and unanswered:
        unanswered = await filter_questions_with_gemini(
            unanswered, chief_complaint, answered, symptoms
        )

    if not unanswered:
        return None

    return unanswered[0]  # Return first remaining question


def get_next_question(
    symptoms: List[str],
    answered: Dict[str, str],
    question_index: int,
    chief_complaint: str = ""
) -> Optional[Dict]:
    """
    Return the next unanswered question, or None if done.
    Synchronous version - uses simple filtering only.
    """
    all_questions = get_questions_for_symptoms(symptoms, chief_complaint)
    unanswered = [q for q in all_questions if q["id"] not in answered]

    if not unanswered or question_index >= len(all_questions):
        return None

    # Pick next unanswered
    for q in unanswered:
        return q  # Return first unanswered

    return None


def compute_progress(symptoms: List[str], answered: Dict[str, str], chief_complaint: str = "") -> int:
    """Return 0-100 progress percentage."""
    all_questions = get_questions_for_symptoms(symptoms, chief_complaint)
    if not all_questions:
        return 100
    answered_count = sum(1 for q in all_questions if q["id"] in answered)
    return int((answered_count / len(all_questions)) * 100)


def bayesian_urgency_update(
    base_urgency: str,
    answered: Dict[str, str],
    symptoms: List[str],
) -> str:
    """
    Simple Bayesian posterior update:
    Adjusts urgency based on answer patterns.
    Returns: 'Emergency' | 'Urgent' | 'HomeCare'
    """
    urgency_score = {"Emergency": 3, "Urgent": 2, "HomeCare": 1}
    reverse_map = {3: "Emergency", 2: "Urgent", 1: "HomeCare"}

    # Start from base
    kg = _get_kg()
    max_base = 1
    for s in symptoms:
        node_urgency = kg.get(s, {}).get("base_urgency", "home_care")
        score = {"emergency": 3, "urgent": 2, "home_care": 1}.get(node_urgency, 1)
        max_base = max(max_base, score)

    current_score = max_base

    # Boost rules based on answers
    boost_rules = {
        "cp_sweating": 1, "cp_radiation": 1, "cp_breath": 1,
        "headache_sudden": 2, "headache_neck": 1,
        "rash_breathing": 2,
        "sob_rest": 1, "sob_cp": 1,
        "nv_blood": 1, "nv_dehydration": 1,
        "bl_pregnant": 1, "bl_amount": 0.5,
        "pal_chest": 1, "pal_dizzy": 1,
    }

    for question_id, boost in boost_rules.items():
        val = answered.get(question_id, "").lower()
        if val in ["yes", "y", "1", "true"]:
            current_score += boost

    # Cap at 3
    current_score = min(current_score, 3)
    level = round(current_score)
    return reverse_map.get(level, "HomeCare")


def get_diseases_for_symptoms(symptoms: List[str]) -> List[str]:
    """Return combined disease list for symptoms."""
    kg = _get_kg()
    diseases = []
    for s in symptoms:
        for d in kg.get(s, {}).get("diseases", []):
            if d not in diseases:
                diseases.append(d)
    return diseases[:6]  # Top 6


def get_remedies_nutrition(symptoms: List[str]) -> Dict:
    """Return combined remedies and nutrition tips for symptoms."""
    kg = _get_kg()
    remedies = []
    nutrition = []
    for s in symptoms:
        node = kg.get(s, {})
        for r in node.get("remedies", []):
            if r not in remedies:
                remedies.append(r)
        for n in node.get("nutrition", []):
            if n not in nutrition:
                nutrition.append(n)
    return {"remedies": remedies[:6], "nutrition_tips": nutrition[:6]}
