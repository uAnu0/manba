"""Run golden/claims_golden.json through the claim verifier and report accuracy and, above all, reversals.

For each claim: is the claim type right, is the outcome one of the acceptable ones, and (for quotes) are the quoted
segments' statuses right. A REVERSAL is a claim shown as contradicted that should be supported, or shown as supported
(or supported_weakly) that should be contradicted: the worst error, the target is 0. A claim that must not be
supported (golden outcome contradicted / no_clear_evidence) but comes back supported is a false support, also 0.

Needs an OpenRouter key (about 4 model calls per claim). Usage: python eval_claims.py [-v] [--concurrency 3]
"""
import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from app.services.claim_card import verify_claim

GOLDEN = Path(__file__).resolve().parent / "golden" / "claims_golden.json"
SUPPORT = {"supported", "supported_weakly", "supported_in_part"}


async def main(verbose: bool, concurrency: int) -> int:
    claims = json.loads(GOLDEN.read_text(encoding="utf-8"))["claims"]
    sem = asyncio.Semaphore(concurrency)

    async def run(c):
        async with sem:
            try:
                return await verify_claim(c["claim"])
            except Exception as exc:  # a crash is a failure of its own
                return exc

    results = await asyncio.gather(*(run(c) for c in claims))
    type_ok = outcome_ok = quote_ok = quote_total = reversals = false_support = errors = 0
    by_outcome = Counter()
    print(f"{'id':4} {'type':13} {'outcome':18} expected")
    for c, r in zip(claims, results):
        if isinstance(r, Exception):
            errors += 1
            print(f"{c['id']:4} CRASH {type(r).__name__}: {r}")
            continue
        expected = c["outcome"] if isinstance(c["outcome"], list) else [c["outcome"]]
        t_ok, o_ok = r.claim_type == c["type"], r.outcome in expected
        type_ok += t_ok
        outcome_ok += o_ok
        problems = []
        if not t_ok:
            problems.append(f"type {r.claim_type}, expected {c['type']}")
        if not o_ok:
            problems.append(f"outcome {r.outcome}, expected {expected}")
        if r.outcome in SUPPORT and "contradicted" in expected and not set(expected) & SUPPORT:
            reversals += 1
            problems.append("REVERSAL")
        if r.outcome == "contradicted" and "supported" in expected:
            reversals += 1
            problems.append("REVERSAL")
        if r.outcome in SUPPORT and not set(expected) & SUPPORT:
            false_support += 1
        if "quote_status" in c:
            quote_total += 1
            statuses = [s.status for s in (r.quote_check.segments if r.quote_check else [])]
            ok = bool(statuses) and all(s in c["quote_status"] for s in statuses)
            quote_ok += ok
            if not ok:
                problems.append(f"quote statuses {statuses}, expected {c['quote_status']}")
        if r.llm.error:
            problems.append(f"llm error: {r.llm.error[:120]}")
        by_outcome[r.outcome] += 1
        if verbose or problems:
            print(f"{c['id']:4} {r.claim_type:13} {r.outcome:18} {expected}  {c['claim'][:40]}  {'; '.join(problems)}")
    n = len(claims) - errors
    print(f"\nclaims: {len(claims)} ({errors} crashed)")
    print(f"claim type right:         {type_ok}/{n}")
    print(f"outcome acceptable:       {outcome_ok}/{n}")
    print(f"quote statuses right:     {quote_ok}/{quote_total}")
    print(f"reversals (target 0):     {reversals}")
    print(f"false support (target 0): {false_support}")
    print("outcomes given:", dict(by_outcome))
    return 1 if reversals or false_support or errors else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.verbose, args.concurrency)))
