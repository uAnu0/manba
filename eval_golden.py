"""Run the golden set through the verifier and report accuracy and false confirmations.

Headline numbers (known_gap items are reported separately and never fail the run):
  - verified accuracy: items expected `verified` that came back verified with the right source
    (and match_type / other_matches_count where the golden item states them)
  - false confirmations: items expected NOT verified that came back verified (target: 0)
  - status accuracy: every item's status is acceptable

Usage: python eval_golden.py [--golden golden/quran_golden.json] [-v]
Exit code 1 if there is any false confirmation or any non-gap failure.
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from app.services.pipeline import verify_text
from app.services.verifier import verify_segment, verse_index, window_index

DEFAULT_GOLDEN = Path(__file__).resolve().parent / "golden" / "quran_golden.json"


def acceptable_statuses(expect: dict) -> set[str]:
    status = expect["status"]
    if status == "not_verified":
        return {"semantic_variant", "baseless"}
    return set(status) if isinstance(status, list) else {status}


def check(item: dict, result) -> list[str]:
    """Return a list of problems; empty means the item passed."""
    expect, problems = item["expect"], []
    if result.status not in acceptable_statuses(expect):
        problems.append(f"status {result.status!r}, expected {expect['status']!r}")
        return problems
    if result.status != "verified":
        return problems
    if "match_type" in expect and result.match_type != expect["match_type"]:
        problems.append(f"match_type {result.match_type!r}, expected {expect['match_type']!r}")
    src = result.source
    if "source" in expect and (src is None or src.number != expect["source"]):
        problems.append(f"source {src and src.number!r}, expected {expect['source']!r}")
    if "other_matches_count" in expect and (src is None or src.other_matches_count != expect["other_matches_count"]):
        problems.append(
            f"other_matches_count {src and src.other_matches_count}, expected {expect['other_matches_count']}"
        )
    return problems


def check_sermon(item: dict, segments: list) -> list[str]:
    expected = item["expect_segments"]
    if len(segments) != len(expected):
        return [f"{len(segments)} segments, expected {len(expected)}"]
    problems = []
    for i, (exp, seg) in enumerate(zip(expected, segments), start=1):
        for p in check({"expect": exp}, seg):
            problems.append(f"segment {i}: {p}")
    return problems


def run_sermons(sermons: list[dict], verbose: bool) -> int:
    """Whole paragraphs through the pipeline. Returns the number of non-gap failures."""
    if not sermons:
        return 0
    print("\nSermons (full pipeline):")
    failed = 0
    for item in sermons:
        segments = verify_text(item["text"]).segments
        problems = check_sermon(item, segments)
        gap = item.get("known_gap")
        failed += bool(problems) and not gap
        state = "ok" if not problems else ("KNOWN GAP" if gap else "FAIL")
        print(f"  {item['id']:5} {state}  {item.get('note', '')}")
        if problems or verbose:
            for seg in segments:
                src = seg.source.number if seg.source else "-"
                print(f"        got {seg.status}/{seg.match_type} {src}: {seg.segment_text[:50]}")
            for p in problems:
                print(f"        - {p}")
    return failed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("-v", "--verbose", action="store_true", help="print every item, not only failures")
    args = parser.parse_args()

    golden = json.loads(args.golden.read_text(encoding="utf-8"))
    items = golden["items"]
    verse_index(), window_index()  # build indexes outside the timing

    rows, categories = [], defaultdict(lambda: [0, 0])
    t0 = time.time()
    for item in items:
        result = verify_segment(item["text"])
        problems = check(item, result)
        rows.append((item, result, problems))
        if not item.get("known_gap"):
            categories[item["category"]][0] += not problems
            categories[item["category"]][1] += 1
    elapsed = time.time() - t0

    core = [r for r in rows if not r[0].get("known_gap")]
    gaps = [r for r in rows if r[0].get("known_gap")]
    expect_verified = [r for r in core if r[0]["expect"]["status"] == "verified"]
    expect_not = [r for r in core if r[0]["expect"]["status"] != "verified"]

    verified_ok = sum(1 for _, _, p in expect_verified if not p)
    false_confirmations = [r for r in expect_not if r[1].status == "verified"]
    status_ok = sum(1 for _, _, p in core if not p)

    def show(item, result, problems):
        src = result.source.number if result.source else "-"
        print(f"  {item['id']:4} [{item['category']}] {result.status}/{result.match_type} {src} conf={result.confidence}")
        for p in problems:
            print(f"        - {p}")
        if problems and result.differences:
            print(f"        differences: {result.differences[:3]}")
        if item.get("note"):
            print(f"        note: {item['note']}")

    failures = [r for r in core if r[2]]
    if args.verbose:
        print("All items:")
        for r in rows:
            show(*r)
    elif failures:
        print("Failures:")
        for r in failures:
            show(*r)

    print("\nBy category (passed/total):")
    for name, (ok, total) in sorted(categories.items()):
        print(f"  {name:18} {ok}/{total}")

    print(f"\nItems: {len(core)} core + {len(gaps)} known-gap, evaluated in {elapsed:.2f}s")
    print(f"Verified accuracy:   {verified_ok}/{len(expect_verified)} = {verified_ok / max(len(expect_verified), 1):.1%}")
    print(f"False confirmations: {len(false_confirmations)}/{len(expect_not)} (target 0)")
    print(f"Overall pass:        {status_ok}/{len(core)} = {status_ok / max(len(core), 1):.1%}")

    if gaps:
        print("\nKnown gaps (ideal outcome stated; not counted above):")
        for item, result, problems in gaps:
            state = "STILL FAILING" if problems else "now passes"
            print(f"  {item['id']:4} {state}: {item['text']!r}")
            for p in problems:
                print(f"        - {p}")

    sermon_failures = run_sermons(golden.get("sermons", []), args.verbose)
    return 1 if failures or false_confirmations or sermon_failures else 0


if __name__ == "__main__":
    sys.exit(main())
