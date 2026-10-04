# Changelog: challenge days (4 to 6 October 2026)

Everything before tag `v0-baseline` is the declared starting version (see `BASELINE.md`). Times are Riyadh time.

## Sunday 4 October (day 1)

**Fiqh check: disputed questions stated as settled, claimed consensus**
- `ingest_fiqh.py` builds `data/fiqh/kuwaiti.jsonl.gz`: the Kuwaiti Fiqh Encyclopedia (45 volumes) as 26,363 numbered paragraphs across 1,619 entries,
  each with volume, page, entry, section and its own heading.
- `app/services/fiqh.py`: how a sentence states a ruling (consensus / flat / hedged), search over the encyclopedia (text plus headings), optional model step
  limited to "same issue or not" and copying the passage's ruling sentence (verified to occur in the passage), agreement or disagreement read by code
  from the encyclopedia's wording, schools' positions quoted verbatim, citation to volume and page. Never a fatwa or a preference between opinions.
- `POST /api/fiqh`; also runs inside `/api/claim` and `/api/check` for sentences worded as fiqh rulings, including the local-only mode.
- `golden/fiqh_golden.json` + `eval_fiqh.py`: keyword mode 11/11 acceptable, expected entry shown 9/9, false_settled 0.

**Content levels of the scientific pack (أ ب ج د)**
- `app/services/levels.py`; `content_level` on every quote segment, claim result and paragraph item; counts in `/api/check` summary.

**Dorar gradings**
- `app/services/dorar.py` + `GET /api/dorar`: parser for Dorar's API result (narrator, scholar, book, page, ruling), tested on a real response.
- Result cards get a Dorar tab for hadith and for attributed quotes that were not found. Dorar refuses data-centre addresses, so the page asks Dorar from
  the reader's browser (JSONP) and falls back to the server endpoint. Rulings shown verbatim per scholar; disagreement flagged; never merged.

**Interface**
- Level badge and fiqh flag on every card; Fiqh tab (outcome, the passage's ruling sentence, schools' positions, full paragraph, citation, notice);
  level counts above the cards; AI-written explanation labelled as generated and not a source text; AI-transparency and privacy notes on the claim page.

**Fixes**
- Local-only paragraph check: a sentence attributing words to the Prophet or to God that matches nothing is now shown as "not found" instead of disappearing.

**Tests and docs**
- `golden/package_cases.json` + `eval_package.py`: the organizers' test table as it applies to Track 4 (needs a model key to run).
- README sections for the fiqh check, levels, Dorar, test cases, transparency; `BASELINE.md`.
- Quote golden set unchanged: verified 51/51, false confirmations 0/25.

## Open items for the team

- Run `python eval_fiqh.py --llm` and `python eval_package.py -v` with the team key and record the numbers here.
- Test the Dorar tab from a normal browser connection (it cannot be tested from a data-centre machine).
- Known baseline gap seen today: "وقال: إنما الأعمال بالنيات" (attribution with no named speaker) is not verified, while the bare text is.
- Before going public: decide how the hadith corpus ships (build at deploy time from the pinned sources, or limit to the Unlicense data).
- A Sharia mentor to review `golden/fiqh_golden.json` and the wording of the fiqh outcomes.
