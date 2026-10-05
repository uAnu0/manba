"""Text verification against a reference corpus loaded from data/corpus.json.

data/corpus.json is a list of objects:
    [{"text": "...", "match_text": "...", "source": {"book": "...", "chapter": "...", "number": "..."}}]
`match_text` (modern spelling), `number` and a top-level `classification` ("quran" | "hadith") are optional;
when classification is missing it is inferred from the book name.
"""
import difflib
from collections import defaultdict
import gzip
import json
import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.schemas import Grade, Segment, Source
from app.services.strength import level_of, strength_of

VARIANT_THRESHOLD = 0.60
CANDIDATE_LIMIT = 20
PARTIAL_MIN_WORDS = 3  # shorter phrases are too ambiguous to call a verified quote
VARIANT_MIN_WORDS = 3  # a one- or two-word fragment is never reported as a variant of a verse
VARIANT_RUN_MIN_WORDS = 4  # verbatim parts shorter than this are too common to point at a source
MAX_WINDOW_VERSES = 5  # longest run of consecutive ayahs that can be matched as one quote
WINDOW_CANDIDATE_LIMIT = 10

_ROOT = Path(__file__).resolve().parents[2]
# CORPUS_PATH may hold several files separated by os.pathsep; by default every corpus file that exists is loaded.
CORPUS_PATHS = tuple(
    Path(p) for p in os.getenv("CORPUS_PATH", "").split(os.pathsep) if p
) or tuple(p for p in (_ROOT / "data" / "corpus.json", _ROOT / "data" / "corpus_hadith.json.gz") if p.exists())
CORPUS_PATH = CORPUS_PATHS[0]  # the Quran corpus (kept for tools that validate it)

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


@lru_cache(maxsize=None)  # pure function of the word; the corpus repeats the same words millions of times
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
    verses: int = 1  # number of consecutive ayahs this entry spans (>1 for multi-verse windows)
    grades: tuple[tuple[str, str], ...] = ()  # (scholar, grade) pairs, hadith only
    strict_forms: tuple[str, ...] = ()  # retain ة / ه for the final exact-match check

    @property
    def normalized(self) -> str:
        return self.forms[0]


def normalize_arabic_text(text: str, preserve_taa: bool = False) -> str:
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
    return text if preserve_taa else text.replace("\u0629", "\u0647")


def normalize(text: str, preserve_taa: bool = False) -> str:
    """Arabic normalization, Imlaei spelling exceptions, and case/punctuation/whitespace folding."""
    text = normalize_arabic_text(text, preserve_taa=preserve_taa).lower()
    words = re.sub(r"[^\w\s]", "", text).split()
    return " ".join(_apply_imlaei_exceptions(w) for w in words)


def _infer_classification(book: str) -> str:
    return "quran" if re.search(r"quran|qur'an|قرآن|القرآن", normalize(book) + " " + book, re.I) else "hadith"


@lru_cache(maxsize=1)
def load_corpus() -> tuple[Entry, ...]:
    raw = []
    for path in CORPUS_PATHS:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as f:
            raw.extend(json.load(f))
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
                grades=tuple((g["name"], g["grade"]) for g in item.get("grades", [])),
                strict_forms=tuple(dict.fromkeys(normalize(t, preserve_taa=True) for t in
                                   (item.get("match_text"), item["text"]) if t)) if book == "القرآن الكريم" else (),
            )
        )
    return tuple(entries)


def split_segments(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?؟\n])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


class CorpusIndex:
    """Inverted word index plus exact-text lookup over a list of entries."""

    def __init__(self, entries: list[Entry] | tuple[Entry, ...]):
        self.entries = tuple(entries)
        words: dict[str, set[int]] = defaultdict(set)
        exact: dict[str, list[int]] = defaultdict(list)
        for i, entry in enumerate(self.entries):
            for form in entry.forms:
                exact[form].append(i)
                for word in form.split():
                    words[word].add(i)
        self._words = {w: tuple(ids) for w, ids in words.items()}
        self._exact = {text: tuple(ids) for text, ids in exact.items()}
        n = max(len(self.entries), 1)
        self._idf = {w: math.log(1 + n / len(ids)) for w, ids in self._words.items()}
        self._unseen_idf = math.log(1 + n)
        entry_words: list[set[str]] = [set() for _ in self.entries]
        for w, ids in self._words.items():
            for i in ids:
                entry_words[i].add(w)
        self._entry_weight = [sum(self._idf[w] for w in ws) for ws in entry_words]

    def candidates(self, norm: str, limit: int) -> list[Entry]:
        """Top entries by IDF-weighted Jaccard overlap of words.

        Rare shared words count most, and entries stuffed with unrelated words (long multi-verse
        windows) are penalized, so tight matches outrank them.
        """
        query_weight = 0.0
        overlap: dict[int, float] = defaultdict(float)
        for word in set(norm.split()):
            postings = self._words.get(word)
            if postings is None:
                query_weight += self._unseen_idf
                continue
            weight = self._idf[word]
            query_weight += weight
            for i in postings:
                overlap[i] += weight
        scores = {i: o / (query_weight + self._entry_weight[i] - o) for i, o in overlap.items()}
        top = sorted(scores, key=scores.__getitem__, reverse=True)[:limit]
        return [self.entries[i] for i in top]

    def word_idf(self, word: str) -> float:
        return self._idf.get(word, self._unseen_idf)

    def find_exact(self, norm: str) -> list[Entry]:
        return [self.entries[i] for i in self._exact.get(norm, ())]

    def find_containing(self, norm: str) -> list[Entry]:
        """Entries that contain `norm` as a run of consecutive whole words."""
        words = norm.split()
        if len(words) < PARTIAL_MIN_WORDS:
            return []
        postings = [self._words.get(w, ()) for w in set(words)]
        if not all(postings):
            return []
        ids = set(min(postings, key=len))
        for p in postings:
            ids.intersection_update(p)
        needle = f" {norm} "
        return [self.entries[i] for i in sorted(ids) if any(needle in f" {form} " for form in self.entries[i].forms)]


_VERSE_REF = re.compile(r"^(\d+):(\d+)$")


def _merge_verses(members: list[Entry]) -> Entry:
    """One entry for a run of consecutive ayahs, e.g. 112:1-2."""
    first, last = members[0], members[-1]
    n_forms = max(len(m.forms) for m in members)
    forms = tuple(
        dict.fromkeys(
            " ".join(m.forms[min(k, len(m.forms) - 1)] for m in members) for k in range(n_forms)
        )
    )
    return Entry(
        classification=first.classification,
        book=first.book,
        chapter=first.chapter,
        number=f"{first.number}-{last.number.split(':')[1]}",
        text=" ".join(m.text for m in members),
        forms=forms,
        verses=len(members),
        strict_forms=tuple(dict.fromkeys(" ".join((m.strict_forms or (normalize(m.text, preserve_taa=True),))[
            min(k, len(m.strict_forms or (m.text,)) - 1)] for m in members) for k in range(2))),
    )


def build_windows(entries: tuple[Entry, ...]) -> list[Entry]:
    """Every run of 2..MAX_WINDOW_VERSES consecutive ayahs of the same surah ("sura:ayah" numbers only)."""
    windows = []
    for start, first in enumerate(entries):
        m = _VERSE_REF.match(first.number)
        if not m:
            continue
        sura, ayah = int(m[1]), int(m[2])
        members = [first]
        for nxt in entries[start + 1 : start + MAX_WINDOW_VERSES]:
            n = _VERSE_REF.match(nxt.number)
            if not n or (nxt.book, int(n[1]), int(n[2])) != (first.book, sura, ayah + len(members)):
                break
            members.append(nxt)
            windows.append(_merge_verses(members))
    return windows


@lru_cache(maxsize=1)
def verse_index() -> CorpusIndex:
    """Single Quran verses. Quran and hadith are indexed separately: hadith texts quote verses, and a
    verse quoted inside a hadith must not outrank (or inflate the match count of) the verse itself."""
    return CorpusIndex([e for e in load_corpus() if e.classification == "quran"])


@lru_cache(maxsize=1)
def window_index() -> CorpusIndex:
    return CorpusIndex(build_windows(tuple(e for e in load_corpus() if e.classification == "quran")))


@lru_cache(maxsize=1)
def hadith_index() -> CorpusIndex:
    return CorpusIndex([e for e in load_corpus() if e.classification != "quran"])


# Hadith texts are long and full of everyday words, so a short run of common words ("ما رأيك في هذا",
# "قال رسول الله صلى الله عليه وسلم") occurs somewhere and says nothing about which hadith is meant.
# A phrase counts as a hadith quote only if it contains distinctive words. Thresholds were tuned on the
# golden hadith quotes (second-rarest word IDF 4.2-8.2, total 13.9-42) against everyday phrases that
# occur in the corpus (second-rarest 2.0-2.4, total 7-15); see golden/quran_golden.json (category hadith).
HADITH_MIN_SECOND_IDF = 4.0
HADITH_MIN_TOTAL_IDF = 12.0


# Stricter bar for text that is NOT already known to be a claim: runs picked out of plain speech, and verbatim
# parts of an unrecognised text. With the nine-book corpus, everyday phrases such as "أريد أن أسألك عن" or
# "الحمد لله على كل حال" occur inside narrations and pass the normal bar (second-rarest IDF 4.6-5.5, total
# 13-20), while the distinctive golden quotes sit at 6.1+ and 18+.
HADITH_STRICT_SECOND_IDF = 5.5
HADITH_STRICT_TOTAL_IDF = 18.0


def has_hadith_content(norm: str, strict: bool = False) -> bool:
    second, total = (HADITH_STRICT_SECOND_IDF, HADITH_STRICT_TOTAL_IDF) if strict else (HADITH_MIN_SECOND_IDF, HADITH_MIN_TOTAL_IDF)
    idfs = sorted(hadith_index().word_idf(w) for w in norm.split())
    return len(idfs) >= 2 and idfs[-2] >= second and sum(idfs) >= total


def similarity(a: str, b: str) -> float:
    """Mean of character-level and word-level similarity.

    Character similarity alone is inflated for short texts (an unrelated three-word saying can share
    two thirds of its letters with a verse); word similarity alone ignores spelling slips inside a word.
    """
    chars = difflib.SequenceMatcher(None, a, b).ratio()
    words = difflib.SequenceMatcher(None, a.split(), b.split(), autojunk=False).ratio()
    return (chars + words) / 2


def find_best_match(segment: str) -> tuple[Entry | None, float, str]:
    """Best fuzzy match over single verses and multi-verse windows: (entry, similarity, best normalized form)."""
    norm = normalize(segment)
    candidates = (
        verse_index().candidates(norm, CANDIDATE_LIMIT)
        + window_index().candidates(norm, WINDOW_CANDIDATE_LIMIT)
        + hadith_index().candidates(norm, WINDOW_CANDIDATE_LIMIT)
    )
    best, best_score, best_form = None, 0.0, ""
    for entry in candidates:
        for form in entry.forms:
            score = similarity(norm, form)
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
        grades=[Grade(name=n, grade=g) for n, g in entry.grades],
        level=level_of(entry.classification, entry.book),
        strength=strength_of(entry.classification, entry.book, entry.grades),
    )


def _short_vowels(word: str) -> dict[int, set[str]]:
    # Compare only ordinary aligned letters; Uthmani shorthand with a different
    # number of written letters needs its separate matching form.
    letters = [c for c in word if c.isalpha()]
    if "".join(normalize(c, preserve_taa=True) for c in letters) != normalize(word, preserve_taa=True):
        return {}
    out: dict[int, set[str]] = defaultdict(set)
    pos = -1
    for c in word:
        if c.isalpha():
            pos += 1
        elif "\u064b" <= c <= "\u0650" and pos >= 0:
            out[pos].add(c)
    return dict(out)


def _vowel_conflict(segment: str, entry: Entry) -> bool:
    if entry.classification != "quran":
        return False
    wanted = [w for w in segment.split() if normalize(w)]
    words = [w for w in entry.text.split() if normalize(w)]
    norms = [normalize(w) for w in words]
    target = [normalize(w) for w in wanted]
    for at in range(len(words) - len(wanted) + 1):
        if norms[at:at + len(wanted)] != target:
            continue
        for left, right in zip(wanted, words[at:at + len(wanted)]):
            left_letters = [c for c in left if c.isalpha()]
            right_letters = [c for c in right if c.isalpha()]
            if len(left_letters) == len(right_letters) and any(
                a in "أإ" and b in "أإ" and a != b for a, b in zip(left_letters, right_letters)
            ):
                return True
            source_vowels = _short_vowels(right)
            if any(pos in source_vowels and marks != source_vowels[pos] for pos, marks in _short_vowels(left).items()):
                return True
        return False
    return False


def _verified(segment: str, entry: Entry, match_type: str, others: int) -> Segment:
    strict = normalize(segment, preserve_taa=True)
    forms = entry.strict_forms or (normalize(entry.text, preserve_taa=True),)
    changed_letters = not any(f" {strict} " in f" {form} " for form in forms)
    if changed_letters or _vowel_conflict(segment, entry):
        return Segment(segment_text=segment, classification=entry.classification, status="semantic_variant",
                       match_type=match_type, confidence=1.0, source=_source(entry, others),
                       differences=["letter spelling differs from the source (ة / ه)" if changed_letters else
                                    "explicit vowels or hamza differ from the Mushaf"])
    return Segment(
        segment_text=segment,
        classification=entry.classification,
        status="verified",
        match_type=match_type,
        confidence=1.0,
        source=_source(entry, others),
    )


def _first_containing(phrase: str) -> Entry | None:
    """The corpus entry that holds `phrase` verbatim (verse, then multi-verse window, then hadith), if any."""
    found = verse_index().find_containing(phrase) or window_index().find_containing(phrase)
    if not found and has_hadith_content(phrase, strict=True):
        found = hadith_index().find_containing(phrase)
    return found[0] if found else None


def verbatim_parts(words: list[str]) -> list[tuple[int, int, Entry]]:
    """Maximal runs [i, j) of >= VARIANT_RUN_MIN_WORDS words found word for word in the corpus, left to right."""
    parts, i = [], 0
    while i + VARIANT_RUN_MIN_WORDS <= len(words):
        entry = _first_containing(" ".join(words[i : i + VARIANT_RUN_MIN_WORDS]))
        if entry is None:
            i += 1
            continue
        j = i + VARIANT_RUN_MIN_WORDS
        while j < len(words):
            longer = _first_containing(" ".join(words[i : j + 1]))
            if longer is None:
                break
            entry, j = longer, j + 1
        parts.append((i, j, entry))
        i = j
    return parts


def _label(entry: Entry) -> str:
    return f"{entry.chapter} {entry.number}".strip() if entry.number else f"{entry.book}, {entry.chapter}".strip(", ")


def partial_match(segment: str, words: list[str]) -> Segment | None:
    """A text that is neither a quote nor a clean variant but is built from real quoted parts.

    Reported as a variant of the entry holding its longest verbatim part, with the matching and the
    non-matching stretches listed in reading order, instead of a bare "baseless".
    """
    parts = verbatim_parts(words)
    if not parts:
        return None
    longest = max(parts, key=lambda p: p[1] - p[0])
    differences, pos = [], 0
    for i, j, entry in parts:
        if i > pos:
            differences.append(f"not found in the corpus: '{' '.join(words[pos:i])}'")
        differences.append(f"verbatim: '{' '.join(words[i:j])}' ({_label(entry)})")
        pos = j
    if pos < len(words):
        differences.append(f"not found in the corpus: '{' '.join(words[pos:])}'")
    covered = sum(j - i for i, j, _ in parts)
    entry = longest[2]
    return Segment(
        segment_text=segment,
        classification=entry.classification,
        status="semantic_variant",
        confidence=round(covered / len(words), 2),
        source=_source(entry),
        differences=differences,
    )


def verify_verbatim(segment: str, norm: str | None = None) -> Segment | None:
    """The fast, exact stages of verification: the text is a verse, part of a verse, a run of consecutive verses
    or part of a hadith, word for word. None if it is none of these (no fuzzy matching is attempted)."""
    norm = norm if norm is not None else normalize(segment)
    verses, windows = verse_index(), window_index()

    # Word-for-word match after normalization; a high character score alone is never enough.
    exact = verses.find_exact(norm)
    if exact:
        return _verified(segment, exact[0], "full", len(exact) - 1)

    # A run of consecutive words quoted from inside one verse.
    containing = verses.find_containing(norm)
    if containing:
        return _verified(segment, containing[0], "partial", len(containing) - 1)

    # Several consecutive verses quoted whole (112:1-2) ...
    exact = windows.find_exact(norm)
    if exact:
        return _verified(segment, exact[0], "full", len(exact) - 1)

    # ... or a phrase that crosses a verse boundary. Use the tightest window(s) that hold it.
    containing = windows.find_containing(norm)
    if containing:
        tightest = min(e.verses for e in containing)
        tight = [e for e in containing if e.verses == tightest]
        return _verified(segment, tight[0], "partial", len(tight) - 1)

    # Hadith: the quote is usually a slice of a long entry (chain of narrators + text).
    if has_hadith_content(norm):
        hadiths = hadith_index()
        exact = hadiths.find_exact(norm)
        if exact:
            return _verified(segment, exact[0], "full", len(exact) - 1)
        containing = hadiths.find_containing(norm)
        if containing:
            return _verified(segment, containing[0], "partial", len(containing) - 1)
    return None


def verify_segment(segment: str, run_variants: bool = True) -> Segment:
    norm = normalize(segment)
    verbatim = verify_verbatim(segment, norm)
    if verbatim:
        return verbatim

    entry, score, form = find_best_match(segment)
    if entry is None or score < VARIANT_THRESHOLD or len(norm.split()) < VARIANT_MIN_WORDS:
        if run_variants:
            built_from_quotes = partial_match(segment, norm.split())
            if built_from_quotes:
                return built_from_quotes
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
