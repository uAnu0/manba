"""The evidence card for a question: retrieved texts plus the decision whether to send the person to a scholar.

Three searches feed the card and their rankings are merged (reciprocal rank fusion):
  meaning   - the question's embedding against the embeddings of every verse and hadith (dense.py)
  keyword   - BM25 over normalized Arabic words (evidence.py)
  recitation - texts an LLM recalls for the question that the corpus then confirms (llm_query.py); optional
Only corpus text is ever shown.
"""
import asyncio
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from app.schemas import EvidenceItem, EvidenceResponse, QueryInfo
from app.services.dense import dense_index, embed_query
from app.services.evidence import excerpt, index, item_for, matn_start, retrieve, stem, terms
from app.services.llm_query import judge, suggest_evidence
from app.services.pipeline import _redact
from app.services.verifier import normalize, partial_match, verify_verbatim

RARE_IDF = 5.0  # a word this rare (about 1 text in 300) says a lot about which text is meant
MIN_RARE_WORDS = 2
APPROX_MIN_COVERAGE = 0.75  # share of a recited text that must be verbatim corpus text to accept it as "close"
_ANNOTATION = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]\s*$")  # "(حديث صحيح)" and similar remarks the model may append

QURAN_LIMIT = 8
HADITH_LIMIT = 10
POOL = 30  # candidates taken from each search before merging
JUDGE_POOL = 30  # merged candidates per type shown to the LLM judge
MIN_DIRECT = 3  # "related" texts are added only while fewer than this many are judged direct

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
        ربا فوائد الفوائد بنك بنوك بنكي بنكية قرض قروض سهم أسهم تأمين رهن مضاربة عملات
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

COMMON_IDF = 4.0  # a listed word whose stem is this common in the corpus ("عمل", "عند") is matched only as the exact word


@lru_cache(maxsize=1)
def _markers() -> tuple[dict[str, tuple[set[str], set[str]]], tuple[set[str], set[str]]]:
    """Per topic: (stems, exact words). A word like "عملية" (surgery) stems to "عمل", which is also in "عمله" (his deeds);
    such common stems are not used, the listed word must appear as written."""
    idf = index().idf

    def split(words: str) -> tuple[set[str], set[str]]:
        stems, exact = set(), set()
        for w in words.split():
            n = normalize(w)
            if not n:
                continue
            st = stem(n)
            if re.search("[؀-ۿ]", n) and idf.get(st, float("inf")) < COMMON_IDF:
                exact.add(n)
            else:
                stems.add(st)
        return stems, exact

    return {t: split(w) for t, w in SENSITIVE_TOPICS.items()}, split(PERSONAL_MARKERS)


def _matches(question: str, markers: tuple[set[str], set[str]]) -> bool:
    stems, exact = markers
    words = normalize(question).split()
    forms = set(words) | {w[2:] for w in words if w.startswith("ال") and len(w) > 4}
    return bool(set(terms(question)) & stems) or bool(forms & exact)


@lru_cache(maxsize=1)
def _entry_lookup() -> dict[tuple[str, str, str, str], int]:
    return {(e.classification, e.book, e.number, e.text): i for i, e in enumerate(index().entries)}


def lookup_index(classification: str, book: str, number: str, text: str) -> int | None:
    return _entry_lookup().get((classification, book, number, text))


def referral(question: str, found: int) -> tuple[bool, str | None]:
    topics, personal = _markers()
    for topic, markers in topics.items():
        if _matches(question, markers):
            return True, f"This question touches {topic}: rulings depend on details, so ask a scholar."
    if _matches(question, personal):
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
    keyword: list[list[tuple[int, float, list[str]]]],
    meaning: list[list[tuple[int, float]]],
    recited: list[int],
    limit: int,
) -> list[tuple[int, float, set[str]]]:
    """Merge the rankings: (entry index, fused score, which searches found it), best first.

    `keyword` and `meaning` hold one ranking per query (a claim verifier searches for the claim and for its opposite)."""
    score: dict[int, float] = defaultdict(float)
    found_by: dict[int, set[str]] = defaultdict(set)
    for ranking in keyword:
        for rank, (i, _, _) in enumerate(ranking):
            score[i] += WEIGHT_KEYWORD / (RRF_K + rank + 1)
            found_by[i].add("keyword")
    for ranking in meaning:
        for rank, (i, _) in enumerate(ranking):
            score[i] += WEIGHT_MEANING / (RRF_K + rank + 1)
            found_by[i].add("meaning")
    for rank, i in enumerate(recited):
        score[i] += WEIGHT_RECITATION / (RRF_K + rank + 1)
        found_by[i].add("suggestion")
    top = sorted(score, key=score.__getitem__, reverse=True)[:limit]
    return [(i, score[i], found_by[i]) for i in top]


@dataclass
class Gathered:
    """Candidate texts for one or more queries, before any LLM judgement."""

    entries: tuple
    query_words: set[str]
    words: list[str]
    keyword: dict[str, list[list[tuple[int, float, list[str]]]]]
    meaning: dict[str, list[list[tuple[int, float]]]]
    similarity: dict[int, float]
    recited: dict[str, list[int]]
    exact: dict[int, bool]
    windows: list[EvidenceItem]
    info: QueryInfo
    pool: dict[str, list[tuple[int, float, set[str]]]]

    def item(self, classification: str, i: int, score: float, sources: set[str]) -> EvidenceItem:
        matched = next((m for ranking in self.keyword[classification] for j, _, m in ranking if j == i), [])
        item = item_for(self.entries[i], self.query_words, score * 1000, matched, sorted(sources), self.exact.get(i, True))
        item.similarity = round(self.similarity[i], 3) if i in self.similarity else None
        return item

    def refuse(self, pool_size: dict[str, int]) -> None:
        self.pool = {
            c: fuse(self.keyword[c], self.meaning[c], self.recited[c], pool_size[c]) for c in self.keyword
        }


async def _search(queries: list[str], api_key: str | None, use_meaning: bool) -> tuple[dict, dict, dict, set, set, QueryInfo]:
    """Keyword and meaning search for every query: (keyword, meaning, similarity, words, query_words, info)."""
    info = QueryInfo(used=False)
    query_words: set[str] = set()
    words: set[str] = set()
    keyword: dict[str, list] = {"quran": [], "hadith": []}
    for q in queries:
        query_words |= set(terms(q))
        kw_quran, kw_hadith, w = retrieve(q, None, POOL, POOL)
        keyword["quran"].append(kw_quran)
        keyword["hadith"].append(kw_hadith)
        words |= set(w)

    meaning: dict[str, list] = {"quran": [], "hadith": []}
    similarity: dict[int, float] = {}
    dense = dense_index() if use_meaning else None
    if dense is not None:
        try:
            for qv in await asyncio.gather(*(embed_query(q, api_key) for q in queries)):
                for classification in meaning:
                    ranking = [
                        (i, s) for i, s in dense.search(qv, classification, POOL) if s >= MIN_SIMILARITY[classification]
                    ]
                    meaning[classification].append(ranking)
                    for i, s in ranking:
                        similarity[i] = max(s, similarity.get(i, 0.0))
            info.meaning_used = True
        except Exception as exc:  # keyword search still runs
            info.meaning_error = _redact(f"{type(exc).__name__}: {exc}")
    return keyword, meaning, similarity, words, query_words, info


async def _recite_all(question: str, api_key: str | None, entries: tuple):
    """The model's recitations for the question, looked up in the corpus: (recited, exact, windows, info fields)."""
    recited: dict[str, list[int]] = {"quran": [], "hadith": []}
    exact: dict[int, bool] = {}
    windows: list[EvidenceItem] = []
    fields = {"used": False, "suggested": 0, "found_in_corpus": 0, "rejected": [], "error": None}
    try:
        suggestions = await suggest_evidence(question, api_key=api_key)
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
        fields.update(used=True, suggested=len(suggestions), found_in_corpus=len(exact) + len(windows), rejected=rejected)
    except Exception as exc:
        fields["error"] = _redact(f"{type(exc).__name__}: {exc}")
    return recited, exact, windows, fields


async def gather(
    queries: list[str],
    use_llm: bool,
    api_key: str | None,
    use_meaning: bool,
    pool_size: dict[str, int],
) -> Gathered:
    """Run the searches for every query and merge them: keyword, meaning, and (use_llm) the model's recitations.

    The meaning search and the recitation run at the same time; the recitation is made for the first query."""
    entries = index().entries

    async def nothing():
        return {"quran": [], "hadith": []}, {}, [], {"used": False, "suggested": 0, "found_in_corpus": 0, "rejected": [], "error": None}

    (keyword, meaning, similarity, words, query_words, info), (recited, exact, windows, fields) = await asyncio.gather(
        _search(queries, api_key, use_meaning), _recite_all(queries[0], api_key, entries) if use_llm else nothing()
    )
    for name, value in fields.items():
        setattr(info, name, value)
    g = Gathered(entries, query_words, sorted(words), keyword, meaning, similarity, recited, exact, windows, info, {})
    g.refuse(pool_size)
    return g


async def extend(g: Gathered, queries: list[str], api_key: str | None, use_meaning: bool, pool_size: dict[str, int]) -> Gathered:
    """Add the keyword and meaning rankings of more queries to an existing gather and merge again."""
    keyword, meaning, similarity, words, query_words, info = await _search(queries, api_key, use_meaning)
    for c in g.keyword:
        g.keyword[c] += keyword[c]
        g.meaning[c] += meaning[c]
    for i, s in similarity.items():
        g.similarity[i] = max(s, g.similarity.get(i, 0.0))
    g.query_words |= query_words
    g.words = sorted(set(g.words) | words)
    g.info.meaning_used = g.info.meaning_used or info.meaning_used
    g.info.meaning_error = g.info.meaning_error or info.meaning_error
    g.refuse(pool_size)
    return g


async def build_card(
    question: str, use_llm: bool = False, api_key: str | None = None, use_meaning: bool = True
) -> EvidenceResponse:
    limits = {"quran": QURAN_LIMIT, "hadith": HADITH_LIMIT}
    g = await gather([question], use_llm, api_key, use_meaning, {c: JUDGE_POOL if use_llm else limits[c] for c in limits})
    info, entries, fused = g.info, g.entries, g.pool

    relevance: dict[int, str] = {}
    in_scope = True
    if use_llm:
        # An LLM judge grades every candidate (direct / related / unrelated) and says whether the question is about
        # Islam at all. Unrelated texts are dropped. If the judge fails, the merged order stands.
        try:
            results = await asyncio.gather(
                *(judge(question, [excerpt(entries[i].text, c, g.query_words) for i, _, _ in fused[c]], api_key) for c in limits)
            )
            in_scope = any(on_topic for on_topic, _ in results)
            for c, (_, verdicts) in zip(limits, results):
                candidates = fused[c]
                direct = [t for k, t in enumerate(candidates) if verdicts.get(k) == "direct"]
                related = [t for k, t in enumerate(candidates) if verdicts.get(k) == "related"]
                chosen = direct[: limits[c]]
                if len(direct) < MIN_DIRECT:
                    chosen += related[: limits[c] - len(chosen)]
                relevance.update({i: ("direct" if t in direct else "related") for t in chosen for i in [t[0]]})
                fused[c] = chosen if in_scope else []
            info.reranked = True
        except Exception as exc:
            info.error = (info.error + "; " if info.error else "") + "judge: " + _redact(f"{type(exc).__name__}: {exc}")

    cards: dict[str, list[EvidenceItem]] = {}
    for classification, limit in limits.items():
        items = list(g.windows) if classification == "quran" else []
        for i, score, sources in fused[classification]:
            item = g.item(classification, i, score, sources)
            item.relevance = relevance.get(i)
            items.append(item)
        cards[classification] = (items if in_scope else [])[:limit]

    refer, reason = referral(question, len(cards["quran"]) + len(cards["hadith"]))
    if not in_scope:
        refer, reason = False, "This does not look like a question about Islam, so no texts are shown."
    return EvidenceResponse(
        question=question,
        search_terms=g.words,
        query=info,
        quran=cards["quran"],
        hadith=cards["hadith"],
        refer_to_scholar=refer,
        in_scope=in_scope,
        reason=reason,
        notice_ar=NOTICE_AR,
        notice_en=NOTICE_EN,
    )
