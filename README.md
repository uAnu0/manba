# Manba

Verification service for Islamic text. It takes raw text (a sentence or a whole sermon), finds the Quran verses and hadith in it,
and checks each against local corpora: word for word, with the source, and an exact account of what differs when a quote is altered.
A language model is optional and only *finds* candidate quotes; it never decides a verdict.

**Private repository: for the team only.** The hadith texts come from sunnah.com-derived datasets without a license file (see Data sources).

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

## Evidence finder (version 0)

`POST /api/evidence` with `{"question": "...", "use_llm": true}` returns the Quran verses and hadith that bear on a topic, each with its source,
an excerpt (a hadith without its chain of narrators), the full text, and the gradings scholars gave it (when the dataset has them).
It also returns `refer_to_scholar` with a reason (sensitive topics such as family law, finance and medicine; personal situations; no clear evidence)
and a notice that this is evidence, not a ruling. Test page: `/evidence`.

How it finds texts. Three searches run and their rankings are merged; only corpus text is ever shown:
1. **Meaning search** (always, when `corpus_embeddings.npz` and an OpenRouter key are available): every verse and hadith was turned into a vector once
   (`python embed_corpus.py`, model `google/gemini-embedding-001`, 768 numbers per text, about 37 MB); the question is embedded at request time and the
   nearest texts are taken. It finds "من قتل نفسه" for a question about suicide, which keywords cannot.
2. **Keyword search** (always): BM25 over normalized, lightly stemmed Arabic; hadith are searched without their chain of narrators.
3. **LLM step** (`use_llm`): the model *recites* the evidence it knows (each recitation is looked up in the corpus; unconfirmed ones are discarded and
   listed in `query.rejected`), then picks the final texts among the retrieved candidates. It only picks from a numbered list; it writes no evidence and no ruling.

Measured on `golden/evidence_golden.json` (25 questions, 36 expected texts, written by the developer) with the card as shown (8 verses + 10 hadith):
keywords only 22% of the expected texts (32% of the questions); meaning + keywords 47% (60%); with the LLM step 67% (80%).
That is a baseline on a small set, not a quality bar: it needs scholar-reviewed questions. Run `python eval_evidence.py [--llm] [--no-meaning]` to re-measure.
Memory with everything loaded is about 510 MB and startup about 20 s (the indexes are built at first use).

## API

`POST /api/verify` with `{"text": "...", "use_llm": false}` returns `original_text`, `word_count`, `segments[]` and, when `use_llm` is on, `extraction`.
Each segment has `segment_text`, `classification` (quran | hadith | unverified), `status` (verified | semantic_variant | baseless),
`match_type` (full | partial), `confidence`, `is_claim`, `source` (book, chapter, number, matched_text, other_matches_count) and `differences`.

`verified` means the words are in the corpus, not that a hadith is authentic: gradings are in the corpus but not returned yet.

## Commands

| Command | What it does |
|---|---|
| `python eval_golden.py` | Runs the golden set (`golden/quran_golden.json`) through the pipeline: verified accuracy, false confirmations, per-category results. Exit code 1 on any non-gap failure. |
| `python eval_evidence.py [--llm] [--no-meaning]` | Measures the evidence finder on `golden/evidence_golden.json` (recall of expected texts). `--llm` makes about 75 cheap model calls. |
| `python embed_corpus.py` | Rebuilds `corpus_embeddings.npz` (about 4 million tokens, under a dollar; resumable). Needed after the corpus changes. |
| `python validate_corpus.py` | Checks `corpus.json` against the Tanzil files character for character. |
| `python ingest_quran.py` | Rebuilds `corpus.json` from `data/tanzil/` (offline). |
| `python ingest_hadith.py` | Rebuilds `corpus_hadith.json.gz`; downloads the raw hadith files on first run (about 100 MB, SHA-256 pinned). |

Run `python eval_golden.py` before and after any change to matching code. The golden set was written by one person and is a smoke test, not proof of accuracy.

## Layout

- `app/services/verifier.py`: normalization, corpus loading, indexes, `verify_segment`.
- `app/services/quote_finder.py`: finds quotes inside long text (brackets, attributions, verbatim runs).
- `app/services/pipeline.py`: sentence splitting, local pass, optional LLM merge.
- `app/services/llm_extractor.py`: OpenRouter call (`openai/gpt-4o-mini`) that lists quotes; claims must occur in the original text.
- `app/static/index.html`: test console.

## Data sources

- `data/tanzil/` holds the Quran texts from the [Tanzil Project](https://tanzil.net) (Uthmani and simple-clean),
  unmodified and used under its CC BY 3.0 terms: source must be credited and linked to tanzil.net.
  Each file keeps Tanzil's original copyright header.
- `corpus.json` is generated offline from those files by `ingest_quran.py` (Uthmani as `text`, simple-clean as `match_text`,
  surah names in `data/surah_names.json`). `validate_corpus.py` checks it against Tanzil character for character.
- `corpus_hadith.json.gz` (about 41,200 hadiths, Arabic only) is generated by `ingest_hadith.py` from two sources:
  [AhmedBaset/hadith-json](https://github.com/AhmedBaset/hadith-json) tag v1.2.0 (all nine books of `the_9_books`: Bukhari, Muslim,
  Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah, Muwatta Malik, Musnad Ahmad, al-Darimi; texts scraped from sunnah.com) and
  [fawazahmed0/hadith-api](https://github.com/fawazahmed0/hadith-api) commit df57907 (Unlicense), which supplies the standard hadith
  numbers and gradings for seven of those books and 300+ Bukhari hadiths the first source lacks. The two are aligned per book and merged;
  the rules are at the top of `ingest_hadith.py`. Raw downloads live in `data/hadith/` and `data/hadith2/` (git-ignored, SHA-256 pinned).
  Neither dataset has a license file for the sunnah.com-derived texts, so check sunnah.com's terms before redistributing.
  Numbers: Bukhari, Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah and Muwatta use B's `hadithnumber`; Muslim uses B's `arabicnumber`
  (the Abd al-Baqi numbering, e.g. 223). Hadiths the two sources could not be paired for, and all of Musnad Ahmad (incomplete in the
  source: 1,374 hadiths) and al-Darimi, have no number: `source.number` is empty rather than guessed. Where a text occurs in several
  books the first in that order is reported.
