"""Evidence finder: given a question or topic, list the Quran verses and hadith that bear on it.

This is retrieval, not judgement. It ranks texts of the local corpus (BM25 over normalized, lightly stemmed Arabic
words) and returns each with its exact source, an excerpt and, for hadith, the gradings that scholars gave it.
It never says what the ruling is. An LLM may be used to turn a question (any language) into Arabic search terms;
the evidence itself always comes from the corpus.
"""
import math
import re
from array import array
from collections import Counter, defaultdict
from functools import lru_cache

from app.schemas import EvidenceItem, Grade, Source
from app.services.strength import level_of, strength_of
from app.services.quote_finder import tokenize
from app.services.verifier import Entry, load_corpus, normalize

K1 = 1.2
B = 0.75
MAX_DF_SHARE = 0.4  # words in more than this share of entries carry no information and are skipped
EXCERPT_WORDS = 45
MIN_SCORE = 4.0  # below this a result is too weak to present as evidence

# Question words, particles and generic religious wording that say nothing about the topic (normalized forms).
STOPWORDS = frozenset(
    """
    ما ماذا هل كيف لماذا متي متى اين من في علي على عن الي الى مع هذا هذه ذلك تلك هو هي هم انا نحن انت اذا ان ان لا لم لن قد
    كان كانت يكون تكون او ثم بعد قبل كل بين حتي حتى الذي التي الذين اللذين ذو ذات حكم احكام يجوز يجب هل
    الاسلام اسلام شرعا شرع الشرع الدين ديني
    """.split()
)

_PREFIXES = ("وبال", "وال", "بال", "كال", "فال", "لل", "ال", "ول", "وب", "فب", "و", "ف", "ب", "ل", "ك")
_SUFFIXES = ("ها", "هم", "هن", "كم", "نا", "ات", "ون", "ين", "ان", "ه", "ي", "ك")


@lru_cache(maxsize=None)
def stem(word: str) -> str:
    """Light stemmer: strips common prefixes and suffixes while at least 3 letters remain. For retrieval only."""
    for p in _PREFIXES:
        if word.startswith(p) and len(word) - len(p) >= 3:
            word = word[len(p) :]
            break
    for s in _SUFFIXES:
        if word.endswith(s) and len(word) - len(s) >= 3:
            word = word[: -len(s)]
            break
    return word


_HONORIFIC = ["صلى", "الله", "عليه", "وسلم"]
_AFTER_HONORIFIC = {"قال", "يقول", "فقال", "انه", "ان"}
_MAX_CHAIN_WORDS = 80


def matn_start(text: str) -> int:
    """Character offset where the text of a hadith starts, i.e. after the chain of narrators.

    The chain ends at the first "صلى الله عليه وسلم" (within the first words); a following "قال"/"يقول" is skipped.
    Texts with no such marker early on are returned whole (offset 0).
    """
    words = tokenize(text)
    norms = [w.norm for w in words]
    for i in range(min(_MAX_CHAIN_WORDS, len(words) - 4)):
        if norms[i : i + 4] == _HONORIFIC:
            j = i + 4
            while j < len(words) - 1 and j < i + 6 and norms[j] in _AFTER_HONORIFIC:
                j += 1
            return words[j].start
    return 0


def search_text(entry: Entry) -> str:
    """The part of an entry that is searched: a verse whole, a hadith without its chain of narrators."""
    if entry.classification == "hadith":
        return entry.forms[0] if (start := matn_start(entry.text)) == 0 else normalize(entry.text[start:])
    return entry.forms[0]


def terms(text: str) -> list[str]:
    return [stem(w) for w in normalize(text).split() if w not in STOPWORDS and len(w) > 1]


class Bm25Index:
    def __init__(self, entries: tuple[Entry, ...]):
        self.entries = entries
        postings_docs: dict[str, array] = defaultdict(lambda: array("I"))
        postings_tf: dict[str, array] = defaultdict(lambda: array("H"))
        lengths = array("I")
        for i, entry in enumerate(entries):
            words = terms(search_text(entry))
            lengths.append(len(words))
            for w, tf in Counter(words).items():
                postings_docs[w].append(i)
                postings_tf[w].append(min(tf, 65535))
        self.docs, self.tfs, self.lengths = dict(postings_docs), dict(postings_tf), lengths
        n = len(entries)
        self.avgdl = sum(lengths) / max(n, 1)
        self.idf = {w: math.log(1 + (n - len(d) + 0.5) / (len(d) + 0.5)) for w, d in self.docs.items()}
        self.max_df = MAX_DF_SHARE * n

    def search(
        self, query: dict[str, float], limit: int, classification: str, coordination: bool = True
    ) -> list[tuple[int, float, list[str]]]:
        """Top entries of one classification for weighted query words: (entry index, score, matched words)."""
        scores: dict[int, float] = defaultdict(float)
        matched: dict[int, list[str]] = defaultdict(list)
        usable = {w: x for w, x in query.items() if (d := self.docs.get(w)) is not None and len(d) <= self.max_df}
        total = sum(self.idf[w] * x for w, x in usable.items()) or 1.0
        for word, weight in usable.items():
            docs = self.docs[word]
            idf, tfs = self.idf[word], self.tfs[word]
            for i, tf in zip(docs, tfs):
                if self.entries[i].classification != classification:
                    continue
                norm = 1 - B + B * self.lengths[i] / self.avgdl
                scores[i] += weight * idf * tf * (K1 + 1) / (tf + K1 * norm)
                matched[i].append(word)
        # Coordination: a text that matches more of the question's (rare) words beats one that matches a single
        # word many times, so "شرب الخمر" prefers texts with both words over any text about drinking water.
        for i in scores if coordination else ():
            share = sum(self.idf[w] * usable[w] for w in matched[i]) / total
            scores[i] *= share
        top = sorted(scores, key=scores.__getitem__, reverse=True)[:limit]
        return [(i, scores[i], matched[i]) for i in top]


@lru_cache(maxsize=1)
def index() -> Bm25Index:
    return Bm25Index(load_corpus())


def excerpt(text: str, classification: str, query_words: set[str]) -> str:
    """The stretch of the text (up to EXCERPT_WORDS words) richest in query words; whole text if it is short."""
    start_char = matn_start(text) if classification == "hadith" else 0
    full = text
    text = text[start_char:]
    words = tokenize(text)
    if len(words) <= EXCERPT_WORDS:
        return text
    idf = index().idf
    hit = [idf.get(stem(w.norm), 0.0) if stem(w.norm) in query_words else 0.0 for w in words]
    window = sum(hit[:EXCERPT_WORDS])
    best, best_start = window, 0
    for start in range(1, len(words) - EXCERPT_WORDS + 1):
        window += hit[start + EXCERPT_WORDS - 1] - hit[start - 1]
        if window > best:
            best, best_start = window, start
    first, last = words[best_start], words[best_start + EXCERPT_WORDS - 1]
    text = text[first.start : last.end]
    return ("… " if best_start > 0 else "") + text + (" …" if best_start + EXCERPT_WORDS < len(words) else "")


def item_for(
    entry: Entry,
    query_words: set[str],
    score: float = 0.0,
    matched: list[str] | None = None,
    found_by: list[str] | None = None,
    exact_wording: bool = True,
) -> EvidenceItem:
    return EvidenceItem(
        classification=entry.classification,
        score=round(score, 2),
        matched_terms=sorted(set(matched or [])),
        source=Source(
            book=entry.book,
            chapter=entry.chapter,
            number=entry.number,
            matched_text=excerpt(entry.text, entry.classification, query_words),
            grades=[Grade(name=n, grade=g) for n, g in entry.grades],
            level=level_of(entry.classification, entry.book),
            strength=strength_of(entry.classification, entry.book, entry.grades),
        ),
        full_text=entry.text,
        found_by=found_by or ["keyword"],
        exact_wording=exact_wording,
    )


def _item(i: int, score: float, matched: list[str], query_words: set[str]) -> EvidenceItem:
    return item_for(index().entries[i], query_words, score, matched)



def retrieve(
    question: str, extra_terms: list[str] | None = None, quran_limit: int = 6, hadith_limit: int = 8
) -> tuple[list[tuple[int, float, list[str]]], list[tuple[int, float, list[str]]], dict[str, float]]:
    """(Quran hits, hadith hits, the weighted search words); a hit is (entry index, score, matched words).
    Extra terms (from the LLM) count a little less than the words of the question itself."""
    query: dict[str, float] = {}
    for w in terms(question):
        query[w] = 1.0
    for w in terms(" ".join(extra_terms or [])):
        query.setdefault(w, 0.7)
    if not query:
        return [], [], {}
    idx = index()
    quran, hadith = (
        [hit for hit in idx.search(query, limit, classification) if hit[1] >= MIN_SCORE]
        for classification, limit in (("quran", quran_limit), ("hadith", hadith_limit))
    )
    return quran, hadith, query


def find_evidence(
    question: str, extra_terms: list[str] | None = None, quran_limit: int = 6, hadith_limit: int = 8
) -> tuple[list[EvidenceItem], list[EvidenceItem], list[str]]:
    """(Quran items, hadith items, the search words used)."""
    quran, hadith, query = retrieve(question, extra_terms, quran_limit, hadith_limit)
    words = set(query)
    return (
        [_item(i, s, m, words) for i, s, m in quran],
        [_item(i, s, m, words) for i, s, m in hadith],
        sorted(query),
    )
