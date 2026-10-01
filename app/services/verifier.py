"""Text verification against a reference corpus loaded from corpus.json.

corpus.json is a list of objects:
    [{"text": "...", "match_text": "...", "source": {"book": "...", "chapter": "...", "number": "..."}}]
`match_text` (modern spelling), `number` and a top-level `classification` ("quran" | "hadith") are optional;
when classification is missing it is inferred from the book name.
"""
import difflib
from collections import defaultdict
import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.schemas import Segment, Source, VerifyResponse

VARIANT_THRESHOLD = 0.60
CANDIDATE_LIMIT = 20
PARTIAL_MIN_WORDS = 3  # shorter phrases are too ambiguous to call a verified quote

CORPUS_PATH = Path(os.getenv("CORPUS_PATH", Path(__file__).resolve().parents[2] / "corpus.json"))

_DAGGER_ALEF = "\u0670"
_MARKS = "[ً-ٟ]*"
# Dagger alef on alef maqsura (على, موسى) is the same sound as the maqsura: drop it, don't add an alef.
# Only U+0649: after a true yaa (U+064A) it is a long a (القيامة, آيات) and must become an alef.
_DAGGER_AFTER_MAQSURA = re.compile("([\u0649]" + _MARKS + ")\u0670")
# Uthmani waw + dagger alef before taa marbuta (الصلوٰة) is Imlaei alef (الصلاة): the waw becomes alef.
_WAW_DAGGER_TAA = re.compile("و" + _MARKS + "ٰ(?=" + _MARKS + "ة)")
# Tashkeel (fathatan..sukun), superscript alef, and Quranic annotation marks.
_DIACRITICS = re.compile("[\u064B-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL = "\u0640"
_ALEF_FORMS = re.compile("[\u0623\u0625\u0622\u0671]")  # alef with hamza above/below, alef madda, alef wasla


# Uthmani spellings (after dagger-alef expansion) -> standard Imlaei spellings.
IMLAEI_EXCEPTIONS = {
    "ذالك": "ذلك",
    "كذالك": "كذلك",
    "ذالكم": "ذلكم",
    "الرحمان": "الرحمن",
    "هاذا": "هذا",
    "هاذه": "هذه",
    "هاذان": "هذان",
    "هاؤلاء": "هؤلاء",
    "لاكن": "لكن",
    "اولائك": "اولئك",
    "الاه": "اله",
    "الالاه": "الاله",
    "ياسين": "يس",
    "طاها": "طه",
    # Orthography gaps found in the corpus: Uthmani riba is written ربوا + dagger alef (-> الربواا),
    # and Ibrahim appears both as ابراهيم and as ابراهم (small yeh stripped); ابرهيم is the rasm spelling.
    "الربواا": "الربا",
    "الربوا": "الربا",
    "ابراهم": "ابراهيم",
    "ابرهيم": "ابراهيم",
}
# Clitic letters (wa, fa, ba, la, ka, sa, hamzat al-istifham) that may precede an exception word,
# and pronoun/dual/plural endings that may follow it, e.g. ولاكنهم, افبهاذا, الاهكم.
_PREFIX_LETTERS = set("\u0648\u0641\u0628\u0644\u0643\u0633\u0627")
_SUFFIXES = ("", "\u0647", "\u0647\u0627", "\u0647\u0645", "\u0647\u0645\u0627", "\u0647\u0646", "\u0643", "\u0643\u0645",
             "\u0643\u0645\u0627", "\u0643\u0646", "\u0646\u0627", "\u064A", "\u0649", "\u064A\u0646", "\u0627\u0646",
             "\u0627", "\u0644\u0647", "\u0648\u0646", "\u0645", "\u0646")
_MAX_PREFIX = 3


def _apply_imlaei_exceptions(word: str) -> str:
    """Whole-word replacement, allowing up to three clitic letters before and a pronoun ending after.

    Never a substring replace: the stem must be the entire word minus those affixes.
    """
    for i in range(min(_MAX_PREFIX, len(word)) + 1):
        if not all(ch in _PREFIX_LETTERS for ch in word[:i]):
            break
        rest = word[i:]
        for suffix in _SUFFIXES:
            if rest.endswith(suffix) and rest[: len(rest) - len(suffix)] in IMLAEI_EXCEPTIONS:
                return word[:i] + IMLAEI_EXCEPTIONS[rest[: len(rest) - len(suffix)]] + suffix
    return word


@dataclass(frozen=True)
class Entry:
    classification: str
    book: str
    chapter: str
    number: str
    text: str
    forms: tuple[str, ...]  # normalized spellings to match against; forms[0] is the primary one

    @property
    def normalized(self) -> str:
        return self.forms[0]


def normalize_arabic_text(text: str) -> str:
    """Convert dagger alef to alef, strip tashkeel and tatweel, unify Alef forms to bare Alef and Taa Marbuta to Haa."""
    # Uthmani shorthand -> Imlaei spelling (e.g. العٰلمين -> العالمين); must run before diacritics are stripped.
    text = _DAGGER_AFTER_MAQSURA.sub(r"\1", text)
    text = _WAW_DAGGER_TAA.sub("\u0627", text)
    text = text.replace(_DAGGER_ALEF, "\u0627")
    text = _DIACRITICS.sub("", text)
    text = text.replace(_TATWEEL, "")
    text = _ALEF_FORMS.sub("\u0627", text)
    # Uthmani writes alef madda as hamza + alef (ءاتوا -> اتوا, matching آتوا after normalization).
    text = text.replace("\u0621\u0627", "\u0627")
    return text.replace("\u0629", "\u0647")


def normalize(text: str) -> str:
    """Arabic normalization, Imlaei spelling exceptions, and case/punctuation/whitespace folding."""
    text = normalize_arabic_text(text).lower()
    words = re.sub(r"[^\w\s]", "", text).split()
    return " ".join(_apply_imlaei_exceptions(w) for w in words)


def _infer_classification(book: str) -> str:
    return "quran" if re.search(r"quran|qur'an|قرآن|القرآن", normalize(book) + " " + book, re.I) else "hadith"


@lru_cache(maxsize=1)
def load_corpus() -> tuple[Entry, ...]:
    with open(CORPUS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    entries = []
    for item in raw:
        src = item.get("source", {})
        book = src.get("book", "")
        # `match_text` is the modern-spelling text (Tanzil simple-clean for the Quran); `text` is the
        # reference/display text (Uthmani). Both are accepted as input, so copy-pasted mushaf text also matches.
        forms = tuple(dict.fromkeys(normalize(t) for t in (item.get("match_text"), item["text"]) if t))
        entries.append(
            Entry(
                classification=item.get("classification") or _infer_classification(book),
                book=book,
                chapter=src.get("chapter", ""),
                number=str(src.get("number", "")),
                text=item["text"],
                forms=forms,
            )
        )
    return tuple(entries)


def split_segments(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?؟\n])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


@lru_cache(maxsize=1)
def _word_index() -> dict[str, tuple[int, ...]]:
    """Inverted index: normalized word -> indices of corpus entries containing it."""
    index: dict[str, set[int]] = defaultdict(set)
    for i, entry in enumerate(load_corpus()):
        for form in entry.forms:
            for word in form.split():
                index[word].add(i)
    return {w: tuple(ids) for w, ids in index.items()}


def candidate_entries(norm: str, limit: int = CANDIDATE_LIMIT) -> list[Entry]:
    """Top entries by IDF-weighted word overlap, so rare shared words count most."""
    corpus, index = load_corpus(), _word_index()
    scores: dict[int, float] = defaultdict(float)
    for word in set(norm.split()):
        postings = index.get(word, ())
        for i in postings:
            scores[i] += 1.0 / len(postings)
    # Ties (common in short queries) are broken toward entries of similar length.
    top = sorted(scores, key=lambda i: (-scores[i], abs(len(corpus[i].normalized) - len(norm))))[:limit]
    return [corpus[i] for i in top]


@lru_cache(maxsize=1)
def _exact_index() -> dict[str, tuple[int, ...]]:
    """Normalized text -> corpus entries with exactly that text (repeated verses share one key)."""
    index: dict[str, list[int]] = defaultdict(list)
    for i, entry in enumerate(load_corpus()):
        for form in entry.forms:
            index[form].append(i)
    return {text: tuple(ids) for text, ids in index.items()}


def find_exact(norm: str) -> list[Entry]:
    corpus = load_corpus()
    return [corpus[i] for i in _exact_index().get(norm, ())]


def find_containing(norm: str) -> list[Entry]:
    """Entries that contain `norm` as a run of consecutive whole words."""
    words = norm.split()
    if len(words) < PARTIAL_MIN_WORDS:
        return []
    index, corpus = _word_index(), load_corpus()
    postings = [index.get(w, ()) for w in set(words)]
    if not all(postings):
        return []
    ids = set(min(postings, key=len))
    for p in postings:
        ids.intersection_update(p)
    needle = f" {norm} "
    return [corpus[i] for i in sorted(ids) if any(needle in f" {form} " for form in corpus[i].forms)]


def find_best_match(segment: str) -> tuple[Entry | None, float, str]:
    """Best fuzzy match: (entry, similarity, the normalized form of the entry that scored best)."""
    norm = normalize(segment)
    best, best_score, best_form = None, 0.0, ""
    for entry in candidate_entries(norm):
        for form in entry.forms:
            score = difflib.SequenceMatcher(None, norm, form).ratio()
            if score > best_score:
                best, best_score, best_form = entry, score, form
    return best, best_score, best_form


def word_differences(segment: str, reference: str) -> list[str]:
    a, b = normalize(segment).split(), normalize(reference).split()
    diffs = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if op == "replace":
            diffs.append(f"'{' '.join(a[i1:i2])}' differs from '{' '.join(b[j1:j2])}'")
        elif op == "delete":
            diffs.append(f"extra words: '{' '.join(a[i1:i2])}'")
        elif op == "insert":
            diffs.append(f"missing words: '{' '.join(b[j1:j2])}'")
    return diffs


def _source(entry: Entry, other_matches: int = 0) -> Source:
    return Source(
        book=entry.book,
        chapter=entry.chapter,
        number=entry.number,
        matched_text=entry.text,
        other_matches_count=other_matches,
    )


def verify_segment(segment: str) -> Segment:
    norm = normalize(segment)

    # Word-for-word match after normalization; a high character score alone is never enough.
    exact = find_exact(norm)
    if exact:
        entry = exact[0]
        return Segment(
            segment_text=segment,
            classification=entry.classification,
            status="verified",
            confidence=1.0,
            source=_source(entry, len(exact) - 1),
        )

    # A run of consecutive words quoted from inside a longer entry.
    containing = find_containing(norm)
    if containing:
        entry = containing[0]
        return Segment(
            segment_text=segment,
            classification=entry.classification,
            status="verified",
            match_type="partial",
            confidence=1.0,
            source=_source(entry, len(containing) - 1),
        )

    entry, score, form = find_best_match(segment)
    if entry is None or score < VARIANT_THRESHOLD:
        return Segment(
            segment_text=segment,
            classification="unverified",
            status="baseless",
            confidence=round(1 - score, 2),
        )
    return Segment(
        segment_text=segment,
        classification=entry.classification,
        status="semantic_variant",
        confidence=round(score, 2),
        source=_source(entry),
        differences=word_differences(segment, form),
    )


def verify_text(text: str) -> VerifyResponse:
    return VerifyResponse(
        original_text=text,
        word_count=len(text.split()),
        segments=[verify_segment(s) for s in split_segments(text)],
    )
