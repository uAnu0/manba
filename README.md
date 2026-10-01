# Manba

Verification tool built with FastAPI.

```bash
.venv\Scripts\activate
uvicorn app.main:app --reload
```

Docs: http://127.0.0.1:8000/docs

## Data sources

- `data/tanzil/` holds the Quran texts from the [Tanzil Project](https://tanzil.net) (Uthmani and simple-clean),
  unmodified and used under its CC BY 3.0 terms: source must be credited and linked to tanzil.net.
  Each file keeps Tanzil's original copyright header.
- `corpus.json` is generated offline from those files by `ingest_quran.py` (Uthmani as `text`, simple-clean as `match_text`,
  surah names in `data/surah_names.json`). `validate_corpus.py` checks it against Tanzil character for character.
