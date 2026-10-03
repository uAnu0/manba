"""Meaning-based search over the corpus.

An embedding model turns a text into a list of numbers such that texts with similar meaning get similar numbers.
Every verse and hadith was embedded once (embed_corpus.py -> corpus_embeddings.npz, shipped with the app); at question
time only the question is embedded (one call to the OpenRouter embeddings API) and compared with all of them.
It finds "من قتل نفسه بحديدة" for a question about suicide, which keyword search cannot.
"""
import hashlib
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.services.cache import async_cache
from app.services.llm_extractor import _get_client, provider_for
from app.services.verifier import Entry, load_corpus

ROOT = Path(__file__).resolve().parents[2]
EMBEDDINGS_PATH = ROOT / "corpus_embeddings.npz"

# Chosen by a bake-off on the golden questions (subset corpus, top 8 / top 20 per type): gemini 81% / 94%,
# qwen3-embedding-8b 67% / 78%, multilingual-e5-large 44% / 56%, bge-m3 42% / 64%. Truncating gemini's 3072 numbers
# to the first 768 (and renormalizing) loses nothing measurable (81% / 94%); 512 does (72% / 86%).
MODEL = "google/gemini-embedding-001"
DIMS = 768
DOC_PREFIX = ""
QUERY_PREFIX = ""
REQUEST_EXTRA: dict = {}

_DIACRITICS = re.compile("[ً-ٰٟۖ-ۭـ]")
MAX_DOC_WORDS = 200


def plain(text: str) -> str:
    """Text as it is embedded: no vowel marks, no tatweel, whitespace collapsed (spelling is left as written)."""
    return " ".join(_DIACRITICS.sub("", text).split())


def fingerprint(entries: tuple[Entry, ...]) -> str:
    """Identifies the corpus the vectors belong to: same entries in the same order."""
    h = hashlib.sha1()
    for e in entries:
        h.update(f"{e.classification}|{e.number}|{e.text[:40]}\n".encode())
    return h.hexdigest()


class DenseIndex:
    def __init__(self, path: Path):
        data = np.load(path, allow_pickle=False)
        # stored as int8 with one scale per row (v = q * scale / 127)
        self.matrix = data["vectors"].astype(np.float32) * (data["scales"].astype(np.float32)[:, None] / 127.0)
        self.fingerprint = str(data["fingerprint"])
        self.model = str(data["model"])
        # Quran and hadith are contiguous in the corpus order, so each class is a slice (a view, no copy).
        self.span: dict[str, tuple[int, int]] = {}
        for c in ("quran", "hadith"):
            ids = [i for i, e in enumerate(load_corpus()) if e.classification == c]
            assert ids == list(range(ids[0], ids[-1] + 1)), f"{c} entries are not contiguous in the corpus"
            self.span[c] = (ids[0], ids[-1] + 1)

    def search(self, query: np.ndarray, classification: str, limit: int) -> list[tuple[int, float]]:
        start, stop = self.span[classification]
        sims = self.matrix[start:stop] @ query
        top = np.argpartition(-sims, min(limit, len(sims) - 1))[:limit]
        top = top[np.argsort(-sims[top])]
        return [(start + int(i), float(sims[i])) for i in top]


@lru_cache(maxsize=1)
def dense_index() -> DenseIndex | None:
    """The shipped vectors, or None if the file is missing or belongs to a different version of the corpus."""
    if not EMBEDDINGS_PATH.exists():
        return None
    index = DenseIndex(EMBEDDINGS_PATH)
    if index.fingerprint != fingerprint(load_corpus()):
        return None
    return index


@async_cache(maxsize=2048)
async def embed_query(question: str, api_key: str | None = None) -> np.ndarray:
    provider = provider_for("EMBED")  # "google": Google's own API (free tier), the same model and the same first 768 numbers
    response = await _get_client(api_key, provider).embeddings.create(
        model="gemini-embedding-001" if provider == "google" else MODEL, input=[QUERY_PREFIX + question], **REQUEST_EXTRA
    )
    return unit(np.array(response.data[0].embedding, dtype=np.float32)[:DIMS])


def unit(vector: np.ndarray) -> np.ndarray:
    """Scale to length 1 (after keeping only the first DIMS numbers, which the model orders by importance)."""
    return vector / np.linalg.norm(vector)
