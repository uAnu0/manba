"""Cross-check corpus.json against the Tanzil Quran texts in data/tanzil/.

Three comparisons, all on text normalized by app.services.verifier.normalize:
  A. corpus.json  vs Tanzil Uthmani      -> is our downloaded corpus the same text?
  B. Tanzil Uthmani vs Tanzil simple-clean -> does our normalization turn Uthmani into modern spelling?
  C. corpus.json  vs Tanzil simple-clean  -> what a user typing modern spelling would hit.

Usage: python validate_corpus.py [--show N]
"""
import argparse
import difflib
import json
from collections import Counter
from pathlib import Path

from app.services.verifier import load_corpus, normalize

TANZIL_DIR = Path(__file__).resolve().parent / "data" / "tanzil"
BASMALA_WORDS = 4  # بسم الله الرحمن الرحيم


def load_tanzil(name: str) -> dict[tuple[int, int], str]:
    verses = {}
    for line in (TANZIL_DIR / name).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        sura, ayah, text = line.split("|", 2)
        verses[(int(sura), int(ayah))] = text.strip()
    return verses


def strip_basmala(verses: dict[tuple[int, int], str]) -> dict[tuple[int, int], str]:
    """Tanzil prepends the basmala to ayah 1 of every surah except 1 and 9; our corpus does not."""
    out = {}
    for (sura, ayah), text in verses.items():
        if ayah == 1 and sura not in (1, 9):
            words = text.split()
            assert normalize(" ".join(words[:BASMALA_WORDS])) == "بسم الله الرحمن الرحيم", (sura, text)
            text = " ".join(words[BASMALA_WORDS:])
        out[(sura, ayah)] = text
    return out


def corpus_by_key() -> dict[tuple[int, int], str]:
    out = {}
    for e in load_corpus():
        sura, ayah = e.number.split(":")
        out[(int(sura), int(ayah))] = e.normalized
    return out


def word_diffs(a: str, b: str) -> list[tuple[str, str]]:
    wa, wb = a.split(), b.split()
    pairs = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes():
        if op != "equal":
            pairs.append((" ".join(wa[i1:i2]), " ".join(wb[j1:j2])))
    return pairs


def compare(label: str, left: dict, right: dict, show: int) -> None:
    keys = sorted(set(left) | set(right))
    missing = [k for k in keys if k not in left or k not in right]
    bad = [k for k in keys if k in left and k in right and left[k] != right[k]]
    ok = len(keys) - len(missing) - len(bad)
    print(f"\n{label}: {ok}/{len(keys)} identical, {len(bad)} differ, {len(missing)} missing on one side")
    if missing:
        print("  missing:", missing[:10])
    pair_counts = Counter(p for k in bad for p in word_diffs(left[k], right[k]))
    for (x, y), n in pair_counts.most_common(show):
        print(f"  {n:4d}x  {x!r:30} -> {y!r}")
    if len(pair_counts) > show:
        print(f"  ... {len(pair_counts) - show} more distinct word differences")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", type=int, default=40)
    args = parser.parse_args()

    uthmani = {k: normalize(v) for k, v in strip_basmala(load_tanzil("quran-uthmani.txt")).items()}
    simple = {k: normalize(v) for k, v in strip_basmala(load_tanzil("quran-simple-clean.txt")).items()}
    ours = corpus_by_key()

    compare("A. corpus.json vs Tanzil Uthmani", ours, uthmani, args.show)
    compare("B. Tanzil Uthmani vs Tanzil simple-clean", uthmani, simple, args.show)
    compare("C. corpus.json vs Tanzil simple-clean", ours, simple, args.show)


if __name__ == "__main__":
    main()
