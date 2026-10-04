"""Build data/fiqh/kuwaiti.jsonl.gz from the Kuwaiti Fiqh Encyclopedia (al-Mawsu'a al-Fiqhiyya al-Kuwaytiyya).

The encyclopedia is published free of charge by the Kuwaiti Ministry of Awqaf (bohoth.awqaf.gov.kw) and is listed in the
challenge's scientific pack as a reference for general fiqh. The text used here is Shamela book 11430 (45 volumes,
"pagination matches the printed edition"), taken from the Hugging Face dataset MoMonir/shamela_books_text_full
(category 18, general fiqh). Each output line is one numbered paragraph of an entry, with its volume and page, so every
passage the app shows can be cited to the printed page.

Usage:
    python scripts/ingest_fiqh.py                       # downloads the category file (~260 MB) into data/fiqh_raw/
    python scripts/ingest_fiqh.py path/to/train-category-018.parquet

Needs pyarrow (pip install pyarrow) only for this build step; the app reads the .jsonl.gz.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root holds the app package

import gzip
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "fiqh_raw" / "train-category-018.parquet"
URL = "https://huggingface.co/datasets/MoMonir/shamela_books_text_full/resolve/main/data/train-category-018.parquet"
OUT = ROOT / "data" / "fiqh" / "kuwaiti.jsonl.gz"
BOOK_ID = "11430"

MARK = re.compile("‌\\s*‌")  # Shamela wraps headings in zero-width non-joiners
PARA = re.compile(r"(?:(?<=\s)|^)(\d{1,3})\s*-\s+")  # "12 - " starts numbered paragraph 12
_DIAC = re.compile("[ً-ٰٟـ]")
SECTION_HINTS = ("التعريف", "الحكم", "الالفاظ", "الأحكام", "الاحكام", "مواطن", "اولا", "أولا", "ثانيا", "ثالثا", "رابعا", "خامسا",
                 "المبحث", "الفصل", "المطلب", "الفرع", "شروط", "اركان", "أركان", "صفته", "حكمه", "اقسام", "أقسام", "انواع", "أنواع")
MAX_CHARS = 9000  # a very long paragraph is cut so a shown passage stays readable


def plain(s: str) -> str:
    return _DIAC.sub("", s).strip()


def is_section(heading: str, body_start: str) -> bool:
    h = plain(heading)
    if h.endswith(":") or ":" in h:
        return True
    if any(h.startswith(x) or h.startswith("ال" + x) for x in SECTION_HINTS):
        return True
    if len(h.split()) > 6:
        return True
    b = plain(body_start)[:40]
    return not (b.startswith("التعريف") or b.startswith("1 -") or b.startswith("1-") or b.startswith("انظر") or "انظر" in h)


def pages(parquet: Path):
    import pyarrow.parquet as pq

    table = pq.read_table(parquet, columns=["book_id", "volume_number", "page_number", "text"], filters=[("book_id", "=", BOOK_ID)])
    rows = table.to_pylist()
    def key(r):
        try:
            return int(r["volume_number"]), int(float(r["page_number"]))
        except (TypeError, ValueError):
            return 999, 0
    rows.sort(key=key)
    for r in rows:
        v, p = key(r)
        if v == 999 or not r["text"]:
            continue
        yield v, p, r["text"]


def build(parquet: Path) -> int:
    # 1. One long text with a map from character offset to (volume, page).
    parts, marks, offset = [], [], 0
    for v, p, text in pages(parquet):
        marks.append((offset, v, p))
        parts.append(text)
        offset += len(text) + 1
    full = " ".join(parts)
    starts = [m[0] for m in marks]

    import bisect

    def where(pos: int) -> tuple[int, int]:
        i = max(0, bisect.bisect_right(starts, pos) - 1)
        return marks[i][1], marks[i][2]

    # 2. Split at headings; track the current entry (term) and section.
    pieces = [(m.start(), m.end()) for m in MARK.finditer(full)]
    out, entry, section, count, last = [], "", "", 0, 0
    # Text between consecutive markers alternates heading / body; a short piece followed by a marker is a heading.
    bounds = [0] + [e for _, e in pieces]
    ends = [s for s, _ in pieces] + [len(full)]
    segments = [(b, e) for b, e in zip(bounds, ends) if e > b]
    i = 0
    while i < len(segments):
        b, e = segments[i]
        chunk = full[b:e].strip()
        nxt = full[segments[i + 1][0] : segments[i + 1][1]] if i + 1 < len(segments) else ""
        if 0 < len(chunk) <= 90 and i + 1 < len(segments):
            if is_section(chunk, nxt):
                section = plain(chunk).rstrip(":").strip()
            else:
                entry, section, last = plain(chunk).rstrip(":").strip(), "", 0
            i += 1
            continue
        if entry:
            found = list(numbered(chunk, last))
            last = max([last] + [n for n, _, _, _ in found])
            for para_no, start, stop, heading in found:
                text = chunk[start:stop].strip()
                if len(plain(text)) < 40:
                    continue
                v, p = where(b + start)
                for k in range(0, len(text), MAX_CHARS):
                    out.append({"id": count, "e": entry, "s": section, "h": heading, "n": para_no, "v": v, "p": p, "t": text[k : k + MAX_CHARS]})
                    count += 1
        i += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return count


INLINE = re.compile(r"(?:^|[.)\]»؛])\s*([^.:؛()]{3,90}):\s*$")  # "زَكَاةُ الْحُلِيِّ:" just before a paragraph number


def numbered(body: str, last: int = 0):
    """(paragraph number, start, end, inline heading) for each numbered paragraph.

    Numbers run on through an entry, so a number is accepted only a little after `last` (the entry's last paragraph so
    far; small gaps happen where Shamela lost a number): "سنة 3 - " inside a sentence does not split a paragraph. Text
    before the first number continues paragraph `last`. A short "title:" right before a number becomes its heading."""
    seq = []
    for m in PARA.finditer(body):
        n = int(m.group(1))
        if last < n <= last + 3 or (last == 0 and not seq and n <= 2):
            start, heading = m.start(), ""
            prev_end = seq[-1][1] if seq else 0
            h = INLINE.search(body[max(prev_end, start - 120) : start])
            if h and len(h.group(1).split()) <= 10:
                heading = plain(h.group(1))
                start = max(prev_end, start - 120) + h.start(1)
            seq.append((n, start, heading))
            last = n
    if not seq:
        yield last, 0, len(body), ""
        return
    if seq[0][1] > 0:
        yield seq[0][0] - 1, 0, seq[0][1], ""
    for k, (n, pos, heading) in enumerate(seq):
        yield n, pos, seq[k + 1][1] if k + 1 < len(seq) else len(body), heading


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else RAW
    if not src.exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {URL} (about 260 MB) ...")
        urllib.request.urlretrieve(URL, src)
    n = build(src)
    print(f"wrote {n} passages to {OUT.relative_to(ROOT)}")
