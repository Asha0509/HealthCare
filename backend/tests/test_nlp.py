import pytest

from services import nlp_engine


@pytest.mark.parametrize("text,present,absent", [
    ("sore throat since yesterday, no fever", {"sore_throat"}, {"fever"}),
    ("headache without any nausea", {"headache"}, {"nausea_vomiting"}),
    ("fever and a cough", {"fever", "cough"}, set()),
    ("I have chills and a rash", {"rash"}, set()),
])
def test_keyword_extraction_respects_negation(text, present, absent):
    found = set(nlp_engine.extract_symptoms_keyword(text))
    assert present <= found and not (absent & found)


def test_intent_greeting_needs_word_boundary():
    assert nlp_engine.detect_intent("I have had a high fever") == "symptom_report"
    assert nlp_engine.detect_intent("hi there") == "greeting"
