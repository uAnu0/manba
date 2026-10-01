"""Check corpus.json against the Tanzil texts in data/tanzil/.

  1. Integrity: every ayah of corpus.json equals Tanzil Uthmani (`text`) and Tanzil simple-clean
     (`match_text`) character for character, apart from the removed basmala; numbering is complete.
  2. Reach: after normalization, how many verses are matched by BOTH spellings, and which word-level
     differences remain between the two (these are what a user typing one script against the other hits).

Usage: python validate_corpus.py [--show N]
"""
import argparse
import difflib
import json
import sys
from collections import Counter

from app.services.verifier import CORPUS_PATH, normalize
from ingest_quran import BASMALA_WORDS, EXPECTED_AYAHS, load_tanzil, strip_basmala


def tanzil_without_basmala(name: str) -> dict[tuple[int, int], str]:
    return {k: strip_basmala(*k, v) for k, v in load_tanzil(name).items()}


def word_diffs(a: str, b: str) -> list[tuple[str, str]]:
    wa, wb = a.split(), b.split()
    return [
        (" ".join(wa[i1:i2]), " ".join(wb[j1:j2]))
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes()
        if op != "equal"
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", type=int, default=15)
    args = parser.parse_args()

    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    uthmani = tanzil_without_basmala("quran-uthmani.txt")
    simple = tanzil_without_basmala("quran-simple-clean.txt")

    problems = []
    keys = []
    for item in corpus:
        sura, ayah = map(int, item["source"]["number"].split(":"))
        key = (sura, ayah)
        keys.append(key)
        if item["text"] != uthmani.get(key):
            problems.append(f"{sura}:{ayah} text differs from Tanzil Uthmani")
        if item.get("match_text") != simple.get(key):
            problems.append(f"{sura}:{ayah} match_text differs from Tanzil simple-clean")
    if sorted(keys) != sorted(uthmani) or len(set(keys)) != len(keys):
        problems.append("ayah numbering is incomplete or duplicated")
    if len(corpus) != EXPECTED_AYAHS:
        problems.append(f"expected {EXPECTED_AYAHS} ayahs, found {len(corpus)}")

    print(f"1. Integrity: {len(corpus)} ayahs checked, {len(problems)} problems")
    for line in problems[:20]:
        print("   ", line)

    same = 0
    gaps: Counter = Counter()
    for key in sorted(uthmani):
        a, b = normalize(uthmani[key]), normalize(simple[key])
        if a == b:
            same += 1
        else:
            gaps.update(word_diffs(a, b))
    print(f"\n2. Reach: Uthmani and simple-clean normalize to the same text in {same}/{len(uthmani)} ayahs")
    print("   (the corpus accepts either spelling; the remaining differences only matter for mixed-script input)")
    for (x, y), n in gaps.most_common(args.show):
        print(f"   {n:4d}x  {x!r} vs {y!r}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
