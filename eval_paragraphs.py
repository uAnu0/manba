"""Run golden/paragraphs_golden.json through the paragraph check.

For each paragraph: is every expected claim found (and checked with an acceptable outcome), is every expected quote
found with the right status, was commentary wrongly checked as a claim, and were claims invented where there are none.
A REVERSAL (a claim that must be contradicted shown as supported, or the other way round) is the worst error: target 0.

Needs an OpenRouter key. Usage: python eval_paragraphs.py [-v]
"""
import argparse
import asyncio
import json
from pathlib import Path

from app.services.text_claims import check_text

GOLDEN = Path(__file__).resolve().parent / "golden" / "paragraphs_golden.json"
SUPPORT = {"supported", "supported_weakly", "supported_in_part"}


async def main(verbose: bool) -> int:
    paragraphs = json.loads(GOLDEN.read_text(encoding="utf-8"))["paragraphs"]
    found = total = quotes_ok = quotes_total = commentary_checked = reversals = extra_claims = 0
    for p in paragraphs:
        r = await check_text(p["text"])
        claims = [i for i in r.items if i.kind == "claim"]
        quotes = [i for i in r.items if i.kind == "quote"]
        print(f"\n{p['id']}: {len(claims)} claims, {len(quotes)} quotes, {r.commentary_sentences} commentary sentences, error={r.llm.error}")
        for want in p["claims"]:
            total += 1
            match = next((i for i in claims if want["contains"] in i.text), None)
            if match is None:
                print(f"  MISSING claim: {want['contains']}")
                continue
            ok = match.result.outcome in want["outcome"]
            found += ok
            if not ok:
                print(f"  WRONG outcome {match.result.outcome} for {want['contains']} (expected {want['outcome']})")
            if (match.result.outcome in SUPPORT and "contradicted" in want["outcome"] and not set(want["outcome"]) & SUPPORT) or (
                match.result.outcome == "contradicted" and set(want["outcome"]) <= SUPPORT
            ):
                reversals += 1
                print(f"  REVERSAL: {want['contains']}")
            elif verbose and ok:
                print(f"  ok   {match.result.outcome:16} {want['contains']}")
        for want in p["quotes"]:
            quotes_total += 1
            match = next((i for i in quotes if want["contains"] in i.text), None)
            ok = match is not None and match.quote.status in want["status"]
            quotes_ok += ok
            if not ok:
                print(f"  QUOTE problem: {want['contains']} -> {match.quote.status if match else 'not found'} (expected {want['status']})")
        for word in p["commentary"]:
            bad = [i for i in r.items if word in i.text]
            commentary_checked += len(bad)
            for i in bad:
                print(f"  COMMENTARY checked as {i.kind}: {i.text[:60]}")
        extra_claims += max(0, len(claims) - len(p["claims"])) if p.get("max_claims") == 0 else 0
    print(f"\nclaims found and right: {found}/{total}")
    print(f"quotes right:           {quotes_ok}/{quotes_total}")
    print(f"commentary checked (target 0): {commentary_checked}")
    print(f"claims invented in claim-free text (target 0): {extra_claims}")
    print(f"reversals (target 0):   {reversals}")
    return 1 if reversals else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    raise SystemExit(asyncio.run(main(parser.parse_args().verbose)))
