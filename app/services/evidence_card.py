"""The evidence card for a question: retrieved texts plus the decision whether to send the person to a scholar.

Three searches feed the card and their rankings are merged (reciprocal rank fusion):
  meaning   - the question's embedding against the embeddings of every verse and hadith (dense.py)
  keyword   - BM25 over normalized Arabic words (evidence.py)
  recitation - texts an LLM recalls for the question that the corpus then confirms (llm_query.py); optional
Only corpus text is ever shown.
"""
import re
from collections import defaultdict
from functools import lru_cache

from app.schemas import EvidenceItem, EvidenceResponse, QueryInfo
from app.services.dense import dense_index, embed_query
from app.services.evidence import index, item_for, matn_start, retrieve, stem, terms
from app.services.llm_query import suggest_evidence
from app.services.pipeline import _redact
from app.services.verifier import normalize, partial_match, verify_verbatim

RARE_IDF = 5.0  # a word this rare (about 1 text in 300) says a lot about which text is meant
MIN_RARE_WORDS = 2
APPROX_MIN_COVERAGE = 0.75  # share of a recited text that must be verbatim corpus text to accept it as "close"
_ANNOTATION = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]\s*$")  # "(حديث صحيح)" and similar remarks the model may append

QURAN_LIMIT = 8
HADITH_LIMIT = 10
POOL = 30  # candidates taken from each search before merging

# Weights of the three searches in the merged ranking, and the usual reciprocal-rank constant.
WEIGHT_MEANING = 1.0
WEIGHT_KEYWORD = 0.5
WEIGHT_RECITATION = 1.5
RRF_K = 60
# Meaning search always returns the nearest texts; below this cosine similarity they are not about the question.
MIN_SIMILARITY = {"quran": 0.0, "hadith": 0.0}

NOTICE_AR = (
    "هذه نصوص من القرآن والسنة ذات صلة بموضوع سؤالك، وليست فتوى ولا حكمًا. "
    "استنباط الحكم الشرعي يقوم به أهل العلم بعد النظر في الأدلة كلها وفي حال السائل؛ "
    "فإن كانت مسألتك تخص حالتك فاسأل عالمًا موثوقًا."
)
NOTICE_EN = (
    "These are Quran and hadith texts related to your question's topic. They are not a fatwa or a ruling. "
    "Rulings are derived by qualified scholars from all the evidence and from your situation; "
    "if your question concerns your own case, ask a trusted scholar."
)

# Version 0 of the referral policy. It is a placeholder to be replaced by a list that scholars review.
# Words are matched after normalization and light stemming (see evidence.stem).
SENSITIVE_TOPICS = {
    "family law (marriage, divorce, custody, inheritance)": """
        طلاق طلق خلع نكاح زواج تزوج عدة نفقة حضانة رضاع ميراث إرث ارث تركة وصية مهر ظهار لعان
        divorce marriage inheritance custody
    """,
    "financial contracts and transactions": """
        ربا فوائد بنك قرض سهم أسهم تأمين رهن مضاربة عملات
        interest loan mortgage insurance
    """,
    "medical questions": """
        إجهاض اجهاض إسقاط علاج عملية دواء تلقيح استنساخ
        abortion surgery medicine
    """,
    "takfir, jihad and politics": """
        تكفير كفر جهاد خروج ردة مرتد قتال
        takfir jihad apostasy
    """,
}
PERSONAL_MARKERS = "زوجتي زوجي أمي أبي والدي ابني بنتي أنا عندي لدي حالتي"

_SENSITIVE = {topic: {stem(w) for w in terms(words)} for topic, words in SENSITIVE_TOPICS.items()}
_PERSONAL = {stem(w) for w in terms(PERSONAL_MARKERS)}


@lru_cache(maxsize=1)
def _entry_lookup() -> dict[tuple[str, str, str, str], int]:
    return {(e.classification, e.book, e.number, e.text): i for i, e in enumerate(index().entries)}


def lookup_index(classification: str, book: str, number: str, text: str) -> int | None:
    return _entry_lookup().get((classification, book, number, text))


def referral(question: str, found: int) -> tuple[bool, str | None]:
    words = set(terms(question))
    for topic, topic_words in _SENSITIVE.items():
        if words & topic_words:
            return True, f"This question touches {topic}: rulings depend on details, so ask a scholar."
    if words & _PERSONAL:
        return True, "The question describes a personal situation: ask a scholar who can hear the details."
    if found == 0:
        return True, "No clear evidence was found in the corpus for this question: ask a scholar."
    return False, None


def rare_words_index(text: str) -> int | None:
    """A corpus text that contains EVERY rare word of the recitation (and at least two of them).

    Catches recitations whose first words were paraphrased ("إن الله يلعن الراشي والمرتشي" for "لعن رسول الله صلى الله
    عليه وسلم الراشي والمرتشي") without ever attaching a recitation to a text that merely shares common words."""
    idx = index()
    rare = {w for w in terms(text) if idx.idf.get(w, 0.0) >= RARE_IDF}
    if len(rare) < MIN_RARE_WORDS:
        return None
    query = {w: 1.0 for w in rare}
    for classification in ("hadith", "quran"):
        for i, _, matched in idx.search(query, 5, classification):
            if set(matched) == rare:
                return i
    return None


def resolve_suggestion(text: str) -> tuple[int | None, bool, EvidenceItem | None]:
    """Find a recited text in the corpus: (entry index, exact wording?, a ready item for multi-verse windows).

    Verbatim (or as a slice of a corpus text) first, then close wording. Never a looser match: attaching a recitation
    to an unrelated text would present unrelated evidence."""
    text = _ANNOTATION.sub("", text).strip()
    text = text[matn_start(text) :]  # drop a chain of narrators the model may still have added
    seg = verify_verbatim(text)
    if seg and seg.status == "verified" and seg.source and seg.classification in ("quran", "hadith"):
        i = lookup_index(seg.classification, seg.source.book, seg.source.number, seg.source.matched_text)
        if i is not None:
            return i, True, None
        if seg.classification == "quran":  # a multi-verse window such as 112:1-2 has no single entry
            window = EvidenceItem(
                classification="quran",
                score=0.0,
                source=seg.source,
                full_text=seg.source.matched_text,
                found_by=["suggestion"],
            )
            return None, True, window
    close = partial_match(text, normalize(text).split())
    if close and close.source and close.confidence >= APPROX_MIN_COVERAGE:
        i = lookup_index(close.classification, close.source.book, close.source.number, close.source.matched_text)
        if i is not None:
            return i, False, None
    i = rare_words_index(text)
    return (i, False, None) if i is not None else (None, False, None)


def fuse(
    keyword: list[tuple[int, float, list[str]]],
    meaning: list[tuple[int, float]],
    recited: list[int],
    limit: int,
) -> list[tuple[int, float, set[str]]]:
    """Merge the three rankings: (entry index, fused score, which searches found it), best first."""
    score: dict[int, float] = defaultdict(float)
    found_by: dict[int, set[str]] = defaultdict(set)
    for rank, (i, _, _) in enumerate(keyword):
        score[i] += WEIGHT_KEYWORD / (RRF_K + rank + 1)
        found_by[i].add("keyword")
    for rank, (i, _) in enumerate(meaning):
        score[i] += WEIGHT_MEANING / (RRF_K + rank + 1)
        found_by[i].add("meaning")
    for rank, i in enumerate(recited):
        score[i] += WEIGHT_RECITATION / (RRF_K + rank + 1)
        found_by[i].add("suggestion")
    top = sorted(score, key=score.__getitem__, reverse=True)[:limit]
    return [(i, score[i], found_by[i]) for i in top]


async def build_card(
    question: str, use_llm: bool = False, api_key: str | None = None, use_meaning: bool = True
) -> EvidenceResponse:
    info = QueryInfo(used=False)
    entries = index().entries
    query_words = set(terms(question))

    kw_quran, kw_hadith, words = retrieve(question, None, POOL, POOL)
    keyword = {"quran": kw_quran, "hadith": kw_hadith}

    meaning: dict[str, list[tuple[int, float]]] = {"quran": [], "hadith": []}
    similarity: dict[int, float] = {}
    dense = dense_index() if use_meaning else None
    if dense is not None:
        try:
            qv = await embed_query(question, api_key)
            for classification in meaning:
                meaning[classification] = [
                    (i, s) for i, s in dense.search(qv, classification, POOL) if s >= MIN_SIMILARITY[classification]
                ]
                similarity.update(meaning[classification])
            info.meaning_used = True
        except Exception as exc:  # keyword search still runs
            info.meaning_error = _redact(f"{type(exc).__name__}: {exc}")

    recited: dict[str, list[int]] = {"quran": [], "hadith": []}
    exact: dict[int, bool] = {}
    windows: list[EvidenceItem] = []
    if use_llm:
        try:
            suggestions = await suggest_evidence(question, api_key)
            rejected = []
            for text in suggestions:
                i, is_exact, window = resolve_suggestion(text)
                if window is not None:
                    windows.append(window)
                elif i is None:
                    rejected.append(text)
                elif i not in exact:
                    exact[i] = is_exact
                    recited[entries[i].classification].append(i)
            info.used = True
            info.suggested = len(suggestions)
            info.found_in_corpus = len(exact) + len(windows)
            info.rejected = rejected
        except Exception as exc:
            info.error = _redact(f"{type(exc).__name__}: {exc}")

    cards: dict[str, list[EvidenceItem]] = {}
    for classification, limit in (("quran", QURAN_LIMIT), ("hadith", HADITH_LIMIT)):
        items = []
        if classification == "quran":
            items += windows
        for i, score, sources in fuse(keyword[classification], meaning[classification], recited[classification], limit):
            matched = next((m for j, _, m in keyword[classification] if j == i), [])
            item = item_for(entries[i], query_words, score * 1000, matched, sorted(sources), exact.get(i, True))
            item.similarity = round(similarity[i], 3) if i in similarity else None
            items.append(item)
        cards[classification] = items[:limit]

    refer, reason = referral(question, len(cards["quran"]) + len(cards["hadith"]))
    return EvidenceResponse(
        question=question,
        search_terms=sorted(words),
        query=info,
        quran=cards["quran"],
        hadith=cards["hadith"],
        refer_to_scholar=refer,
        reason=reason,
        notice_ar=NOTICE_AR,
        notice_en=NOTICE_EN,
    )
