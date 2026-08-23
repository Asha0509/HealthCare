"""
Answer validation and normalisation for follow-up questions.

Each question in the knowledge graph has a type (yesno, scale, duration,
choice, text). Answers are checked against that type so "5" can't be stored
as the answer to "Do you have nausea?", and severity/duration answers are fed
back into the case instead of being ignored.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

YES = {"yes", "y", "yeah", "yep", "haan", "ha", "true"}
NO = {"no", "n", "nope", "nahi", "false"}

DURATION_UNITS = [
    (r"min(ute)?s?", 1 / 60),
    (r"h(ou)?rs?|hours?", 1),
    (r"days?", 24),
    (r"w(ee)?ks?|weeks?", 168),
    (r"months?", 720),
    (r"years?", 8760),
]
# Quick-pick values the UI offers for duration questions.
DURATION_PRESETS = {
    "less than a day": 12,
    "1-3 days": 48,
    "4-7 days": 132,
    "1-4 weeks": 360,
    "more than a month": 1080,
}


class AnswerError(ValueError):
    """Raised when an answer doesn't fit its question type."""


def parse_duration_hours(text: str) -> Optional[float]:
    t = " ".join(text.lower().split())
    if t in DURATION_PRESETS:
        return float(DURATION_PRESETS[t])
    if t in ("today", "since morning", "a few hours"):
        return 6.0
    if t in ("yesterday", "since yesterday"):
        return 24.0
    m = re.match(r"^(?:about |around |for )?(\d+(?:\.\d+)?|a|an|one|two|three|four|five|six|seven)\s*(.*)$", t)
    if not m:
        return None
    words = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
    token = m.group(1)
    num = float(words[token]) if token in words else float(token)
    unit = m.group(2).strip()
    for pattern, mult in DURATION_UNITS:
        if re.fullmatch(pattern, unit):
            return num * mult
    return None


def normalise(question: Dict, raw: str) -> str:
    """Return the canonical stored answer, or raise AnswerError with a user-facing message."""
    qtype = question.get("type", "text")
    value = " ".join(str(raw or "").split())
    if not value:
        raise AnswerError("Please enter an answer.")

    if qtype == "yesno":
        v = value.lower().rstrip(".!")
        if v in YES:
            return "yes"
        if v in NO:
            return "no"
        if v in ("not sure", "unsure", "don't know", "dont know"):
            return "not sure"
        raise AnswerError("Please answer Yes or No (or 'Not sure').")

    if qtype == "scale":
        m = re.fullmatch(r"(\d{1,2})(?:\s*/\s*10)?", value)
        if not m or not 1 <= int(m.group(1)) <= 10:
            raise AnswerError("Please pick a number from 1 (mild) to 10 (worst imaginable).")
        return m.group(1)

    if qtype == "duration":
        if parse_duration_hours(value) is None:
            raise AnswerError("Please give a duration, for example '3 days' or '5 hours'.")
        return value.lower()

    if qtype == "choice":
        options: List[str] = question.get("options") or []
        for opt in options:
            if value.lower() == opt.lower():
                return opt
        raise AnswerError("Please choose one of: " + ", ".join(options))

    if len(value) > 500:
        raise AnswerError("Please keep your answer under 500 characters.")
    return value


def case_updates(question: Dict, answer: str) -> Dict:
    """Fields to merge into the case after an answer (severity, duration)."""
    updates: Dict = {}
    if question.get("type") == "scale":
        updates["severity_score"] = float(answer)
    elif question.get("type") == "duration":
        hours = parse_duration_hours(answer)
        if hours is not None:
            updates["duration_hours"] = hours
    return updates


def presentation(question: Dict) -> Tuple[str, Optional[List[str]]]:
    """Answer type and the options the UI should render as buttons."""
    qtype = question.get("type", "text")
    if qtype == "yesno":
        return qtype, ["Yes", "No", "Not sure"]
    if qtype == "duration":
        return qtype, [k[0].upper() + k[1:] for k in DURATION_PRESETS]
    if qtype == "choice":
        return qtype, question.get("options")
    return qtype, None
