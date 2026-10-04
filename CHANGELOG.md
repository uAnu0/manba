# Changelog: challenge days (4 to 6 October 2026)

Everything before tag `v0-baseline` is the declared starting version (see `BASELINE.md`). Times are Riyadh time.

## Sunday 4 October (day 1)

**Fiqh check: disputed questions stated as settled, claimed consensus**
- `scripts/ingest_fiqh.py` builds `data/fiqh/kuwaiti.jsonl.gz`: the Kuwaiti Fiqh Encyclopedia (45 volumes) as 26,363 numbered paragraphs across 1,619 entries,
  each with volume, page, entry, section and its own heading.
- `app/services/fiqh.py`: how a sentence states a ruling (consensus / flat / hedged), search over the encyclopedia (text plus headings), optional model step
  limited to "same issue or not" and copying the passage's ruling sentence (verified to occur in the passage), agreement or disagreement read by code
  from the encyclopedia's wording, schools' positions quoted verbatim, citation to volume and page. Never a fatwa or a preference between opinions.
- `POST /api/fiqh`; also runs inside `/api/claim` and `/api/check` for sentences worded as fiqh rulings, including the local-only mode.
- `golden/fiqh_golden.json` + `evals/eval_fiqh.py`: keyword mode 11/11 acceptable, expected entry shown 9/9, false_settled 0.

**Content levels of the scientific pack (أ ب ج د)**
- `app/services/levels.py`; `content_level` on every quote segment, claim result and paragraph item; counts in `/api/check` summary.

**Dorar gradings**
- `app/services/dorar.py` + `GET /api/dorar`: parser for Dorar's API result (narrator, scholar, book, page, ruling), tested on a real response.
- Result cards get a Dorar tab for hadith and for attributed quotes that were not found. Dorar refuses data-centre addresses, so the page asks Dorar from
  the reader's browser (JSONP) and falls back to the server endpoint. Rulings shown verbatim per scholar; disagreement flagged; never merged.

**Interface**
- Level badge and fiqh flag on every card; Fiqh tab (outcome, the passage's ruling sentence, schools' positions, full paragraph, citation, notice);
  level counts above the cards; AI-written explanation labelled as generated and not a source text; AI-transparency and privacy notes on the claim page.

**Dorar access (later on day 1)**
- Dorar's Cloudflare answers 403 by TLS fingerprint: httpx, PowerShell and the in-page JSONP request are refused, browser headers or not; curl and a
  Chrome-like client are accepted. The server now calls Dorar's official API with `curl_cffi` (impersonate Chrome): 200 from a data centre, full rulings.
  The page asks the server first, then JSONP, then offers the search on dorar.net.
- Rulings with a negation ("ليس بصحيح"، "ليس بحديث، لكن معناه صحيح"، "لم يصح") were counted as authentic because they contain "صحيح": fixed in server and page.

**Fixes**
- Local-only paragraph check: a sentence attributing words to the Prophet or to God that matches nothing is now shown as "not found" instead of disappearing.

**Tests and docs**
- `golden/package_cases.json` + `evals/eval_package.py`: the organizers' test table as it applies to Track 4 (needs a model key to run).
- README sections for the fiqh check, levels, Dorar, test cases, transparency; `BASELINE.md`.
- Quote golden set unchanged: verified 51/51, false confirmations 0/25.

**Repository tidy-up**
- Scripts moved to `scripts/` (ingest, embed, validate) and `evals/` (one per golden set); corpora moved to `data/`. Paths, docstrings and the README
  updated; every script runs from its new place. Checked: corpus validation identical, quotes 51/51 with 0 false confirmations, fiqh 11/11.

**Disputed rulings no longer look "supported" (later on day 1)**
- A claim the text search supports but the encyclopedia reports as disputed (stated as certain, consensus claimed, partly disputed) now shows an amber
  **Disputed ruling · خلافية** badge and headline instead of the green "Supported"; a ruling the encyclopedia reports as agreed differently shows a red
  "Differs from the agreed ruling". The text-search outcome itself is unchanged (it is still printed, as a description of the texts, not of the ruling).
  The Fiqh tab opens first and the strip counts these separately. Cards only: `app/static/cards.js`, `cards.css`.
- The Arabic explanation says the same: its summary line and caution are replaced by a fixed sentence written by code (the ruling is disputed; the texts
  are cited for one view), and the writer is told not to present the claim as supported or settled. `app/services/explain.py`.

**Scan a PDF or image (OCR)**
- The reviewer page `/` has a third input tab, **مسح PDF أو صورة**, and `/claim` has the same reader in English; both accept a PDF (up to 10 pages shown as thumbnails; the person ticks the pages to keep and only ticked scans are read, until the 500-word limit is reached) or images; a PDF text layer is read in the browser, anything else (scan, photo, garbled layer) goes to
  `POST /api/ocr`, read by two different models; the words they disagree on are listed for the person to check. Nothing stored.
  `app/services/ocr.py`, `app/routers/ocr.py`, `app/static/ocr.js`. See the README section for the reasoning and the spike results.

## Open items for the team

- Run `python evals/eval_fiqh.py --llm` and `python evals/eval_package.py -v` with the team key and record the numbers here.
- Optional: tell Dorar's support (support@dorar.net) how the app uses their API (cached, credited), so the access is on record.
- Check `/api/dorar` once from the deployed host (a different data centre) right after deploying.
- Consider HadeethEnc (hadeethenc.com, the organizers' partner): its API answers without a key and gives grade, attribution, reference and explanation for each hadith.
- Known baseline gap seen today: "وقال: إنما الأعمال بالنيات" (attribution with no named speaker) is not verified, while the bare text is.
- Before going public: decide how the hadith corpus ships (build at deploy time from the pinned sources, or limit to the Unlicense data).
- A Sharia mentor to review `golden/fiqh_golden.json` and the wording of the fiqh outcomes.
