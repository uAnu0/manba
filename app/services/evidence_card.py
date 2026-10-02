"""The evidence card for a question: retrieved texts plus the decision whether to send the person to a scholar."""
import re
from functools import lru_cache

from app.schemas import EvidenceItem, EvidenceResponse, QueryInfo
from app.services.evidence import find_evidence, index, item_for, matn_start, stem, terms
from app.services.llm_query import suggest_evidence
from app.services.pipeline import _redact
from app.services.verifier import Entry, normalize, partial_match, verify_verbatim

RARE_IDF = 5.0  # a word this rare (about 1 text in 300) says a lot about which text is meant
MIN_RARE_WORDS = 2
APPROX_MIN_COVERAGE = 0.75  # share of a recited text that must be verbatim corpus text to accept it as "close"
_ANNOTATION = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]\s*$")  # "(حديث صحيح)" and similar remarks the model may append

QURAN_LIMIT = 8
HADITH_LIMIT = 10

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
def _entry_lookup() -> dict[tuple[str, str, str, str], Entry]:
    return {(e.classification, e.book, e.number, e.text): e for e in index().entries}


def lookup_entry(classification: str, book: str, number: str, text: str) -> Entry | None:
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


def _key(item: EvidenceItem) -> tuple[str, str, str, str]:
    return (item.classification, item.source.book, item.source.number, item.full_text[:80])


def resolve_suggestion(text: str, query_words: set[str]) -> EvidenceItem | None:
    """Find a recalled text in the corpus: verbatim (or as a slice of a corpus text) first, then a close wording."""
    text = _ANNOTATION.sub("", text).strip()
    text = text[matn_start(text):]  # drop a chain of narrators the model may still have added
    seg = verify_verbatim(text)
    if seg and seg.status == "verified" and seg.source and seg.classification in ("quran", "hadith"):
        entry = lookup_entry(seg.classification, seg.source.book, seg.source.number, seg.source.matched_text)
        if entry:
            return item_for(entry, query_words, found_by="suggestion")
        if seg.classification == "quran":  # a multi-verse window such as 112:1-2 has no single entry
            return EvidenceItem(
                classification="quran",
                score=0.0,
                source=seg.source,
                full_text=seg.source.matched_text,
                found_by="suggestion",
            )
    # Close wording: mostly verbatim corpus text with a word or two different. Never a looser match: attaching a
    # recitation to an unrelated text would present unrelated evidence.
    seg = partial_match(text, normalize(text).split())
    if seg and seg.source and seg.confidence >= APPROX_MIN_COVERAGE:
        entry = lookup_entry(seg.classification, seg.source.book, seg.source.number, seg.source.matched_text)
        if entry:
            return item_for(entry, query_words, found_by="suggestion", exact_wording=False)
    entry = rare_words_entry(text)
    if entry:
        return item_for(entry, query_words, found_by="suggestion", exact_wording=False)
    return None


def rare_words_entry(text: str) -> Entry | None:
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
                return idx.entries[i]
    return None


async def build_card(question: str, use_llm: bool = False, api_key: str | None = None) -> EvidenceResponse:
    info = QueryInfo(used=False)
    recalled: list[EvidenceItem] = []
    keyword_words = set(terms(question))
    if use_llm:
        try:
            suggestions = await suggest_evidence(question, api_key)
            rejected = []
            for text in suggestions:
                item = resolve_suggestion(text, keyword_words)
                if item is None:
                    rejected.append(text)
                elif _key(item) not in {_key(r) for r in recalled}:
                    recalled.append(item)
            info = QueryInfo(used=True, suggested=len(suggestions), found_in_corpus=len(recalled), rejected=rejected)
        except Exception as exc:  # keyword search still runs
            info = QueryInfo(used=False, error=_redact(f"{type(exc).__name__}: {exc}"))
    quran, hadith, words = find_evidence(question)
    merged = {"quran": [r for r in recalled if r.classification == "quran"], "hadith": [r for r in recalled if r.classification == "hadith"]}
    for kind, found in (("quran", quran), ("hadith", hadith)):
        seen = {_key(r) for r in merged[kind]}
        merged[kind] += [i for i in found if _key(i) not in seen]
    quran, hadith = merged["quran"][:QURAN_LIMIT], merged["hadith"][:HADITH_LIMIT]
    refer, reason = referral(question, len(quran) + len(hadith))
    return EvidenceResponse(
        question=question,
        search_terms=words,
        query=info,
        quran=quran,
        hadith=hadith,
        refer_to_scholar=refer,
        reason=reason,
        notice_ar=NOTICE_AR,
        notice_en=NOTICE_EN,
    )
