"""Build corpus_hadith.json.gz from two sources that complement each other.

Source A, AhmedBaset/hadith-json (tag v1.2.0, `the_9_books`, texts scraped from sunnah.com): all nine books,
Arabic chapter titles, but no usable hadith numbers (`idInBook` is a scrape sequence, not the standard number).
It is the only source here for Musnad Ahmad (incomplete: 1,374 hadiths) and Sunan al-Darimi.

Source B, fawazahmed0/hadith-api (commit below, Unlicense): seven books with the standard `hadithnumber`
and hadith gradings. It has more Bukhari hadiths than source A (7,589 vs 7,277) but leaves the Arabic text empty
for some hadiths (e.g. 203 in Muslim) that source A has.

Merge, per book of source B (both sources list a book in the same order, so the two sequences are aligned):
  - same text in both            -> one entry: B's text and number, A's Arabic chapter title
  - in B only (text present)     -> entry from B, English chapter title, number from B
  - in A only                    -> entry from A with an EMPTY number (never guessed)
  - B has no text, A has it      -> A's text with B's number, only if the two sit at the same place in the
                                    sequence and the block sizes agree (positional pairing; counted in the report)
Texts that differ slightly are paired only above SIMILARITY_MIN. Everything else stays unpaired.
Ahmad and Darimi come from A with an empty number.

The raw downloads go to data/hadith/ (A) and data/hadith2/ (B), are git-ignored, and are checked against the
SHA-256 values below.

Usage: python ingest_hadith.py
"""
import difflib
import gzip
import hashlib
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIR_A = ROOT / "data" / "hadith"
DIR_B = ROOT / "data" / "hadith2"
OUTPUT = ROOT / "corpus_hadith.json.gz"  # gzip: the plain JSON is 53 MB

TAG_A = "v1.2.0"
URL_A = "https://raw.githubusercontent.com/AhmedBaset/hadith-json/" + TAG_A + "/db/by_book/the_9_books/{name}.json"
COMMIT_B = "df57907be35291c91ad6a6691180e22ca9920784"
URL_B = "https://raw.githubusercontent.com/fawazahmed0/hadith-api/" + COMMIT_B + "/editions/ara-{name}.json"

SIMILARITY_MIN = 0.8

# Which field of source B holds the standard citation number. For every book but Muslim it is `hadithnumber`
# (checked against known numbers: Bukhari 1 and 6406, Abu Dawud 61, 236 and 4833, Tirmidhi 1924, Ibn Majah 2340).
# Muslim's `hadithnumber` is a continuous sequence (the Book of Purification starts at 534); the usual citation
# number (Abd al-Baqi: "الطهور شطر الإيمان" = 223) is `arabicnumber`, a string such as "223" or "8.01".
# A Muslim hadith without `arabicnumber` is left unnumbered rather than given the other scheme's number.
NUMBER_FIELD = {"muslim": "arabicnumber"}

# Order matters: when a text occurs in several books the first one here is reported as the source.
# (title, A: expected hadith count, A sha256, B sha256 or None if the book is not in source B)
BOOKS = {
    "bukhari": ("صحيح البخاري", 7277, "8b0038db684b9a37efe2f047627c8076496b2a6d05bff576272de17b6da699f7", "e34a3402889ca378871da3c5984b7875c680920e93f1c8738ac7afe502179562"),
    "muslim": ("صحيح مسلم", 7459, "530ed720dea65c7eb4d6ebfef86e9be22ed284f3cb2d33e33d1d66c8318fd24f", "194073b24090c5368e4d14a3f55c9e0ef144c7437bd7e5aa83aa4d2bc54a8ea0"),
    "abudawud": ("سنن أبي داود", 5276, "7bfced5699eed170bd996601f810863b8fb171c48f093925de4c54e4d194a0bd", "216139c5f40a8147e700d62ffa3b5b2fe45d0e034f86941a193c598c10056189"),
    "tirmidhi": ("جامع الترمذي", 4053, "e6fa74f574f6f5e6b4d90bef77e00e672af5ee92901a1eb8da99eefb8858daa1", "408028cd56329ed78edbe3ad443beb96b58e16c3e5bd49f9bc7b0eac77c8820f"),
    "nasai": ("سنن النسائي", 5768, "07c94b52058c781943cfc0f2ddf15af5877c0e134e71b286d40f14aaeb67e7ce", "c705983c19bb089c87cd6531aff609bd94d862183ed0859115b0ff991826a956"),
    "ibnmajah": ("سنن ابن ماجه", 4345, "081fb0e9b715c0b9e67de8d6a88276b80f88ec48517e3564b7bd9e8ff9a2312f", "b406e6be81588ab0ec1ddbed32f5fd95bbcdda242c460d88331e82eb5c2bc0aa"),
    "malik": ("موطأ مالك", 1985, "cce1c43c7d07a3f4d43a8dea1476ce7eabfbf8698b05980b827b134ebb0ef5da", "088b1f354e110211da006d47e37dd8f8837368f318ed683271f0fdb0f09a3ab5"),
    # Not in source B. Musnad Ahmad is incomplete in A (8 chapters; its README says chapters 8-30 are missing).
    "ahmed": ("مسند أحمد", 1374, "d889aedc76563439a230d0b557d2059b29de169ed310a064a92638dc84566d32", None),
    "darimi": ("سنن الدارمي", 3406, "45ec3ac92b072287e6c7451084f55f50a2676e0eab2ec165c4ffecfa57f41d2a", None),
}


def fetch(directory: Path, filename: str, url: str, sha256: str) -> dict:
    path = directory / filename
    if not path.exists():
        directory.mkdir(parents=True, exist_ok=True)
        print(f"downloading {filename} ...")
        with urllib.request.urlopen(url, timeout=180) as resp:
            path.write_bytes(resp.read())
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != sha256:
        raise SystemExit(f"{filename}: sha256 {digest} does not match the pinned value")
    return json.loads(raw)


def clean(text: str) -> str:
    text = text.replace("‎", "").replace("‏", "")
    return re.sub(r"\s+", " ", text).strip()


def number_text(value) -> str:
    return str(int(value)) if float(value) == int(value) else str(value)


def citation_number(hadith: dict, field: str) -> str:
    value = hadith.get(field)
    if value in (None, ""):
        return ""
    return number_text(value) if isinstance(value, (int, float)) else str(value)


def key(text: str) -> str:
    """Comparison key: the verifier's normalization, so spelling/diacritic differences never split a pair."""
    from app.services.verifier import normalize

    return normalize(text) if text else ""


def similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def entry(title: str, text: str, chapter: str, number: str, index, grades=None) -> dict:
    out = {
        "classification": "hadith",
        "text": text,
        "index": index,
        "source": {"book": title, "chapter": chapter, "number": number},
    }
    if grades:
        out["grades"] = grades
    return out


def merge_book(name: str, report: Counter) -> list[dict]:
    title, count_a, sha_a, sha_b = BOOKS[name]
    a = fetch(DIR_A, f"{name}.json", URL_A.format(name=name), sha_a)
    if len(a["hadiths"]) != count_a:
        raise SystemExit(f"{name}: expected {count_a} hadiths in source A, got {len(a['hadiths'])}")
    chapters_a = {c["id"]: c["arabic"].strip() for c in a["chapters"]}
    items_a = [
        (h["idInBook"], clean(h["arabic"]), chapters_a.get(h["chapterId"], ""))
        for h in sorted(a["hadiths"], key=lambda h: h["idInBook"])
    ]
    items_a = [i for i in items_a if i[1]]  # source A has no Arabic text for some hadiths (125 in Malik)

    if sha_b is None:
        report[f"{name}: from A only, no number"] += len(items_a)
        return [entry(title, text, chapter, "", idx) for idx, text, chapter in items_a]

    b = fetch(DIR_B, f"ara-{name}.json", URL_B.format(name=name), sha_b)
    sections_b = {int(k): v for k, v in b["metadata"]["sections"].items()}
    items_b = [
        (citation_number(h, NUMBER_FIELD.get(name, "hadithnumber")), clean(str(h["text"])), sections_b.get(h["reference"]["book"], ""), h["grades"])
        for h in b["hadiths"]
    ]
    keys_a = [key(i[1]) for i in items_a]
    keys_b = [key(i[1]) for i in items_b]

    out: list[dict | None] = []
    # Entries each side contributes alone; the second pass pairs them by text even if the books order them differently.
    only_a: dict[str, list[int]] = {}
    only_b: dict[str, list[int]] = {}

    def from_b(j: int, chapter: str | None = None, text: str | None = None, index=None, alone: bool = False):
        number, text_b, section, grades = items_b[j]
        if alone:
            only_b.setdefault(keys_b[j], []).append(len(out))
        out.append(entry(title, text or text_b, chapter or section, number, index, grades))

    def from_a(i: int):
        idx, text, chapter = items_a[i]
        only_a.setdefault(keys_a[i], []).append(len(out))
        out.append(entry(title, text, chapter, "", idx))

    matcher = difflib.SequenceMatcher(None, keys_a, keys_b, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                from_b(j, items_a[i][2], index=items_a[i][0])
                report[f"{name}: same text in A and B"] += 1
        elif op == "delete":
            for i in range(i1, i2):
                from_a(i)
                report[f"{name}: A only (no number)"] += 1
        elif op == "insert":
            for j in range(j1, j2):
                if items_b[j][1]:
                    from_b(j, alone=True)
                    report[f"{name}: B only"] += 1
                else:
                    report[f"{name}: B placeholder without text, skipped"] += 1
        else:  # replace: the two sides disagree over this stretch
            used_b: set[int] = set()
            pairs: dict[int, int] = {}
            same_size = (i2 - i1) == (j2 - j1)
            for i in range(i1, i2):
                best_j, best = None, SIMILARITY_MIN
                for j in range(j1, j2):
                    if j in used_b or not items_b[j][1]:
                        continue
                    s = similar(keys_a[i], keys_b[j])
                    if s >= best:
                        best_j, best = j, s
                if best_j is not None:
                    pairs[i] = best_j
                    used_b.add(best_j)
            for i in range(i1, i2):
                j = pairs.get(i)
                at = j1 + (i - i1)
                if j is not None:
                    from_b(j, items_a[i][2], index=items_a[i][0])
                    report[f"{name}: paired by similarity"] += 1
                elif same_size and not items_b[at][1] and at not in used_b:
                    # B left this hadith's text empty; the sequences agree on its place and on the block size.
                    used_b.add(at)
                    from_b(at, items_a[i][2], text=items_a[i][1], index=items_a[i][0])
                    report[f"{name}: number paired by position (B text empty)"] += 1
                else:
                    from_a(i)
                    report[f"{name}: A only (no number)"] += 1
            for j in range(j1, j2):
                if j in used_b:
                    continue
                if items_b[j][1]:
                    from_b(j, alone=True)
                    report[f"{name}: B only"] += 1
                else:
                    report[f"{name}: B placeholder without text, skipped"] += 1

    # Second pass: a hadith that both sides have but order differently shows up once as "A only" and once as
    # "B only". Pair them by identical normalized text (in order, for repeated texts) and keep one entry.
    for k, positions_a in only_a.items():
        for pos_a, pos_b in zip(positions_a, only_b.get(k, [])):
            kept, dropped = out[pos_b], out[pos_a]
            kept["index"] = dropped["index"]
            if dropped["source"]["chapter"]:
                kept["source"]["chapter"] = dropped["source"]["chapter"]
            out[pos_a] = None
            report[f"{name}: A only (no number)"] -= 1
            report[f"{name}: B only"] -= 1
            report[f"{name}: same text, different position in A and B"] += 1
    return [e for e in out if e is not None]


def main() -> None:
    report: Counter = Counter()
    corpus: list[dict] = []
    for name in BOOKS:
        entries = merge_book(name, report)
        numbered = sum(1 for e in entries if e["source"]["number"])
        print(f"  {name}: {len(entries)} hadiths, {numbered} numbered")
        corpus.extend(entries)
    print()
    for line, n in sorted(report.items()):
        print(f"  {n:6d}  {line}")
    with gzip.open(OUTPUT, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(corpus, f, ensure_ascii=False, indent=0)
    print(f"\nWrote {len(corpus)} hadiths to {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
