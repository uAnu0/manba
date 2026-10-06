"""The nearest known verse or hadith for a sentence that nothing else recognised.

A preacher often rewords a hadith ("فإنما تنصرون وترزقون بضعفائكم" for "هل تنصرون وترزقون إلا بضعفائكم"). No run of words
matches word for word, and the sentence reads like advice, so it used to pass without a word. Here the sentence is
compared by meaning (one embedding call: the corpus vectors are already stored) and by shared words with the closest
texts. A text is shown only if it shares most of the sentence's words, and the words the text does NOT contain are
listed: for a hadith with a changed ending that list is exactly the warning. It is a pointer for the reader, never
"verified", and no chat model is involved.

Thresholds come from a calibration on real sermon sentences: genuine rewordings share 55-100% of their words with the
hadith, fabricated sermon sentences at most 47%, stock phrases only 2-3 words.
"""
import re

from app.schemas import SimilarText
from app.services.dense import dense_index, embed_query
from app.services.evidence import STOPWORDS, index, item_for, retrieve, search_text, stem, terms
from app.services.quote_finder import tokenize
from app.services.strength import level_of
from app.services.verifier import load_corpus

MIN_TERMS = 3  # a sentence with fewer distinctive words says too little to match
POOL = 12  # candidates from each search
SHARE, MATCHED, COSINE = 0.5, 4, 0.7  # a text shares at least half of the sentence's words, four of them, and the same meaning
STRONG_SHARE, STRONG_MATCHED, STRONG_COSINE = 0.75, 3, 0.8  # a short sentence needs a closer text instead
LONG_TERMS, LONG_SHARE = 14, 0.65  # a long sentence (a sermon's praise opening) shares many common words with real texts: ask for more
MIN_MEAN_IDF = 3.8  # stock formulas (the shahada, the salawat) are made of very common words: real rewordings score 4.1-7.2, formulas 3.1-3.4
MAX_MISSING = 8


def _accept(share: float, matched: int, cosine: float, n_terms: int = 0) -> bool:
    if n_terms >= LONG_TERMS and share < LONG_SHARE:
        return False
    return (share >= SHARE and matched >= MATCHED and cosine >= COSINE) or (
        share >= STRONG_SHARE and matched >= STRONG_MATCHED and cosine >= STRONG_COSINE
    )


async def nearest_text(sentence: str, api_key: str | None = None, strict: bool = False) -> SimilarText | None:
    """The closest corpus text to `sentence` if it is close enough to point out, else None. Never raises."""
    wanted = set(terms(sentence))
    dense = dense_index()
    if len(wanted) < MIN_TERMS:
        return None
    if dense is None:
        if strict:
            raise RuntimeError("meaning search index unavailable")
        return None
    idf = index().idf
    if sum(idf.get(w, 0.0) for w in wanted) / len(wanted) < MIN_MEAN_IDF:
        return None
    try:
        vector = await embed_query(sentence, api_key)
    except Exception:  # no embedding available: simply no pointer
        if strict:
            raise
        return None
    entries = load_corpus()
    candidates: dict[int, float] = {}
    for classification in ("quran", "hadith"):
        for i, similarity in dense.search(vector, classification, POOL):
            candidates[i] = similarity
    quran, hadith, _ = retrieve(sentence, None, POOL, POOL)
    for i, _, _ in quran + hadith:
        candidates.setdefault(i, float(dense.matrix[i] @ vector))
    best = None
    for i, similarity in candidates.items():
        entry = entries[i]
        text_terms = set(terms(search_text(entry)))
        matched = len(wanted & text_terms)
        share = matched / len(wanted)
        if not _accept(share, matched, similarity, len(wanted)):
            continue
        level = level_of(entry.classification, entry.book) or 9
        key = (round(share, 2), -level, similarity)  # the same text is often in several collections: prefer the higher level
        if best is None or key > best[0]:
            best = (key, i, similarity, share, matched, text_terms)
    if best is None:
        return None
    _, i, similarity, share, matched, text_terms = best
    entry = entries[i]
    seen, missing = set(), []
    for word in tokenize(sentence):
        norm = word.norm
        if norm in STOPWORDS or len(norm) < 2 or stem(norm) in text_terms or norm in seen:
            continue
        seen.add(norm)
        missing.append(re.sub("[ً-ٰٟـ]", "", sentence[word.start : word.end]).strip("،؛:.!؟()«»\"'"))
    return SimilarText(
        evidence=item_for(entry, wanted, similarity * 1000, [], ["meaning"], True),
        similarity=round(similarity, 3),
        shared_share=round(share, 2),
        shared_words=matched,
        missing_words=missing[:MAX_MISSING],
    )
