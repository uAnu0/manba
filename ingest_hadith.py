"""Build corpus_hadith.json (the nine books of the_9_books) from AhmedBaset/hadith-json.

The source files are downloaded once from a pinned tag into data/hadith/ and checked against the
SHA-256 values below; afterwards the script is offline. The raw files are not committed (about 65 MB, re-downloadable).

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
# Order matters: when a text occurs in several books the first one here is reported as the source.
BOOKS = {
    "bukhari": {"title": "صحيح البخاري", "count": 7277, "sha256": "8b0038db684b9a37efe2f047627c8076496b2a6d05bff576272de17b6da699f7"},
    "muslim": {"title": "صحيح مسلم", "count": 7459, "sha256": "530ed720dea65c7eb4d6ebfef86e9be22ed284f3cb2d33e33d1d66c8318fd24f"},
    "abudawud": {"title": "سنن أبي داود", "count": 5276, "sha256": "7bfced5699eed170bd996601f810863b8fb171c48f093925de4c54e4d194a0bd"},
    "tirmidhi": {"title": "جامع الترمذي", "count": 4053, "sha256": "e6fa74f574f6f5e6b4d90bef77e00e672af5ee92901a1eb8da99eefb8858daa1"},
    "nasai": {"title": "سنن النسائي", "count": 5768, "sha256": "07c94b52058c781943cfc0f2ddf15af5877c0e134e71b286d40f14aaeb67e7ce"},
    "ibnmajah": {"title": "سنن ابن ماجه", "count": 4345, "sha256": "081fb0e9b715c0b9e67de8d6a88276b80f88ec48517e3564b7bd9e8ff9a2312f"},
    "malik": {"title": "موطأ مالك", "count": 1985, "sha256": "cce1c43c7d07a3f4d43a8dea1476ce7eabfbf8698b05980b827b134ebb0ef5da"},
    # Incomplete in the source: only 8 chapters / 1,374 hadiths of Musnad Ahmad (the dataset README says chapters 8-30 are missing).
    "ahmed": {"title": "مسند أحمد", "count": 1374, "sha256": "d889aedc76563439a230d0b557d2059b29de169ed310a064a92638dc84566d32"},
    "darimi": {"title": "سنن الدارمي", "count": 3406, "sha256": "45ec3ac92b072287e6c7451084f55f50a2676e0eab2ec165c4ffecfa57f41d2a"},
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
    if len(data["hadiths"]) != info["count"]:
        raise SystemExit(f"{name}: expected {info['count']} hadiths, got {len(data['hadiths'])}")
    entries, skipped = [], 0
    for h in sorted(data["hadiths"], key=lambda h: h["idInBook"]):
        text = clean(h["arabic"])
        if not text:  # the source has no Arabic text for some hadiths (125 in Muwatta Malik)
            skipped += 1
            continue
        entries.append(
            {
                "classification": "hadith",
                "text": text,
                "index": h["idInBook"],
                "source": {"book": info["title"], "chapter": chapters.get(h["chapterId"], ""), "number": ""},
            }
        )
    print(f"  {name}: {len(entries)} hadiths" + (f" ({skipped} without Arabic text skipped)" if skipped else ""))
    return entries


def main() -> None:
    corpus = [entry for name in BOOKS for entry in book_entries(name)]
    OUTPUT.write_text(json.dumps(corpus, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Wrote {len(corpus)} hadiths to {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
