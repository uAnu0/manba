# Manba

Verification service for Islamic text. It takes raw text (a sentence or a whole sermon), finds the Quran verses and hadith in it,
and checks each against local corpora: word for word, with the source, and an exact account of what differs when a quote is altered.
A language model is optional and only *finds* candidate quotes; it never decides a verdict.

Code: MIT (`LICENSE`). Data: each file keeps its source's terms; the register of sources, tools and licences, with what is not yet verified, is `SOURCES.md` (سجل المصادر والتراخيص).
What existed before the challenge days is declared in `BASELINE.md` (tag `v0-baseline`); what was built from 4 October is in `CHANGELOG.md`.

## Quick start

Requires Python 3.12.

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # optional: only OPENROUTER_API_KEY is needed, for LLM extraction
uvicorn app.main:app --reload
```

- Test console (throwaway page): http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/docs
- Startup takes about 10 s (it builds the search indexes) and about 300 MB of memory.

`.env` is git-ignored. Never commit a key. Ask the owner for the OpenRouter key; without it everything works except `use_llm`.

## Keys and access (local and Vercel)

LLM extraction (`use_llm`) needs an OpenRouter key. There are two ways to provide one, and both can be used together:

1. **Shared team key (server side).** Set the environment variable `OPENROUTER_API_KEY` where the app runs. Locally that is `.env`; on Vercel
   it is Project Settings, Environment Variables: add `OPENROUTER_API_KEY` (tick Production, and Preview if you use it, and mark it Sensitive),
   then **redeploy**, because a running deployment does not see new variables. CLI alternative: `vercel env add OPENROUTER_API_KEY production`.
   The key stays on the server and is never sent to browsers.
2. **Your own key (per request).** In the test console open Settings and paste your key. It is kept in your browser only and sent with each request
   in the `X-OpenRouter-Key` header; the server uses it for that call and never stores or logs it. A key sent this way takes priority over the shared one.

**Protect a deployed app.** With a shared key on a public URL, anyone who finds the URL can spend your OpenRouter credit. Also set
`API_ACCESS_TOKEN` (any long random string) in the same place. `POST /api/verify` then answers 401 unless the request carries it in the
`X-Access-Token` header; the test console has an access-code field in Settings. Share the code with teammates directly, not in the repo.
`GET /api/config` reports only whether a code is required and whether the server has a shared key.

Heads-up for serverless hosting: at startup the app loads about 48,000 corpus entries and builds its search indexes (about 10 s, about 300 MB).
On Vercel give the function enough memory and duration, and expect a slow first request after a cold start.

## Fiqh check (challenge day 1)

`POST /api/fiqh` with `{"claim": "...", "use_llm": true}`, and automatically inside `/api/claim` and `/api/check` for any sentence worded as a fiqh
ruling. It answers one question the scientific pack makes binding: **is a disputed question being stated as settled, or a consensus claimed that the
sources do not report?** It never says which opinion is right.

1. **How the sentence is worded** (code): a claimed consensus (أجمع، بالإجماع، اتفق العلماء، لا خلاف، متفقون), a flat ruling (حرام، واجب، لا يجوز، سنة، ينقض ...),
   or a hedged one (عند الجمهور، على الراجح، في قول، عند الحنفية ...). A sentence with no ruling word is not a fiqh claim.
2. **Where the encyclopedia discusses it**: BM25 over the 26,363 numbered paragraphs of the Kuwaiti Fiqh Encyclopedia (45 volumes, built by
   `python scripts/ingest_fiqh.py` into `data/fiqh/kuwaiti.jsonl.gz`), with a second index over entry names and paragraph headings ("زكاة الحلي").
3. **Which passages are about the same issue** (model, optional): it may only say same issue or not, copy the passage's own ruling sentence (the copy must
   occur in the passage, or it is dropped), and say whether the person's ruling is one the passage reports. It writes no ruling.
4. **Agreement or disagreement** (code, never the model): read from the encyclopedia's fixed wording (اتفق الفقهاء، أجمعوا، بلا خلاف / اختلف الفقهاء، ذهب ... وذهب،
   خلافًا لـ، في رواية). The schools' positions are the passage's own sentences that name الحنفية، المالكية، الشافعية، الحنابلة، الجمهور, quoted verbatim, with volume, page and paragraph.
5. **Outcome**: `consensus_claim_disputed`, `stated_as_certain_disputed`, `disagreement_acknowledged`, `agreement_reported`, `agreement_differs`,
   `partly_disputed`, `found_no_marker`, `not_found` (nothing concluded, refer to a specialist). Without a model the best keyword match is shown and labelled so.

Measured on `golden/fiqh_golden.json` (11 sentences written from the encyclopedia's wording; needs a scholar's review) in keyword mode, no model:
status acceptable 11/11, the expected entry shown 9/9, **false_settled 0** (no disputed question shown as agreed). Run `python evals/eval_fiqh.py [--llm]`.
Startup cost: about 8 s and 190 MB more memory.

## Content levels (challenge day 1)

Every quote segment, claim result and paragraph item carries `content_level`, the level of the scientific pack: **أ** settled text (Quran, authentic hadith),
**ب** explanation with the reference shown, **ج** disputed or sensitive (disagreement stated, or referral), **د** personal case or fatwa (referral only).
Nothing that was not found gets a level. Rules: `app/services/levels.py`. `/api/check` counts them in `summary` (`level_أ` ...), next to the fiqh flags (`fiqh_<status>`).

## Dorar gradings (challenge day 1)

The pack's rule: no hadith is attributed without a source and an approved grading. The local corpus has no grading for about 4,800 hadith (Musnad Ahmad,
al-Darimi) and covers nine books. A card with a hadith, or with words attributed to the Prophet that were not found, has a **Dorar** tab: it searches Dorar's
hadith encyclopedia (about 300,000 hadith) and lists each narration with its scholar, book, page and ruling **as Dorar gives them**, flags when the rulings
differ, and never merges them into one grade. Dorar's Cloudflare decides by the TLS fingerprint of the request (Python httpx,
PowerShell and the in-page JSONP request all get 403, with browser headers or not), so the server calls Dorar's official API with `curl_cffi`
impersonating Chrome, which gets the API's normal answer from a data centre too (`GET /api/dorar?q=...`, `app/services/dorar.py`, cached a day).
If that fails the page tries JSONP, then offers the same search on dorar.net. Rulings with a negation ("ليس بصحيح", "ليس بحديث") are never
counted as authentic. The parser is tested on a real Dorar response (`tests/fixtures/dorar_sample.json`).

## Organizers' test cases

`golden/package_cases.json` holds the test table of the scientific pack (page 6) as it applies to Track 4: the input Manba gets, the pack's expected
behaviour, and a check. Cases for a conversational or translation product are listed as not applicable, with the reason. `python evals/eval_package.py -v` (needs a model).

## Transparency and privacy

The claim page states that Manba is an AI-assisted tool, not a scholar; that it issues no fatwa and prefers no opinion; that AI-written explanations are
labelled and kept apart from source texts; and what happens to the text a person enters (sent for checking, not stored; keys stay in the browser; the Dorar
tab contacts dorar.net from the browser).

## Paragraph check (version 0)

`POST /api/check` with `{"text": "..."}` (up to 12,000 characters) finds every quote and every religious claim in a paragraph or sermon and checks each one. The `/claim` page uses it
automatically when the text has several sentences.

1. **Quotes** are found locally (quote finder + verifier, no model), including bracketed or attributed texts that match nothing (shown as not found).
2. **Claims**: the remaining sentences go to the model once; it says which make a religious claim and copies the claim text (a sentence with several claims is split; a piece that does not name its
   subject gets it from the same sentence). Nothing it writes is trusted: a returned claim must occur in its sentence, or be a faithful trim of it (every word from the sentence, in order, no negation dropped);
   otherwise the whole sentence is the claim. Commentary, greetings, questions and personal stories are skipped.
3. Each claim goes through the claim check (up to 8 per request, 5 at a time); the response lists the items in reading order with a count per outcome and the number of commentary sentences.

Measured on `golden/paragraphs_golden.json` (4 paragraphs written by the developer): 9 of 10 expected claims found with an acceptable outcome, 3/3 quotes right, no commentary checked as a claim,
no claim invented in claim-free text, 0 reversals. The miss is the weak spot of the stance judge (a claim about keeping covenants came back `mixed`). Run `python evals/eval_paragraphs.py`.

**Speed.** Model calls that do not depend on each other run at the same time (the router, the evidence search and the recitation; the recitation of verses and of hadith; the stance judging of the
candidates in chunks of 10), and repeated calls are cached in memory (`services/cache.py`). A single claim went from about 21 s to about 9 s with the same results on the golden claims
(reversals 0, false support 0); a repeated claim is instant; a paragraph with five claims takes about 14 s. The evidence card's relevance judge is NOT chunked: chunking it lowered the recall
of the golden evidence questions by about 5 points (69% to 64%), so it still judges all candidates in one call.

## Claim check (version 0)

The point of the app is checking claims, so this is where everything else comes together. `POST /api/claim` with `{"claim": "..."}` (any language) returns where the
evidence stands: never "true" or "false". Test page: `/claim`.

1. **Route** (LLM): is it a *quote* (a verse or hadith, or words attributed to God or the Prophet), a *topic* claim ("Islam forbids X"), a *personal* question, or *not religious*?
   A text that is itself in the corpus is always treated as a quote.
2. **Quote** -> the quote verifier (levels, sources, gradings, what differs). **Personal** -> "ask a scholar". **Not religious** -> out of scope.
3. **Topic** -> evidence for the claim *and* for its opposite is gathered with the evidence finder (meaning + keyword + recitation). The model grades every candidate text as
   supports / contradicts / related / unrelated against the person's own words. A text may only count as support or contradiction if it names the claim's subject
   (key terms from the router, else the claim's rare words): this is what stops an invented claim such as "Islam forbids tomatoes" from being "supported" by verses about food in general.
4. **Outcome** from the two sides, weighted by source strength (Quran and Sahih al-Bukhari/Muslim 3, sahih 2, hasan 1.5, disputed 1, weak or ungraded 0.5): `supported`,
   `supported_weakly` (only weak or ungraded hadith), `supported_in_part` (texts cover some parts of a multi-part claim, each text shows which; nothing covers all of it), `contradicted`, `mixed` (comparable weight on both sides), `no_clear_evidence`. A lone text on the other side does not make a clear case "mixed"; it is shown with a note.
   Sensitive topics add a "ask a scholar" banner.

Every source carries its level (1 Quran, 2 Sahih al-Bukhari / Sahih Muslim, 3 other hadith) and strength (`quran`, `sahihayn`, `sahih`, `hasan`, `daif`, `disputed`, `ungraded`) with the gradings scholars gave.
Without a model (`use_llm: false`) only the quote check and the nearest texts are returned (`evidence_only`).

Measured on `golden/claims_golden.json` (30 claims written by the developer: 20 topic, 5 quotes, 2 personal, 2 not religious, 1 invented; run twice, same result):
claim type right 30/30, outcome acceptable 27/30, quote statuses 5/5, **reversals 0, false support 0**. The three misses are on the cautious side (one `mixed`, one `supported_weakly`, one `no_clear_evidence`).
Run `python evals/eval_claims.py -v` to re-measure (about 4 model calls per claim). This is a smoke test: a scholar must review the claims and expected outcomes before anyone relies on it.
A claim takes 15-40 seconds with the model (routing, recitation, two judging calls).

## Evidence finder (version 0)

`POST /api/evidence` with `{"question": "...", "use_llm": true}` returns the Quran verses and hadith that bear on a topic, each with its source,
an excerpt (a hadith without its chain of narrators), the full text, and the gradings scholars gave it (when the dataset has them).
It also returns `refer_to_scholar` with a reason (sensitive topics such as family law, finance and medicine; personal situations; no clear evidence)
and a notice that this is evidence, not a ruling. Test page: `/evidence`.

How it finds texts. Three searches run and their rankings are merged; only corpus text is ever shown:
1. **Meaning search** (always, when `data/corpus_embeddings.npz` and an OpenRouter key are available): every verse and hadith was turned into a vector once
   (`python scripts/embed_corpus.py`, model `google/gemini-embedding-001`, 768 numbers per text, about 37 MB); the question is embedded at request time and the
   nearest texts are taken. It finds "من قتل نفسه" for a question about suicide, which keywords cannot.
2. **Keyword search** (always): BM25 over normalized, lightly stemmed Arabic; hadith are searched without their chain of narrators.
3. **LLM step** (`use_llm`): the model *recites* the evidence it knows (each recitation is looked up in the corpus; unconfirmed ones are discarded and
   listed in `query.rejected`), then **judges every retrieved candidate** as direct / related / unrelated and says whether the question is about Islam at all.
   Unrelated texts are dropped, "related" ones are shown only when fewer than three are direct, and an off-topic question (`in_scope: false`) gets no texts.
   The model only grades numbered texts it is shown; it writes no evidence and no ruling.

Measured on `golden/evidence_golden.json` (25 questions, 36 expected texts, written by the developer) with the card as shown (8 verses + 10 hadith):
keywords only 22% of the expected texts (32% of the questions); meaning + keywords 47% (60%); with the LLM step 72% (84%).
Precision (how many shown texts are really relevant) is not measured yet. That is a baseline on a small set, not a quality bar: it needs scholar-reviewed questions. Run `python evals/eval_evidence.py [--llm] [--no-meaning]` to re-measure.
Memory with everything loaded is about 510 MB and startup about 20 s (the indexes are built at first use).

## Arabic explanation (on demand)

`POST /api/explain` with `{claim, result}` (a claim result) or `{claim, segment}` (a checked quote). The UI shows an **Explain** button under each
result; nothing is written until it is clicked. A cheap writer model (`EXPLAIN_MODEL`, default `google/gemini-2.5-flash-lite`) phrases the already
finished result in Arabic, citing the numbered texts. It never sees anything but those facts and cannot change the outcome. Code rejects the output if it
changes the verdict, cites a missing text, quotes words not in the cited text, invents a number or a grading, calls anything fabricated, or gives a fatwa;
then a plain template explanation (`ai_written: false`) is returned instead. Writer bake-off: DeepSeek V4 Flash passed 8/10 after raising max tokens but
needs more care; Gemini 2.5 Flash Lite passed 9/10. All text inputs are limited to 500 words (HTTP 422 beyond that).

## Close to a known text (no chat model)

A reworded hadith ("فإنما تنصرون وترزقون بضعفائكم") matches nothing word for word and reads like advice, so it used to pass silently.
Now every sentence (and each clause of it) that no quote covers is compared with the corpus by meaning (one cached embedding; the
corpus vectors are stored) and by shared words (`app/services/similar.py`). The closest text is shown as a pointer, never as
"verified", with the words of the sentence that the text does not contain. It is shown only if the text shares at least half
of the sentence's distinctive words (more for long sentences), the meaning is close, and the sentence is not a stock formula
(shahada, salawat: very common words). Thresholds were calibrated on real sermon sentences: genuine rewordings 55-100%,
fabricated reward claims at most 47%. `/api/check` returns `kind: "similar"` items; `/api/claim` returns `similar`. Cost: about
a tenth of a cent per sermon.

## Result cards (test console)

`/claim` shows each quote, claim and close match as one compact card (status badge, the sentence, the strongest source). A card
opens like a tab: Evidence, Partial & related, Quote check, Close text, and Explain (the Arabic explanation, only on click).
A strip of status counts and the filters (All, Claims, Quran & hadith quotes, Close matches, Short phrases, Needs attention)
keep a long sermon manageable. Verified runs of four words or fewer are counted apart as "Matched phrase", so they do not
inflate "verified". The code is `app/static/cards.js` and `cards.css` (served under `/static`); the API did not change.

## Choosing the provider in the page

Each test page has Settings with **AI provider** (Server default, OpenRouter, Google) and a key field for each provider. A
teammate picks the provider and pastes their own key; the choice and the keys stay in their browser (localStorage) and travel
with each request as `X-LLM-Provider`, `X-OpenRouter-Key` and `X-Gemini-Key`. They apply to that request only: never stored,
never logged, and error messages are scrubbed of key-like text. A chosen provider uses that provider's default models (the
server's `LLM_MODEL` / `JUDGE_MODEL` / `EXPLAIN_MODEL` names belong to one provider, so they are ignored then). Without a choice
the server's `LLM_PROVIDER` (default OpenRouter) and its own keys are used. `/api/config` tells the page which providers the
server holds a key for. The cache keeps answers of different providers apart.

## Free testing with Google's API

Set `GEMINI_API_KEY` and `LLM_PROVIDER=google` in `.env` to run every model step and the embeddings on Google's free Gemini tier
(no OpenRouter credit). Defaults on Google: router, recall and triage `gemini-3.5-flash-lite`, claim judge `gemini-3.1-flash-lite`,
explanation writer `gemini-flash-lite-latest`. The judge benchmark (10 overreach and control cases, 3 runs each) gave 30/30 for
`gemini-3.1-flash-lite` and 29/30 for `gemini-3.5-flash-lite` (Haiku 4.5: 30/30, gpt-4o-mini: 23/30). The free tier allows about 15
requests per minute per Flash-Lite model and 5 per Flash model, so the client spaces calls and retries after a 429; a golden run
takes about 20 minutes. Production stays on OpenRouter unless `LLM_PROVIDER` is set on the host.

## Tafsir under Quran verses

A Quran verse shown in a card has a **Tafsir** button; the commentary is fetched only when it is clicked (`GET /api/tafsir/2:191` or
`/api/tafsir/33:41-42`) and is never part of a result: it takes no part in the search, the judge or any outcome, and no model writes
or summarises it. Shown as the author wrote it: **Al-Tafsir al-Muyassar** and **Tafsir al-Saadi** (`app/services/tafsir.py`,
`data/tafsir/*.json.gz`). Built by `scripts/ingest_tafsir.py` from `data/tafsir_raw/` (not committed; files from
github.com/abdalrhmanreda/islamic-data-assets, MIT compilation). Only markup is removed; a commentary that covers several verses is
stored once ("covers 4:60-62"). Both cover all 6,236 verses except Saadi 26:1 (empty in the source). **Rights in the underlying
texts are not verified: check them before a public release.** Hadith have no tafsir (their commentary, sharh, would be a separate source).

## Scan a PDF or image (OCR)

On `/claim`, **Scan a PDF or image** fills the claim box from up to **3 pages**; the 500-word limit stays the real limit and the person
keeps the pages they want, then edits the text. A PDF page that has a real text layer is read in the browser (pdf.js, nothing uploaded);
a garbled layer, a scan or an image is shrunk in the browser and sent to `POST /api/ocr`, where **two different models read it**
(`app/services/ocr.py`: `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite`, on the provider chosen in Settings). The words on which the two
readings differ are listed next to the page, with a button to take the second reading. Nothing is stored, no cache is kept, and the
page warns, next to the box and again on the results of the check: "Read from a scan; the reader may have filled in unclear words from context; check every word against the picture." (not shown for a PDF's own text layer). Both models can make the same context-driven mistake on a blurry image (a dialect word read back as a nearby standard one), which the comparison cannot catch: that is what the warning is for.

Why two readers and a strict prompt: an OCR step that "improves" the text would hide a misquote. In the spike both models copied altered
quotes exactly, but one once added «عَزَّ وَجَلَّ» to a real-looking hadith: the second reading catches that kind of insertion. Tesseract
(tried in the browser) was perfect on clean typed text but 27-39% wrong on a vowelled page and unusable on stylised frames; ArafiX (OCR
post-correction by language models) was rejected because it would correct misquotes toward the real text.

## API

`POST /api/verify` with `{"text": "...", "use_llm": false}` returns `original_text`, `word_count`, `segments[]` and, when `use_llm` is on, `extraction`.
Each segment has `segment_text`, `classification` (quran | hadith | unverified), `status` (verified | semantic_variant | baseless),
`match_type` (full | partial), `confidence`, `is_claim`, `source` (book, chapter, number, matched_text, other_matches_count) and `differences`.

`verified` means the words are in the corpus, not that a hadith is authentic: gradings are in the corpus but not returned yet.

## Commands

| Command | What it does |
|---|---|
| `python evals/eval_golden.py` | Runs the golden set (`golden/quran_golden.json`) through the pipeline: verified accuracy, false confirmations, per-category results. Exit code 1 on any non-gap failure. |
| `python evals/eval_paragraphs.py [-v]` | Runs the golden paragraphs through the paragraph check: claims found with an acceptable outcome, quotes, commentary wrongly checked, reversals. |
| `python evals/eval_claims.py [-v]` | Runs the golden claims through the claim verifier: type and outcome accuracy, quote statuses, reversals and false support (the two numbers that must be 0). |
| `python evals/eval_evidence.py [--llm] [--no-meaning]` | Measures the evidence finder on `golden/evidence_golden.json` (recall of expected texts). `--llm` makes about 75 cheap model calls. |
| `python evals/eval_fiqh.py [--llm]` | Measures the fiqh check on `golden/fiqh_golden.json`: acceptable status, expected encyclopedia entry shown, and false_settled (a disputed question shown as agreed; must be 0). |
| `python evals/eval_package.py [-v]` | Runs the organizers' test cases (`golden/package_cases.json`) through the claim check. Needs a model key. |
| `python scripts/ingest_fiqh.py` | Rebuilds `data/fiqh/kuwaiti.jsonl.gz` from the Kuwaiti Fiqh Encyclopedia (downloads about 260 MB on first run; needs pyarrow). |
| `python scripts/ingest_tafsir.py` | Rebuilds `data/tafsir/` from the raw tafsir files in `data/tafsir_raw/`. |
| `python scripts/embed_corpus.py` | Rebuilds `data/corpus_embeddings.npz` (about 4 million tokens, under a dollar; resumable). Needed after the corpus changes. |
| `python scripts/validate_corpus.py` | Checks `data/corpus.json` against the Tanzil files character for character. |
| `python scripts/ingest_quran.py` | Rebuilds `data/corpus.json` from `data/tanzil/` (offline). |
| `python scripts/ingest_hadith.py` | Rebuilds `data/corpus_hadith.json.gz`; downloads the raw hadith files on first run (about 100 MB, SHA-256 pinned). |

Run `python evals/eval_golden.py` before and after any change to matching code. The golden set was written by one person and is a smoke test, not proof of accuracy.

## Layout

```
app/              the FastAPI service
  main.py         app, routers, startup (builds the indexes)
  schemas.py      every request and response model
  routers/        one file per endpoint group (verify, check, claim, evidence, explain, tafsir, fiqh, dorar)
  services/       the logic: verifier.py, quote_finder.py, pipeline.py (quotes); claim_card.py, text_claims.py (claims);
                  fiqh.py (fiqh check); levels.py (content levels); dorar.py (Dorar gradings); evidence*.py, dense.py,
                  similar.py (search); llm_*.py, cache.py (model calls); explain.py, tafsir.py, strength.py
  static/         the test pages and the result cards (cards.js, cards.css)
data/             corpora shipped with the app: Quran, hadith, embeddings, tafsir, fiqh encyclopedia, Tanzil sources
scripts/          rebuild the data (ingest_*.py, embed_corpus.py) and check it (validate_corpus.py)
evals/            measurement scripts, one per golden set
golden/           the test sets (quotes, claims, paragraphs, evidence, fiqh, organizers' cases)
tests/fixtures/   saved real responses used by tests (Dorar)
BASELINE.md       what existed before the challenge days; CHANGELOG.md: what was built during them
```

## Data sources

- `data/fiqh/kuwaiti.jsonl.gz`: al-Mawsu'a al-Fiqhiyya al-Kuwaytiyya (Ministry of Awqaf and Islamic Affairs, Kuwait; published free of charge at
  bohoth.awqaf.gov.kw and named in the challenge's scientific pack). Text from Shamela book 11430 via the Hugging Face dataset
  MoMonir/shamela_books_text_full (Apache-2.0 for the dataset), pagination matching the printed edition. Rebuild with `python scripts/ingest_fiqh.py`.
- Hadith gradings shown in the Dorar tab come live from Dorar al-Saniyya (dorar.net, hadith encyclopedia API) and are credited on every result.

- `data/tanzil/` holds the Quran texts from the [Tanzil Project](https://tanzil.net) (Uthmani and simple-clean),
  unmodified and used under its CC BY 3.0 terms: source must be credited and linked to tanzil.net.
  Each file keeps Tanzil's original copyright header.
- `data/corpus.json` is generated offline from those files by `scripts/ingest_quran.py` (Uthmani as `text`, simple-clean as `match_text`,
  surah names in `data/surah_names.json`). `scripts/validate_corpus.py` checks it against Tanzil character for character.
- `data/corpus_hadith.json.gz` (about 41,200 hadiths, Arabic only) is generated by `scripts/ingest_hadith.py` from two sources:
  [AhmedBaset/hadith-json](https://github.com/AhmedBaset/hadith-json) tag v1.2.0 (all nine books of `the_9_books`: Bukhari, Muslim,
  Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah, Muwatta Malik, Musnad Ahmad, al-Darimi; texts scraped from sunnah.com) and
  [fawazahmed0/hadith-api](https://github.com/fawazahmed0/hadith-api) commit df57907 (Unlicense), which supplies the standard hadith
  numbers and gradings for seven of those books and 300+ Bukhari hadiths the first source lacks. The two are aligned per book and merged;
  the rules are at the top of `scripts/ingest_hadith.py`. Raw downloads live in `data/hadith/` and `data/hadith2/` (git-ignored, SHA-256 pinned).
  Neither dataset has a license file for the sunnah.com-derived texts, so check sunnah.com's terms before redistributing.
  Numbers: Bukhari, Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah and Muwatta use B's `hadithnumber`; Muslim uses B's `arabicnumber`
  (the Abd al-Baqi numbering, e.g. 223). Hadiths the two sources could not be paired for, and all of Musnad Ahmad (incomplete in the
  source: 1,374 hadiths) and al-Darimi, have no number: `source.number` is empty rather than guessed. Where a text occurs in several
  books the first in that order is reported.
