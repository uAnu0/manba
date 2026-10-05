"""Quotes in another language against the official translations (services/foreign.py).

Usage: python evals/eval_translations.py [-v]
Target: no false verification (a changed or invented quote shown as verified).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root holds the app package

import json

from app.services.foreign import match_quote

CASES = json.loads((Path(__file__).resolve().parents[1] / "golden" / "translations.json").read_text(encoding="utf-8"))


def main(verbose: bool) -> None:
    ok = false_verified = 0
    for c in CASES:
        seg = match_quote(c["quote"], c["lang"], c.get("hint", ""), tuple(c["ref"]) if c.get("ref") else None)
        where = None
        if seg.source:
            where = seg.source.number if seg.classification == "quran" else f"{seg.source.book}|{seg.source.number}"
        want = c.get("source")
        place_ok = want is None or where in want.split("|") or where == want
        if c["expect"] == "any_found":
            good = seg.status != "baseless" and place_ok
        else:
            good = seg.status == c["expect"] and (seg.status == "baseless" or place_ok)
        if seg.status == "verified" and c["expect"] not in ("verified", "any_found"):
            false_verified += 1
        ok += good
        if verbose or not good:
            print(("ok " if good else "XX ") + f"{c['id']} {seg.status:16} {where or '-':22} {seg.confidence:.2f} | {c['quote']}")
    print(f"\ncases passed: {ok}/{len(CASES)}")
    print(f"false verifications (target 0): {false_verified}")


if __name__ == "__main__":
    main("-v" in sys.argv)
