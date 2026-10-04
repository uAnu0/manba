"""Build data/corpus.json from the Tanzil Quran texts in data/tanzil/ (no network needed).

Each entry keeps the Uthmani verse as `text` (reference/display) and the Tanzil simple-clean verse as
`match_text` (modern spelling, what people type). Tanzil text is used unmodified, except that the basmala
Tanzil prepends to ayah 1 of every surah other than 1 and 9 is removed (it is not part of the ayah).

Tanzil Project, https://tanzil.net, CC BY 3.0: keep the credit and the link to tanzil.net.

Usage: python scripts/ingest_quran.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root holds the app package

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TANZIL_DIR = ROOT / "data" / "tanzil"
SURAH_NAMES = ROOT / "data" / "surah_names.json"
OUTPUT = ROOT / "data" / "corpus.json"
BOOK = "القرآن الكريم"
BASMALA_WORDS = 4  # بسم الله الرحمن الرحيم
EXPECTED_AYAHS = 6236


def load_tanzil(name: str) -> dict[tuple[int, int], str]:
    verses = {}
    for line in (TANZIL_DIR / name).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        sura, ayah, text = line.split("|", 2)
        verses[(int(sura), int(ayah))] = text.strip()
    return verses


def strip_basmala(sura: int, ayah: int, text: str) -> str:
    if ayah == 1 and sura not in (1, 9):
        words = text.split()
        if len(words) <= BASMALA_WORDS:
            raise ValueError(f"surah {sura}: ayah 1 is shorter than the basmala")
        return " ".join(words[BASMALA_WORDS:])
    return text


def main() -> None:
    uthmani = load_tanzil("quran-uthmani.txt")
    simple = load_tanzil("quran-simple-clean.txt")
    if uthmani.keys() != simple.keys():
        raise SystemExit("Tanzil Uthmani and simple-clean files do not cover the same ayahs")
    names = json.loads(SURAH_NAMES.read_text(encoding="utf-8"))

    corpus = []
    for sura, ayah in sorted(uthmani):
        corpus.append(
            {
                "classification": "quran",
                "text": strip_basmala(sura, ayah, uthmani[(sura, ayah)]),
                "match_text": strip_basmala(sura, ayah, simple[(sura, ayah)]),
                "source": {"book": BOOK, "chapter": names[sura - 1], "number": f"{sura}:{ayah}"},
            }
        )

    if len(corpus) != EXPECTED_AYAHS:
        raise SystemExit(f"expected {EXPECTED_AYAHS} ayahs, got {len(corpus)}")
    OUTPUT.write_text(json.dumps(corpus, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(corpus)} ayahs to {OUTPUT}")


if __name__ == "__main__":
    main()
