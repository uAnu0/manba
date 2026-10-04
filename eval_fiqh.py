"""Measure the fiqh check on golden/fiqh_golden.json.

    python eval_fiqh.py           # keyword mode (no model, no key)
    python eval_fiqh.py --llm     # with the model step (about one call per item)

Reports: status acceptable, the expected encyclopedia entry among the passages shown, and false_settled (a question the
encyclopedia reports as disputed shown as agreed: target 0). Exit code 1 if false_settled > 0.
"""
import asyncio
import json
import sys
from pathlib import Path

from app.services.fiqh import fiqh_check

ROOT = Path(__file__).resolve().parent


async def main(use_llm: bool) -> int:
    items = json.loads((ROOT / "golden" / "fiqh_golden.json").read_text(encoding="utf-8"))["items"]
    ok = entry_hits = entry_total = false_settled = 0
    for it in items:
        r = await fiqh_check(it["claim"], use_llm=use_llm)
        accept = it["accept"] + ([] if use_llm else it.get("accept_keywords", []))
        good = r.status in accept
        ok += good
        if it["where"]:
            entry_total += 1
            want = it["where"].rsplit(" ", 1)[0]
            hit = any(p.entry == want for p in r.passages)
            entry_hits += hit
        else:
            hit = None
        settled = it["disputed"] and r.status in ("agreement_reported", "found_no_marker")
        false_settled += settled
        mark = "ok " if good else "XX "
        top = r.passages[0].cite if r.passages else "-"
        print(f"{mark}{it['id']} {r.status:28} {'' if hit is None else ('entry ok' if hit else 'entry MISSING'):13} {it['claim']}  |  {top}")
        if settled:
            print("     FALSE SETTLED: a disputed question shown as agreed")
    print(f"\nmode: {'model' if use_llm else 'keywords'}")
    print(f"status acceptable: {ok}/{len(items)}")
    print(f"expected entry shown: {entry_hits}/{entry_total}")
    print(f"false_settled: {false_settled} (target 0)")
    return 1 if false_settled else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--llm" in sys.argv)))
