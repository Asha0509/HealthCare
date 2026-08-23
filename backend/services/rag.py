"""
Retrieval over the curated knowledge base (data/knowledge/*.md).

Each `##` section of a note is one chunk, embedded with a small static
embedding model (model2vec potion-base-8M, ~30 MB, numpy only) and searched
by cosine similarity. If the model can't be loaded the retriever falls back
to keyword overlap so the app keeps working, and reports which mode it's in.
"""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from core.config import settings
from core.logging import app_logger

EMBED_MODEL_ID = "minishlab/potion-base-8M"
EMBED_MODEL_DIR = os.environ.get(
    "EMBED_MODEL_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "models_cache", "potion-base-8M"),
)
KB_DIR = os.path.join(settings.DATA_DIR, "knowledge")


@dataclass
class Chunk:
    chunk_id: str          # "<note-id>#<section-slug>"
    note_id: str
    title: str
    section: str
    text: str
    url: Optional[str]
    symptoms: List[str] = field(default_factory=list)

    def citation(self, score: Optional[float] = None) -> Dict:
        d = {"chunk_id": self.chunk_id, "title": self.title, "section": self.section,
             "text": self.text, "url": self.url}
        if score is not None:
            d["score"] = round(float(score), 3)
        return d


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse_note(raw: str) -> List[Chunk]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if not m:
        return []
    meta: Dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    body = m.group(2)
    symptoms = [s.strip() for s in meta.get("symptoms", "").split(",") if s.strip()]
    chunks = []
    for sec in re.split(r"^## ", body, flags=re.M)[1:]:
        heading, _, text = sec.partition("\n")
        text = " ".join(text.split())
        if text:
            chunks.append(Chunk(f"{meta['id']}#{_slug(heading)}", meta["id"], meta.get("title", meta["id"]),
                                heading.strip(), text, meta.get("url") or None, symptoms))
    return chunks


def load_chunks(kb_dir: str = KB_DIR) -> List[Chunk]:
    chunks: List[Chunk] = []
    for name in sorted(os.listdir(kb_dir)):
        if name.endswith(".md") and name != "README.md":
            with open(os.path.join(kb_dir, name), encoding="utf-8") as f:
                chunks.extend(parse_note(f.read()))
    return chunks


_WORD = re.compile(r"[a-z]+")
_STOP = set("a an the and or of to in on for with is are be if you your it this that as at by from not can do".split())


def _tokens(text: str) -> List[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2]


class Retriever:
    def __init__(self) -> None:
        self.chunks: List[Chunk] = []
        self.matrix: Optional[np.ndarray] = None
        self.model = None
        self.mode = "uninitialised"
        self._lock = threading.Lock()

    def ensure_loaded(self) -> None:
        if self.mode != "uninitialised":
            return
        with self._lock:
            if self.mode != "uninitialised":
                return
            self.chunks = load_chunks()
            self._chunk_tokens = [set(_tokens(f"{c.title} {c.section} {c.text}")) for c in self.chunks]
            try:
                from model2vec import StaticModel
                if os.path.isdir(EMBED_MODEL_DIR):
                    self.model = StaticModel.from_pretrained(EMBED_MODEL_DIR)
                else:
                    self.model = StaticModel.from_pretrained(EMBED_MODEL_ID)
                vecs = self.model.encode([f"{c.title}. {c.section}. {c.text}" for c in self.chunks])
                self.matrix = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
                self.mode = "embeddings"
            except Exception as exc:  # model missing / no network: degrade, don't crash
                app_logger.warning(f"Embedding model unavailable, using keyword retrieval: {exc}")
                self.mode = "keyword"
            app_logger.info(f"Knowledge base loaded: {len(self.chunks)} chunks, mode={self.mode}")

    def search(self, query: str, k: int = 3, symptoms: Optional[List[str]] = None) -> List[Dict]:
        self.ensure_loaded()
        if not self.chunks or not query.strip():
            return []
        symptoms = symptoms or []
        qt = set(_tokens(query))
        keyword = np.array([len(qt & self._chunk_tokens[i]) / (len(qt) or 1) for i in range(len(self.chunks))])
        if self.mode == "embeddings":
            q = self.model.encode([query])[0]
            q = q / (np.linalg.norm(q) + 1e-9)
            # Hybrid: dense similarity plus exact-term overlap, which rescues
            # rare clinical words ("drooping", "slurred") a small model blurs.
            scores = 0.7 * (self.matrix @ q) + 0.3 * keyword
        else:
            scores = keyword
        # Small boost for notes about the patient's own symptoms.
        boost = np.array([0.08 if set(c.symptoms) & set(symptoms) else 0.0 for c in self.chunks])
        final = scores + boost
        order = np.argsort(-final)[:k]
        return [self.chunks[i].citation(final[i]) for i in order if final[i] > 0]

    def get(self, chunk_id: str) -> Optional[Chunk]:
        self.ensure_loaded()
        return next((c for c in self.chunks if c.chunk_id == chunk_id), None)

    def status(self) -> Dict:
        return {"mode": self.mode, "chunks": len(self.chunks),
                "notes": len({c.note_id for c in self.chunks}), "model": EMBED_MODEL_ID if self.mode == "embeddings" else None}


retriever = Retriever()
