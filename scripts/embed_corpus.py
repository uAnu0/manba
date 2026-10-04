"""Embed every verse and hadith of the corpus and save data/corpus_embeddings.npz (needs OPENROUTER_API_KEY).

Quran verses are embedded in modern spelling (Tanzil simple-clean), hadith as their text without the chain of
narrators, both without vowel marks, hadith cut at 200 words. Batches are cached in data/embeddings_cache/ so an
interrupted run resumes. The model and size are set in app/services/dense.py. Cost with the default model is a few cents.

Usage: python scripts/embed_corpus.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root holds the app package

import gzip
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

from app.services import dense
from app.services.evidence import matn_start
from app.services.verifier import CORPUS_PATHS, load_corpus

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "embeddings_cache" / dense.MODEL.replace("/", "_")  # one folder per model: never mix vectors
BATCH = 48
WORKERS = 8


def doc_texts() -> list[str]:
    """One text per corpus entry, in the order of verifier.load_corpus."""
    texts = []
    for path in CORPUS_PATHS:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as f:
            for item in json.load(f):
                if item["classification"] == "quran":
                    text = dense.plain(item.get("match_text") or item["text"])
                else:
                    raw = item["text"]
                    text = " ".join(dense.plain(raw[matn_start(raw) :]).split()[: dense.MAX_DOC_WORDS])
                texts.append(dense.DOC_PREFIX + text[:1500])
    return texts


def embed_batch(client: OpenAI, number: int, batch: list[str]) -> np.ndarray:
    file = CACHE / f"{number:05d}.npy"
    if file.exists():
        return np.load(file)
    for attempt in range(5):
        try:
            r = client.embeddings.create(model=dense.MODEL, input=batch, **dense.REQUEST_EXTRA)
            vectors = np.array([d.embedding for d in r.data], dtype=np.float32)
            np.save(file, vectors)
            return vectors
        except Exception as exc:  # rate limits and transient errors
            error = exc
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f"batch {number} failed: {error}")


def main() -> None:
    load_dotenv()
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1", api_key=(os.getenv("OPENROUTER_API_KEY") or "").strip(), timeout=180
    )
    entries = load_corpus()
    texts = doc_texts()
    assert len(texts) == len(entries), (len(texts), len(entries))
    CACHE.mkdir(parents=True, exist_ok=True)
    batches = [texts[i : i + BATCH] for i in range(0, len(texts), BATCH)]
    print(f"{len(texts)} texts in {len(batches)} batches with {dense.MODEL} ({dense.DIMS} dims)")
    t0 = time.time()
    with ThreadPoolExecutor(WORKERS) as pool:
        parts = list(pool.map(lambda args: embed_batch(client, *args), enumerate(batches)))
    matrix = np.concatenate(parts)[:, : dense.DIMS]  # first DIMS numbers; the model orders them by importance
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    scales = np.abs(matrix).max(axis=1)
    quantized = np.round(matrix / scales[:, None] * 127).astype(np.int8)
    np.savez(
        dense.EMBEDDINGS_PATH,
        vectors=quantized,
        scales=scales.astype(np.float16),
        fingerprint=dense.fingerprint(entries),
        model=dense.MODEL,
    )
    size = dense.EMBEDDINGS_PATH.stat().st_size / 1e6
    print(f"saved {matrix.shape} to {dense.EMBEDDINGS_PATH.name} ({size:.0f} MB) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
