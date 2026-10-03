"""Tafsir (commentary on the Quran) shown under a verse that a card already displays.

This is a plain lookup by verse number (sura:ayah): it takes no part in the search, the judge or any outcome, and no model writes
or summarises it. Each text is shown as its author wrote it, labelled with the tafsir's name and author. The files are built by
ingest_tafsir.py from data/tafsir_raw.
"""
import gzip
import json
import re
from functools import lru_cache
from pathlib import Path

from app.schemas import TafsirEntry, TafsirResponse, TafsirVerse

TAFSIR_DIR = Path(__file__).resolve().parents[2] / "data" / "tafsir"
MAX_VERSES = 12  # a reference may be a range such as 33:41-42; more than this is refused
REF = re.compile(r"^(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?$")


@lru_cache(maxsize=1)
def _sources() -> list[dict]:
    """Every tafsir file found, in display order. A missing folder simply means no tafsir."""
    found = []
    for path in sorted(TAFSIR_DIR.glob("*.json.gz")) if TAFSIR_DIR.exists() else []:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            found.append(json.load(f))
    return sorted(found, key=lambda s: s["meta"].get("order", 99))


def parse_ref(ref: str) -> list[str]:
    """"2:191" -> ["2:191"]; "33:41-42" -> ["33:41", "33:42"]. Raises ValueError for anything else."""
    m = REF.match(ref.strip())
    if not m:
        raise ValueError("a verse reference looks like 2:191 or 33:41-42")
    sura, first = int(m.group(1)), int(m.group(2))
    last = int(m.group(3)) if m.group(3) else first
    if not 1 <= sura <= 114 or first < 1 or last < first or last - first + 1 > MAX_VERSES:
        raise ValueError(f"a reference covers at most {MAX_VERSES} verses of one surah")
    return [f"{sura}:{n}" for n in range(first, last + 1)]


def lookup(ref: str) -> TafsirResponse:
    keys = parse_ref(ref)
    sources = _sources()
    verses = []
    shown: set[tuple[str, str]] = set()  # (tafsir, first verse of its commentary): a group's text is shown once in a range
    for key in keys:
        entries = []
        for source in sources:
            holder = source["group"].get(key, key)  # a verse without text of its own is covered by the group's first verse
            text = source["verses"].get(holder)
            if not text or (source["meta"]["id"], holder) in shown:
                continue
            shown.add((source["meta"]["id"], holder))
            meta = source["meta"]
            last = holder
            members = [k for k, h in source["group"].items() if h == holder]  # the verses this commentary spans, e.g. 4:60-62
            if members:
                last = max(members, key=lambda k: int(k.split(":")[1]))
            entries.append(
                TafsirEntry(
                    source_id=meta["id"],
                    name_ar=meta["name_ar"],
                    name_en=meta["name_en"],
                    author_ar=meta["author_ar"],
                    text=text,
                    covers_from=holder if last != holder else None,
                    covers_to=last if last != holder else None,
                )
            )
        verses.append(TafsirVerse(ref=key, entries=entries))
    return TafsirResponse(ref=ref.strip(), verses=verses, available=[s["meta"]["id"] for s in sources])
