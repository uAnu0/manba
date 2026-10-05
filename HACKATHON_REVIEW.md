# Hackathon cleanup, 5 October 2026

This change tightens what a review can claim. The original direct-matching tests
pass, but they do not establish full claim detection or scholarly correctness.

## Before deployment

1. Set a dedicated `BADGE_SECRET` containing at least 32 cryptographically random
   bytes. Keep it stable across deployments. Do not reuse access or model keys.
2. New receipts start with `MNB2-` and use a 128-bit text digest and 128-bit MAC.
   The old `MNB-` format is retired. Reissue demonstration receipts and regenerate
   reports on the final deployment. Receipts from localhost do not prove that
   production reviewed anything.
3. Receipt matching now uses the exact UTF-8 text, including spaces and newlines.
   The UI submits its trimmed review input; verification must use that reviewed
   input. Retain the full code when copying or printing.
4. The six built-in samples are available as clearly labelled saved, direct
   matching demos without an access token. They never issue a receipt. Arbitrary
   live input still requires `API_ACCESS_TOKEN`. Arrange judge access or implement
   a public live mode with distributed rate limits and a cost budget before
   submission. Do not simply expose a shared model key.
5. Review model credentials and run the paragraph and organiser suites in full
   AI mode. Without a key the paragraph suite gets 0/10 expected claim outcomes
   and 4/4 quotes; the organiser suite gets 6/10 applicable cases.
6. Resolve the permission questions recorded in `SOURCES.md`. Nothing in this
   cleanup supplies rights to redistribute the underlying texts.

## Behavior changes

- Quran matching preserves the distinction between ة and ه before verification,
  and checks explicit short vowels and above/below hamza where letter positions
  align with the source. The changed words رحمه, أَحِدٌ and أن (for إن) no longer
  pass as the source's wording. This
  is not a claim of exhaustive vocalization or orthography coverage.
- The API owns each finding's category and whether it requires action; the UI
  uses these fields. Unresolved claims, referrals, disputed unqualified rulings,
  missing grades, keyword-only fiqh matches, failed model steps, skipped claims,
  and truncated reviews cannot earn a receipt.
- A model's assessment that evidence supports a claim does not certify it.
  Opposing evidence remains mixed regardless of its relative score. Agreement
  direction in fiqh requires explicit ruling words in a source-checked excerpt,
  rather than a model's direction label. Multiple school attributions require
  separate checks. Correct school attribution cannot erase a false consensus.
- Claim triage receives entire sentences, and attributed unquoted text cannot
  disappear merely because triage returns no claims. Foreign claims beside
  quotes and request limits are handled explicitly.
- Automatic fixes use finding offsets rather than the first repeated string.
  Manual drafts survive actions and language changes. Editing manually disables
  automatic modifications until a new review. A translated quote with a wrong
  reference requires manual correction; replacing its words alone is insufficient.
  Keyword-only and ambiguous fiqh matches do not offer automatic rewriting.
- The tour has a pause control and stops while focused. Long receipt codes wrap.
- Privacy wording acknowledges process caches and external model processing.
  Sharing carries the entire input in the URL, rather than a stored report.
- Removed the `memory` setting that the supplied Vercel build explicitly ignores
  under Active CPU billing. The 120-second duration setting remains.
- The paragraph evaluation now fails when expected claims or quotes are missed,
  instead of passing solely because no reversal occurred.

## Local validation

Run `python -m pytest tests/test_readiness.py -q`,
`node tests/frontend_regressions.cjs`, `python -m evals.eval_golden`,
`python -m evals.eval_fiqh`, and `python -m evals.eval_translations`.
The CI workflow runs these checks without paid model calls. The AI suites require
configured model access and separate human review of sensitive cases.

The supplied participant guide requires a working live link, public repository,
source/license record, PDF or PowerPoint presentation, and a video no longer than
two minutes. Its deadline is 6 October 2026 at 23:59 Riyadh time.
