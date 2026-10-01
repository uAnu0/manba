"""Download the Quran from semarketir/quranjson and write it to corpus.json.

Usage: python ingest_quran.py
"""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/semarketir/quranjson/master/source/surah/surah_{n}.json"
OUTPUT = Path(__file__).resolve().parent / "corpus.json"
BOOK = "القرآن الكريم"
SURAH_COUNT = 114


def fetch_surah(n: int, retries: int = 3) -> dict:
    url = BASE_URL.format(n=n)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8-sig"))
        except Exception:
            if attempt == retries:
                raise
            time.sleep(2 * attempt)


def surah_entries(n: int, data: dict) -> list[dict]:
    entries = []
    for key, text in data["verse"].items():
        ayah = int(key.removeprefix("verse_"))
        if ayah == 0:  # unnumbered basmala header, not an ayah
            continue
        entries.append(
            {
                "classification": "quran",
                "text": text.replace("﻿", "").strip(),
                "source": {"book": BOOK, "chapter": data["name"].strip(), "number": f"{n}:{ayah}"},
            }
        )
    return sorted(entries, key=lambda e: int(e["source"]["number"].split(":")[1]))


def main() -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        surahs = list(pool.map(fetch_surah, range(1, SURAH_COUNT + 1)))

    corpus = []
    for n, data in enumerate(surahs, start=1):
        entries = surah_entries(n, data)
        if len(entries) != data.get("count", len(entries)):
            print(f"warning: surah {n} has {len(entries)} verses, expected {data['count']}")
        corpus.extend(entries)

    OUTPUT.write_text(json.dumps(corpus, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(corpus)} ayahs from {len(surahs)} surahs to {OUTPUT}")


if __name__ == "__main__":
    main()
