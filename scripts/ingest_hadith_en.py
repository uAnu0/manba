"""Build data/translations/hadith_en.json.gz: English renderings of seven hadith books, keyed by the same book and number
as data/corpus_hadith.json.gz, so an English quote found here leads to the Arabic text, its source and its gradings.

Source: fawazahmed0/hadith-api (The Unlicense), the commit the Arabic corpus uses, English editions. The English texts are
the published translations that dataset carries (for example Muhsin Khan for al-Bukhari); their own rights are listed as
unverified in SOURCES.md. Numbers follow scripts/ingest_hadith.py: `hadithnumber`, except Muslim (`arabicnumber`).

Usage: python scripts/ingest_hadith_en.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root holds the app package

import gzip
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "translations" / "hadith_en.json.gz"
COMMIT = "df57907be35291c91ad6a6691180e22ca9920784"
URL = "https://raw.githubusercontent.com/fawazahmed0/hadith-api/" + COMMIT + "/editions/eng-{name}.json"
BOOKS = {"bukhari": "صحيح البخاري", "muslim": "صحيح مسلم", "abudawud": "سنن أبي داود", "tirmidhi": "جامع الترمذي",
         "nasai": "سنن النسائي", "ibnmajah": "سنن ابن ماجه", "malik": "موطأ مالك"}
NUMBER_FIELD = {"muslim": "arabicnumber"}


def main() -> None:
    items, names = [], {}
    for name, book in BOOKS.items():
        with urllib.request.urlopen(URL.format(name=name), timeout=120) as r:
            data = json.load(r)
        names[book] = data["metadata"]["name"]
        field = NUMBER_FIELD.get(name, "hadithnumber")
        for h in data["hadiths"]:
            text = (h.get("text") or "").strip()
            number = h.get(field)
            if not text or number in (None, "", 0):
                continue
            n = str(number)
            items.append({"book": book, "number": n[:-2] if n.endswith(".0") else n, "text": text})
        print(book, sum(1 for i in items if i["book"] == book))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    meta = {"source": f"https://github.com/fawazahmed0/hadith-api/tree/{COMMIT}", "license": "The Unlicense (dataset)", "books": names}
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "items": items}, f, ensure_ascii=False)
    print("total", len(items))


if __name__ == "__main__":
    main()
