"""Build corpus_hadith.json (Sahih al-Bukhari and Sahih Muslim) from AhmedBaset/hadith-json.

The two source files are downloaded once from a pinned tag into data/hadith/ and checked against the
SHA-256 values below; afterwards the script is offline. The raw files are not committed (24 MB, re-downloadable).

Source: https://github.com/AhmedBaset/hadith-json (tag v1.2.0), texts scraped from sunnah.com.

IMPORTANT: the dataset's `idInBook` is a sequence number from the scrape, NOT the standard hadith number of
any printed edition (Fath al-Bari / Abd al-Baqi). Example: "كلمتان خفيفتان..." is Bukhari 7563 in the standard
numbering but idInBook 6167 / 6438 here. Citing it as a hadith number would be wrong, so `source.number` is
left empty and the sequence is kept in the extra field `index` until a verified numbering is joined in.

Usage: python ingest_hadith.py
"""
import hashlib
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "hadith"
OUTPUT = ROOT / "corpus_hadith.json"
TAG = "v1.2.0"
BASE_URL = "https://raw.githubusercontent.com/AhmedBaset/hadith-json/" + TAG + "/db/by_book/the_9_books/{name}.json"
BOOKS = {
    "bukhari": {"title": "صحيح البخاري", "count": 7277, "sha256": "8b0038db684b9a37efe2f047627c8076496b2a6d05bff576272de17b6da699f7"},
    "muslim": {"title": "صحيح مسلم", "count": 7459, "sha256": "530ed720dea65c7eb4d6ebfef86e9be22ed284f3cb2d33e33d1d66c8318fd24f"},
}


def fetch(name: str) -> Path:
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"downloading {name}.json from {TAG} ...")
        with urllib.request.urlopen(BASE_URL.format(name=name), timeout=120) as resp:
            path.write_bytes(resp.read())
    expected = BOOKS[name]["sha256"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected and digest != expected:
        raise SystemExit(f"{path.name}: sha256 {digest} does not match the pinned value")
    print(f"{path.name}: sha256 {digest}")
    return path


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def book_entries(name: str) -> list[dict]:
    data = json.loads(fetch(name).read_text(encoding="utf-8"))
    info = BOOKS[name]
    chapters = {c["id"]: c["arabic"].strip() for c in data["chapters"]}
    entries = []
    for h in sorted(data["hadiths"], key=lambda h: h["idInBook"]):
        text = clean(h["arabic"])
        if not text:
            raise SystemExit(f"{name}: hadith {h['id']} has no Arabic text")
        entries.append(
            {
                "classification": "hadith",
                "text": text,
                "index": h["idInBook"],
                "source": {"book": info["title"], "chapter": chapters.get(h["chapterId"], ""), "number": ""},
            }
        )
    if len(entries) != info["count"]:
        raise SystemExit(f"{name}: expected {info['count']} hadiths, got {len(entries)}")
    return entries


def main() -> None:
    corpus = [entry for name in BOOKS for entry in book_entries(name)]
    OUTPUT.write_text(json.dumps(corpus, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Wrote {len(corpus)} hadiths to {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
