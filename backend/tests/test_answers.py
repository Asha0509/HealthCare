import pytest
from services import answers as a

YN = {"id": "q", "type": "yesno"}
SCALE = {"id": "headache_severity", "type": "scale"}
DUR = {"id": "cp_duration", "type": "duration"}
CHOICE = {"id": "sob_onset", "type": "choice", "options": ["Suddenly", "Gradually"]}
TEXT = {"id": "fever_temp", "type": "text"}


@pytest.mark.parametrize("raw,expected", [("Yes", "yes"), ("y", "yes"), ("NO", "no"), ("nope", "no"),
                                          ("Not sure", "not sure")])
def test_yesno(raw, expected):
    assert a.normalise(YN, raw) == expected


@pytest.mark.parametrize("raw", ["5", "maybe", "sometimes yes", ""])
def test_yesno_rejects(raw):
    with pytest.raises(a.AnswerError):
        a.normalise(YN, raw)


def test_scale():
    assert a.normalise(SCALE, "7") == "7"
    assert a.normalise(SCALE, "7/10") == "7"
    for bad in ("0", "11", "yes", "seven"):
        with pytest.raises(a.AnswerError):
            a.normalise(SCALE, bad)


@pytest.mark.parametrize("raw,hours", [("3 days", 72), ("5 hours", 5), ("2 weeks", 336), ("a week", 168),
                                       ("1-3 days", 48), ("Less than a day", 12), ("yesterday", 24),
                                       ("30 minutes", 0.5)])
def test_duration(raw, hours):
    assert a.normalise(DUR, raw)
    assert a.parse_duration_hours(a.normalise(DUR, raw)) == pytest.approx(hours)


def test_duration_rejects_numbers_without_units():
    with pytest.raises(a.AnswerError):
        a.normalise(DUR, "5")


def test_choice_is_case_insensitive_and_strict():
    assert a.normalise(CHOICE, "suddenly") == "Suddenly"
    with pytest.raises(a.AnswerError):
        a.normalise(CHOICE, "fast")


def test_text_length_limit():
    assert a.normalise(TEXT, " 101  F ") == "101 F"
    with pytest.raises(a.AnswerError):
        a.normalise(TEXT, "x" * 501)


def test_case_updates_feed_severity_and_duration():
    assert a.case_updates(SCALE, "8") == {"severity_score": 8.0}
    assert a.case_updates(DUR, "2 days") == {"duration_hours": 48}
    assert a.case_updates(YN, "yes") == {}


def test_presentation_gives_buttons():
    assert a.presentation(YN) == ("yesno", ["Yes", "No", "Not sure"])
    qtype, opts = a.presentation(DUR)
    assert qtype == "duration" and "1-3 days" in opts
    assert a.presentation(CHOICE)[1] == ["Suddenly", "Gradually"]
    assert a.presentation(TEXT) == ("text", None)
