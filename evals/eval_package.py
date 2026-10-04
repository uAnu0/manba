"""Run the organizers' test cases (golden/package_cases.json) through the claim check. Needs a model key.

    python evals/eval_package.py [-v]

Each applicable case has one check:
  not_supported            the claim is not reported as supported
  personal_referral        refer_to_scholar, content level د
  quote_not_verified       a quote check in which nothing is verified
  quote_variant_with_source  the altered verse is reported as differing, with the right sura:ayah
  fiqh_disputed            the fiqh check reports disagreement (content level ج)
  supported_or_partial     supported or supported in part
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root holds the app package

import asyncio
import json
import sys
from pathlib import Path

from app.services.claim_card import verify_claim

ROOT = Path(__file__).resolve().parents[1]
DISPUTED = {"consensus_claim_disputed", "stated_as_certain_disputed", "partly_disputed", "disagreement_acknowledged"}


def passes(case: dict, r) -> tuple[bool, str]:
    check = case["check"]
    segs = r.quote_check.segments if r.quote_check else []
    if check == "not_supported":
        return r.outcome not in ("supported", "supported_in_part", "supported_weakly"), r.outcome
    if check == "personal_referral":
        return r.outcome == "refer_to_scholar" and r.content_level == "د", f"{r.outcome} level={r.content_level}"
    if check == "quote_not_verified":
        return r.outcome == "quote_checked" and not any(s.status == "verified" for s in segs), f"{r.outcome} {[s.status for s in segs]}"
    if check == "quote_variant_with_source":
        ok = any(s.status == "semantic_variant" and s.source and s.source.number == case["expect_ref"] for s in segs)
        return ok, f"{r.outcome} {[(s.status, s.source.number if s.source else None) for s in segs]}"
    if check == "fiqh_disputed":
        status = r.fiqh.status if r.fiqh else None
        return status in DISPUTED and r.content_level == "ج", f"fiqh={status} level={r.content_level}"
    if check == "supported_or_partial":
        return r.outcome in ("supported", "supported_in_part"), r.outcome
    return False, f"unknown check {check}"


async def main(verbose: bool) -> int:
    cases = json.loads((ROOT / "golden" / "package_cases.json").read_text(encoding="utf-8"))["cases"]
    run = [c for c in cases if c.get("applies", True)]
    ok = 0
    for c in run:
        r = await verify_claim(c["input"], use_llm=True)
        good, why = passes(c, r)
        ok += good
        print(f"{'ok ' if good else 'XX '}{c['id']} {c['check']:26} {why}   | {c['input']}")
        if verbose and r.llm.error:
            print("     model error:", r.llm.error)
    skipped = [c["id"] for c in cases if not c.get("applies", True)]
    print(f"\npassed {ok}/{len(run)} applicable cases; not applicable to Track 4: {', '.join(skipped)}")
    return 0 if ok == len(run) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main("-v" in sys.argv)))
