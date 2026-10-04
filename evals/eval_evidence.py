"""Measure the evidence finder on golden/evidence_golden.json.

For every question and every expected phrase: is it contained in one of the returned Quran / hadith texts?
Reports recall (phrases found) and the share of questions with at least one expected text found, with and without the
optional LLM query expansion.

Usage: python evals/eval_evidence.py [--llm] [--no-meaning] [--limit 8] [-v]
The LLM run needs OPENROUTER_API_KEY (from .env) and costs about one cheap call per question.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root holds the app package

import argparse
import asyncio
import json
from pathlib import Path

from app.services.evidence_card import build_card
from app.services.verifier import load_corpus, normalize

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "evidence_golden.json"


def contains(texts: list[str], phrase: str) -> bool:
    needle = normalize(phrase)
    return any(needle in text for text in texts)


async def run(use_llm: bool, use_meaning: bool, limit: int, verbose: bool) -> None:
    questions = json.loads(GOLDEN.read_text(encoding="utf-8"))["questions"]
    corpus = load_corpus()
    quran_all = [e.normalized for e in corpus if e.classification == "quran"]
    hadith_all = [normalize(e.text) for e in corpus if e.classification == "hadith"]
    # Sanity: every expected phrase must exist somewhere in the corpus, or the question is mis-specified.
    for q in questions:
        for kind, pool in (("quran", quran_all), ("hadith", hadith_all)):
            for phrase in q[kind]:
                if not contains(pool, phrase):
                    print(f"  note: {q['id']} {kind} phrase not found anywhere in the corpus: {phrase}")

    found = total = answered = with_expected = 0
    suggested = confirmed = 0
    for q in questions:
        card = await build_card(q["question"], use_llm=use_llm, use_meaning=use_meaning)
        shown = card.quran + card.hadith  # the card as a user would see it
        texts = [normalize(i.full_text) for i in shown]
        suggested += card.query.suggested
        confirmed += card.query.found_in_corpus
        expected = [("quran", p) for p in q["quran"]] + [("hadith", p) for p in q["hadith"]]
        hits = [(k, p, contains(texts, p)) for k, p in expected]
        found += sum(h for _, _, h in hits)
        total += len(hits)
        if hits:
            with_expected += 1
            answered += any(h for _, _, h in hits)
        if verbose or not all(h for _, _, h in hits):
            status = ", ".join(f"{k}:{'ok' if h else 'MISS'}" for k, _, h in hits)
            note = f"  recalled {card.query.found_in_corpus}/{card.query.suggested}" if use_llm else ""
            print(f"{q['id']} {q['question']}  [{status}]{note}")
            if verbose and use_llm:
                for r in card.query.rejected:
                    print(f"      not in corpus: {r[:90]}")
    print(f"\nLLM recall + corpus check: {'on' if use_llm else 'off'}, top {limit} Quran + top {limit} hadith")
    print(f"expected texts found: {found}/{total} = {found / max(total, 1):.0%}")
    print(f"questions with at least one expected text found: {answered}/{with_expected} = {answered / max(with_expected, 1):.0%}")
    if use_llm:
        print(f"recited texts confirmed in the corpus: {confirmed}/{suggested} = {confirmed / max(suggested, 1):.0%}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="also let the LLM recite evidence")
    parser.add_argument("--no-meaning", action="store_true", help="keyword search only (plus --llm if given)")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.llm, not args.no_meaning, args.limit, args.verbose))
