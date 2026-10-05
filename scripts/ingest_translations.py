"""Download official Quran translations from QuranEnc (quranenc.com) into data/translations/<key>.json.gz.

QuranEnc publishes translations reviewed by the King Fahd Complex, Rowwad and partners. Its terms ask that the text is not
modified, that QuranEnc is credited, and that the version is shown: each file keeps the translation text exactly as the API
returns it, with the title, version and update time, and the app shows them next to every verse it quotes.

Usage: python scripts/ingest_translations.py [key ...]   (default: the keys below)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root holds the app package

import gzip
import json
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "translations"
API = "https://quranenc.com/api/v1"
KEYS = [
    "english_saheeh", "english_rwwad", "english_hilali_khan", "french_montada", "urdu_junagarhi",
    "indonesian_affairs", "turkish_rwwad", "spanish_montada_eu",
]


def get(url: str):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "manba-ingest"}), timeout=60) as r:
                return json.load(r)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def meta_of(key: str) -> dict:
    lang = key.split("_")[0]
    code = {"english": "en", "french": "fr", "urdu": "ur", "indonesian": "id", "turkish": "tr", "spanish": "es"}.get(lang, lang[:2])
    for t in get(f"{API}/translations/list/{code}")["translations"]:
        if t["key"] == key:
            return {"key": key, "language": t.get("language_iso_code", code), "title": t["title"], "description": t.get("description", ""),
                    "version": t.get("version"), "last_update": t.get("last_update"), "source": f"https://quranenc.com/en/browse/{key}"}
    raise SystemExit(f"unknown translation key {key}")


def main(keys: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key in keys:
        meta = meta_of(key)
        verses = {}
        for sura in range(1, 115):
            for row in get(f"{API}/translation/sura/{key}/{sura}")["result"]:
                verses[f"{int(row['sura'])}:{int(row['aya'])}"] = row["translation"]
            time.sleep(0.15)
        assert len(verses) == 6236, (key, len(verses))
        with gzip.open(OUT / f"{key}.json.gz", "wt", encoding="utf-8") as f:
            json.dump({"meta": meta, "verses": verses}, f, ensure_ascii=False)
        print(key, meta["version"], len(verses))


if __name__ == "__main__":
    main(sys.argv[1:] or KEYS)
