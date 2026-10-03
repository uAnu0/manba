"""Build the compact tafsir files the app serves (data/tafsir/*.json.gz) from the raw per-verse JSON.

Raw source: github.com/abdalrhmanreda/islamic-data-assets (folder tafser/, MIT license of the compilation; the underlying texts have
their own history: check the rights of each text before a public release). Put muyassar.json and saady.json in data/tafsir_raw/.

What is changed in the text, and nothing else:
  * HTML tags are removed (paragraph tags become line breaks),
  * { ... } around a quoted verse in As-Saadi becomes the Quran brackets ﴿ ... ﴾,
  * whitespace is tidied.
A scholar who comments on a group of verses at once has the text on the first verse and nothing on the others, or the same text
repeated on each verse: both are stored once, and the other verses point to the first one ("group" in the file), so the app can
say "this commentary covers 4:60-62".

Usage: python ingest_tafsir.py
"""
import gzip
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "tafsir_raw"
OUT = ROOT / "data" / "tafsir"

SOURCES = {
    "muyassar": {
        "file": "muyassar.json",
        "name_ar": "التفسير الميسر",
        "name_en": "Al-Tafsir al-Muyassar (the Simplified Tafsir)",
        "author_ar": "نخبة من علماء التفسير، مجمع الملك فهد لطباعة المصحف الشريف",
        "order": 1,
    },
    "saadi": {
        "file": "saady.json",
        "name_ar": "تفسير السعدي (تيسير الكريم الرحمن)",
        "name_en": "Tafsir al-Saadi (Taysir al-Karim al-Rahman)",
        "author_ar": "عبد الرحمن بن ناصر السعدي (ت 1376هـ)",
        "order": 2,
    },
}
LICENSE_NOTE = (
    "Compilation: MIT license (islamic-data-assets). Rights in the underlying texts are NOT verified: check them before a public release."
)


def clean(text: str) -> str:
    text = re.sub(r"</p\s*>\s*<p[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("{", "﴿").replace("}", "﴾")
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.split("\n") if line.strip()).strip()


def build(source: dict) -> dict:
    rows = json.loads((RAW / source["file"]).read_text(encoding="utf-8"))
    verses: dict[str, str] = {}
    group: dict[str, str] = {}  # a verse without its own text -> the verse that holds the commentary
    head = None
    for row in sorted(rows, key=lambda r: (r["sura"], r["aya"])):
        key = f'{row["sura"]}:{row["aya"]}'
        text = clean(row["text"])
        if text and head is not None and head.split(":")[0] == str(row["sura"]) and text == verses[head]:
            group[key] = head  # the same text repeated on a neighbouring verse
        elif text:
            verses[key] = text
            head = key
        elif head is not None and head.split(":")[0] == str(row["sura"]):
            group[key] = head
    return {"verses": verses, "group": group}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for sid, source in SOURCES.items():
        data = build(source)
        meta = {k: v for k, v in source.items() if k != "file"}
        meta.update(id=sid, license_note=LICENSE_NOTE, source="github.com/abdalrhmanreda/islamic-data-assets")
        payload = {"meta": meta, **data}
        path = OUT / f"{sid}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        print(f"{sid}: {len(data['verses'])} verses with text, {len(data['group'])} covered by an earlier verse's commentary, {path.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
