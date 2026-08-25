import pytest
from services import red_flags as rf

EMERGENCY_TEXTS = [
    ("I have crushing chest pain", "cardiac_chest_pain_severe"),
    ("chest pain and I'm sweating a lot", "cardiac_chest_pain_plus"),
    ("chest tightness spreading to my left arm", "cardiac_chest_pain_plus"),
    ("I can't breathe properly", "breathing_severe"),
    ("my lips are turning blue", "breathing_severe"),
    ("her face is drooping and speech is slurred", "stroke_signs"),
    ("sudden weakness in my left arm", "stroke_signs"),
    ("worst headache of my life came on suddenly", "thunderclap_headache"),
    ("fever and a stiff neck", "meningitis_signs"),
    ("my lips are swollen after eating peanuts", "anaphylaxis"),
    ("he passed out and won't wake up", "unconscious_seizure"),
    ("vomiting blood since morning", "severe_bleeding"),
    ("I took too many pills", "poisoning_overdose"),
    ("I am pregnant and bleeding", "pregnancy_bleeding_pain"),
    ("I want to kill myself", "crisis_self_harm"),
    ("i dont want to live anymore", "crisis_self_harm"),
]


@pytest.mark.parametrize("text,rule", EMERGENCY_TEXTS)
def test_emergency_rules_fire(text, rule):
    flags = rf.scan_text(text)
    assert rule in [f.rule_id for f in flags]
    assert rf.highest_level(flags) == "Emergency"


@pytest.mark.parametrize("text", [
    "mild headache since this morning",
    "sore throat and runny nose",
    "chest pain when I cough",            # chest pain alone is not an emergency rule
    "I fit into my old jeans again",     # no false seizure match on 'fit'
    "my stomach hurts a bit after lunch",
    "high fever",                         # needs a second sign for meningitis
    "hi, I have chills",
])
def test_no_false_alarm(text):
    assert rf.scan_text(text) == []


def test_urgent_rules():
    assert rf.highest_level(rf.scan_text("severe stomach pain")) == "Urgent"
    assert rf.highest_level(rf.scan_text("fever of 104 F")) == "Urgent"


def test_answer_rules_yes_and_value():
    flags = rf.scan_case("chest pain", {"cp_sweating": "yes", "cp_nausea": "no"})
    assert [f.rule_id for f in flags] == ["answer_cp_sweating"]
    assert rf.highest_level(rf.scan_case("bleeding", {"bl_stop": "no"})) == "Emergency"
    assert rf.scan_case("bleeding", {"bl_stop": "yes"}) == []


def test_free_text_answers_are_scanned():
    flags = rf.scan_case("headache", {"headache_location": "now my face is drooping on one side"})
    assert "stroke_signs" in [f.rule_id for f in flags]


def test_age_rules():
    assert rf.highest_level(rf.scan_case("fever", {}, age=0, symptoms=["fever"])) == "Emergency"
    assert rf.highest_level(rf.scan_case("chest pain", {}, age=70, symptoms=["chest_pain"])) == "Urgent"
    assert rf.scan_case("fever", {}, age=30, symptoms=["fever"]) == []


@pytest.mark.parametrize("label", ["HomeCare", "Urgent", "Emergency"])
def test_escalate_never_lowers(label):
    urgent = [rf.RedFlag("x", "Urgent", "", "")]
    out = rf.escalate(label, urgent)
    assert rf.LEVELS[out] >= rf.LEVELS[label]
    assert rf.LEVELS[out] >= rf.LEVELS["Urgent"]
    assert rf.escalate(label, []) == label


def test_duplicates_removed():
    flags = rf.scan_case("crushing chest pain", {"x": "crushing chest pain again"})
    ids = [f.rule_id for f in flags]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("text", [
    "I keep having thoughts of ending my life",
    "I want to take my own life",
    "thinking about ending it all",
])
def test_crisis_phrasings(text):
    assert rf.is_crisis(rf.scan_text(text))


@pytest.mark.parametrize("text", [
    "acid reflux after a heavy dinner, no chest pain",
    "headache without any stiff neck, fever since yesterday",
    "denies chest pain, feels heavy and tired",
])
def test_negated_symptoms_do_not_fire(text):
    assert rf.highest_level(rf.scan_text(text)) != "Emergency"


def test_not_breathing_still_fires():
    assert rf.highest_level(rf.scan_text("he is not breathing")) == "Emergency"
