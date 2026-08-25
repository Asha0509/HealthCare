import pytest
from services import rag


def test_parse_note_sections():
    raw = "---\nid: x\ntitle: X note\nurl: https://example.org\nsymptoms: fever, cough\n---\n## Self-care\nRest.\n\n## Get help if\nIt gets worse.\n"
    chunks = rag.parse_note(raw)
    assert [c.chunk_id for c in chunks] == ["x#self-care", "x#get-help-if"]
    assert chunks[0].symptoms == ["fever", "cough"] and chunks[0].url == "https://example.org"


def test_every_note_parses_and_has_a_url():
    chunks = rag.load_chunks()
    assert len({c.note_id for c in chunks}) >= 20
    assert all(c.url and c.url.startswith("https://medlineplus.gov/") for c in chunks)
    assert len({c.chunk_id for c in chunks}) == len(chunks)


@pytest.mark.parametrize("query,symptoms,expected_note", [
    ("crushing chest pain spreading to my arm", ["chest_pain"], {"chest_pain", "heart_attack"}),
    ("face drooping and slurred speech", [], {"stroke", "dizziness"}),
    ("lips swelling after eating peanuts", [], {"anaphylaxis"}),
    ("took too many pills", [], {"poisoning"}),
    ("how to look after a mild sore throat", ["sore_throat"], {"sore_throat"}),
    ("I want to end my life", [], {"mental_health_crisis"}),
])
def test_search_finds_relevant_note(query, symptoms, expected_note):
    hits = rag.retriever.search(query, k=3, symptoms=symptoms)
    assert {h["chunk_id"].split("#")[0] for h in hits} & expected_note


def test_keyword_fallback_mode(monkeypatch):
    r = rag.Retriever()
    monkeypatch.setattr(rag, "EMBED_MODEL_DIR", "/nonexistent")
    monkeypatch.setattr(rag, "EMBED_MODEL_ID", "nonexistent/model-xyz")
    r.ensure_loaded()
    assert r.mode == "keyword"
    hits = r.search("swollen lips peanuts allergy", k=2)
    assert hits and hits[0]["chunk_id"].startswith("anaphylaxis")


def test_empty_query():
    assert rag.retriever.search("   ") == []
