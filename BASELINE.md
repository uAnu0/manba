# Starting version (before the challenge days)

The challenge guide allows earlier work if it is declared, and only what is built from 4 to 6 October 2026 is assessed.
This file declares what existed before the challenge opened (Sunday 4 October 2026, 09:00 Riyadh time).

- **Baseline commit and `v0-baseline` tag:** `52962663421a245605a8e1fe10b08f2aff32b35a` (last commit 4 October 2026, 02:59 +03:00). Commit IDs changed on 5 October 2026 when tool co-author lines were removed from commit messages and a personal email was replaced with a GitHub no-reply address; contents and dates are unchanged. The same commit had the ID `192bd08` before the metadata cleanup. The remote tag now points to the declared baseline above.
- **Everything after that tag** is challenge work and is listed, by date, in `CHANGELOG.md`.
- **Rights:** the code in the baseline was written by the team. Third-party data and its licences are listed in the README (Data sources).

## What the baseline already did

| Area | State at the baseline |
|---|---|
| Quote check (`/api/verify`) | Finds Quran and hadith quotes in raw text, matches them word for word against Tanzil (6,236 verses) and nine hadith books (~41,200 hadith), reports the exact differences of an altered quote. |
| Paragraph check (`/api/check`) | Finds every quote and every religious claim in a paragraph and checks each. |
| Claim check (`/api/claim`) | Routes a claim (quote / topic / personal / not religious), gathers evidence for and against, weighs it by source strength. Never a true or false verdict. |
| Evidence finder (`/api/evidence`) | Texts that bear on a question (meaning + keyword search + model recitation checked against the corpus). |
| Close to a known text | Points to the nearest verse or hadith for reworded text. |
| Explain | On-demand Arabic explanation written by a model from the facts of a result, validated by code. |
| Tafsir | Al-Muyassar and al-Saadi under Quran verses, on demand. |
| Test sets | `quran_golden` (79 items + 6 sermons), `claims_golden` (34), `paragraphs_golden` (5), `evidence_golden` (25), all written by the developer. |

## What the baseline did not have

- No fiqh layer: no scholarly positions, no check for disputed questions stated as settled or for claimed consensus.
- No content levels from the organizers' scientific pack (أ / ب / ج / د).
- No Dorar gradings: about 4,800 hadith (Musnad Ahmad, al-Darimi) had no grading at all, and only nine books were covered.
- Not deployed; repository private.
