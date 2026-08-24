"""
Deterministic red-flag rules.

These run on every case before and after the AI step. They can only ESCALATE
a triage level, never lower it, so a model mistake can't talk the system out
of an emergency. Patterns are deliberately simple and conservative: a false
alarm costs a trip to a clinic, a miss can cost a life.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional

LEVELS = {"HomeCare": 0, "Urgent": 1, "Emergency": 2}


@dataclass(frozen=True)
class RedFlag:
    rule_id: str
    level: str          # "Emergency" | "Urgent"
    reason: str         # plain-language explanation shown to the user
    matched: str        # the text that triggered it

    def to_dict(self) -> Dict:
        return asdict(self)


def _norm(text: str) -> str:
    return " ".join((text or "").lower().replace("’", "'").split())


# "no chest pain", "without fever", "denies headache": a symptom that is
# explicitly absent must not trigger a rule. ("not" is deliberately excluded
# so "not breathing" still matches.)
_NEGATION = re.compile(r"\b(no|without|denies|denied|never had|free of)\s+(any\s+)?(\w+\s+){0,2}$")


def _any(text: str, patterns: Iterable[str]) -> Optional[str]:
    for p in patterns:
        for m in re.finditer(p, text):
            if not _NEGATION.search(text[max(0, m.start() - 40):m.start()]):
                return m.group(0)
    return None


# Each rule: (rule_id, level, reason, [all-of pattern groups])
# A rule fires when every group has at least one matching pattern.
_RULES = [
    ("crisis_self_harm", "Emergency",
     "You mentioned thoughts of ending your life or harming yourself. Please reach out for support right now.",
     [[r"\b(kill|hurt|harm) (myself|my self)\b", r"\bsuicid", r"\bwant to die\b",
       r"\bend(ing)? (it all|my (own )?life)\b", r"\btak(e|ing) my (own )?life\b", r"\bthoughts of (dying|death)\b",
       r"\bno reason to live\b", r"\bself[- ]?harm", r"\bnot worth living\b", r"\bdon'?t want to (live|be here)\b"]]),
    ("cardiac_chest_pain_severe", "Emergency",
     "Severe or crushing chest pain can be a heart attack.",
     [[r"\bchest (pain|pressure|tightness)\b", r"\bheart ?ache\b"],
      [r"\b(severe|intense|extreme|crushing|unbearable|worst|squeezing|heavy)\b"]]),
    ("cardiac_chest_pain_plus", "Emergency",
     "Chest pain together with breathlessness, sweating, or pain spreading to the arm or jaw are warning signs of a heart attack.",
     [[r"\bchest (pain|pressure|tightness|discomfort)\b"],
      [r"\b(short(ness)? of breath|breathless|can'?t breathe|sweat(ing|y)?|clammy|left arm|jaw|radiat)"]]),
    ("breathing_severe", "Emergency",
     "Serious difficulty breathing needs emergency care.",
     [[r"\b(can'?t|cannot|unable to|struggling to|hard to) breathe\b", r"\bnot breathing\b", r"\bgasping\b",
       r"\bchoking\b", r"\blips? (are |is )?(turning |going )?(blue|grey|gray)\b", r"\bblue lips\b"]]),
    ("stroke_signs", "Emergency",
     "Face drooping, arm weakness, slurred speech or sudden confusion are stroke warning signs (FAST). Every minute counts.",
     [[r"\bface (is )?droop", r"\bdrooping (face|mouth)\b", r"\bslurred speech\b", r"\bslurring\b",
       r"\b(sudden )?(weakness|numbness) (in|on|of) (my |the |one |his |her )?(left |right )?(side|arm|leg|face)\b",
       r"\bone side of (my|the) (body|face)\b", r"\bcan'?t (speak|talk) properly\b", r"\bstroke\b"]]),
    ("thunderclap_headache", "Emergency",
     "A sudden, extremely severe 'worst ever' headache can signal bleeding in the brain.",
     [[r"\bheadache\b"],
      [r"\bworst (headache|pain) (of|in) my life\b", r"\bthunderclap\b", r"\bsudden(ly)? (severe|intense|explosive)\b",
       r"\bworst headache\b"]]),
    ("meningitis_signs", "Emergency",
     "Fever with a stiff neck, a rash that doesn't fade, or confusion can be meningitis.",
     [[r"\bfever\b", r"\bhigh temperature\b"],
      [r"\bstiff neck\b", r"\bneck (is )?stiff", r"\brash (that )?(doesn'?t|does not|won'?t) fade\b",
       r"\bconfus", r"\blight hurts my eyes\b"]]),
    ("anaphylaxis", "Emergency",
     "Swelling of the face, lips or throat, or trouble breathing after an allergy trigger, can be anaphylaxis.",
     [[r"\b(swollen|swelling|swelled) (of )?(my )?(face|lips?|tongue|throat)\b",
       r"\b(face|lips?|tongue|throat) (is |are )?(swollen|swelling)\b", r"\bthroat (is )?closing\b", r"\banaphyla"]]),
    ("unconscious_seizure", "Emergency",
     "Fainting, loss of consciousness or a seizure needs urgent assessment.",
     [[r"\bunconscious\b", r"\bpassed out\b", r"\bfainted\b", r"\bblack(ed)? out\b", r"\bseizure\b",
       r"\bconvuls", r"\bunresponsive\b", r"\bwon'?t wake up\b"]]),
    ("severe_bleeding", "Emergency",
     "Heavy bleeding that won't stop, or vomiting or coughing up blood, needs emergency care.",
     [[r"\bbleeding (heavily|a lot|won'?t stop|that won'?t stop|non[- ]?stop)\b", r"\bheavy bleeding\b",
       r"\b(vomit(ing)?|throwing up|cough(ing)? up) blood\b", r"\bblood in (my )?vomit\b", r"\bblack,? tarry stool"]]),
    ("poisoning_overdose", "Emergency",
     "A possible overdose or poisoning needs emergency help right away.",
     [[r"\boverdose\b", r"\btoo many (pills|tablets)\b", r"\bswallowed (bleach|poison|chemical)", r"\bpoison(ed|ing)\b"]]),
    ("pregnancy_bleeding_pain", "Emergency",
     "Bleeding or severe abdominal pain during pregnancy needs urgent medical care.",
     [[r"\bpregnan"], [r"\bbleed", r"\bsevere (abdominal|stomach|belly) pain\b", r"\bcramp"]]),
    ("severe_abdominal", "Urgent",
     "Severe abdominal pain should be checked by a doctor promptly.",
     [[r"\b(severe|intense|unbearable|worst|sharp) (abdominal|stomach|belly|tummy) (pain|ache)\b",
       r"\b(abdominal|stomach|belly) pain (is )?(severe|unbearable)\b"]]),
    ("high_fever_prolonged", "Urgent",
     "A high fever lasting several days should be checked by a doctor.",
     [[r"\b(10[3-9](\.\d)? ?(f|°f)|39\.[5-9]|4[0-2](\.\d)? ?(c|°c))\b", r"\bvery high fever\b"]]),
    ("dehydration_signs", "Urgent",
     "Being unable to keep fluids down or not passing urine are signs of dehydration.",
     [[r"\bcan'?t keep (anything|fluids|water) down\b", r"\bnot (peeing|urinating)\b",
       r"\bno urine\b", r"\bvery dizzy when standing\b"]]),
]

# Answer-based rules: question_id -> (level, reason) when answered "yes".
_YES_ANSWER_RULES = {
    "cp_radiation": ("Emergency", "Chest pain spreading to the arm, jaw or back is a heart-attack warning sign."),
    "cp_sweating": ("Emergency", "Chest pain with heavy sweating is a heart-attack warning sign."),
    "cp_breath": ("Emergency", "Chest pain with shortness of breath needs emergency assessment."),
    "headache_sudden": ("Emergency", "A sudden, severe headache can signal bleeding in the brain."),
    "headache_neck": ("Urgent", "Headache with a stiff neck should be checked promptly."),
    "rash_breathing": ("Emergency", "A rash with breathing difficulty can be a severe allergic reaction."),
    "sob_rest": ("Urgent", "Breathlessness at rest should be checked promptly."),
    "sob_cp": ("Emergency", "Breathlessness with chest pain needs emergency assessment."),
    "nv_blood": ("Emergency", "Vomiting blood needs emergency care."),
    "bl_pregnant": ("Emergency", "Bleeding during pregnancy needs urgent medical care."),
    "pal_chest": ("Emergency", "Palpitations with chest pain need emergency assessment."),
    "pal_dizzy": ("Urgent", "Palpitations with dizziness or fainting should be checked promptly."),
    "diz_speech": ("Emergency", "Difficulty speaking or a drooping face are stroke warning signs (FAST)."),
    "headache_vision": ("Urgent", "Headache with changes in vision should be checked promptly."),
    "cough_blood": ("Urgent", "Coughing up blood should be checked by a doctor promptly."),
    "st_breathe": ("Emergency", "A sore throat with difficulty breathing needs emergency care."),
    "sob_legs": ("Urgent", "Breathlessness with leg swelling should be checked promptly."),
    "nv_dehydration": ("Urgent", "Being unable to keep fluids down for over 8 hours risks dehydration."),
    "bp_bladder": ("Emergency", "Back pain with loss of bladder or bowel control needs emergency care."),
}

# Answer-based rules that fire on a specific non-yes answer.
_VALUE_ANSWER_RULES = {
    ("bl_stop", "no"): ("Emergency", "Bleeding that can't be stopped with pressure needs emergency care."),
    ("bl_amount", "heavy"): ("Emergency", "Heavy bleeding needs emergency care."),
    ("st_swallow", "no"): ("Urgent", "Being unable to swallow liquids should be checked promptly."),
    ("sob_onset", "suddenly"): ("Urgent", "Breathlessness that started suddenly should be checked promptly."),
}


def scan_text(text: str) -> List[RedFlag]:
    """Run every text rule over free text (complaint or answers)."""
    t = _norm(text)
    flags: List[RedFlag] = []
    for rule_id, level, reason, groups in _RULES:
        matches = [_any(t, g) for g in groups]
        if all(matches):
            flags.append(RedFlag(rule_id, level, reason, " + ".join(m for m in matches if m)))
    return flags


def scan_case(
    complaint: str,
    answers: Optional[Dict[str, str]] = None,
    age: Optional[int] = None,
    symptoms: Optional[List[str]] = None,
    max_fever_temp_c: Optional[float] = None,
) -> List[RedFlag]:
    """All red flags for a case: complaint text, yes/no answers, free-text answers, age-specific rules."""
    answers = answers or {}
    symptoms = symptoms or []
    flags = scan_text(complaint)

    for qid, value in answers.items():
        v = _norm(str(value))
        if qid in _YES_ANSWER_RULES and v in ("yes", "y", "true", "1"):
            level, reason = _YES_ANSWER_RULES[qid]
            flags.append(RedFlag(f"answer_{qid}", level, reason, f"{qid}=yes"))
        elif (qid, v) in _VALUE_ANSWER_RULES:
            level, reason = _VALUE_ANSWER_RULES[(qid, v)]
            flags.append(RedFlag(f"answer_{qid}", level, reason, f"{qid}={v}"))
        elif v not in ("yes", "no", "y", "n", "true", "false") and len(v) > 3:
            flags.extend(scan_text(v))

    if age is not None and age < 1 and "fever" in symptoms:
        flags.append(RedFlag("infant_fever", "Emergency",
                             "Any fever in a baby under 12 months needs prompt medical assessment.", f"age={age}"))
    if age is not None and age >= 65 and any(s in symptoms for s in ("chest_pain", "shortness_of_breath")):
        flags.append(RedFlag("older_adult_cardiorespiratory", "Urgent",
                             "Chest or breathing symptoms in adults over 65 should be checked promptly.", f"age={age}"))

    # de-duplicate by rule_id, keep first
    seen, unique = set(), []
    for f in flags:
        if f.rule_id not in seen:
            seen.add(f.rule_id)
            unique.append(f)
    return unique


def highest_level(flags: List[RedFlag]) -> Optional[str]:
    if not flags:
        return None
    return max(flags, key=lambda f: LEVELS[f.level]).level


def escalate(label: str, flags: List[RedFlag]) -> str:
    """Return the higher of `label` and the strongest red flag. Never lowers."""
    top = highest_level(flags)
    if top and LEVELS[top] > LEVELS.get(label, 0):
        return top
    return label


def is_crisis(flags: List[RedFlag]) -> bool:
    return any(f.rule_id == "crisis_self_harm" for f in flags)
