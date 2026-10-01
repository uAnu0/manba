"""Locate Quran quotes inside longer text such as a sermon, without any LLM.

Two kinds of quote are found:

* Marked claims (regions). Text inside quote marks or brackets (﴿ ﴾ « » " " ( ) [ ]) and text that follows an
  attribution such as "قال تعالى" up to the next punctuation mark. The whole region is the claim and goes
  through verify_segment, so an altered or invented quote comes back as a variant or baseless instead of
  being trimmed down to the part that happens to match.
* Verbatim runs. Outside any region, every run of SPAN_MIN_WORDS or more consecutive words that appears
  word for word in the corpus (a verse or a window of consecutive verses) is reported as a verified quote.
  Only exact runs are reported here; unmarked quotes with altered words need the LLM step.
"""
import re
from dataclasses import dataclass

from app.schemas import Segment
from app.services.verifier import normalize, verify_segment, verse_index, window_index

SPAN_MIN_WORDS = 4  # unmarked runs: shorter ones are common speech ("في سبيل الله") and too noisy
REGION_MIN_WORDS = 3
ATTRIBUTION_LOOKBACK = 6
MAX_RUN_WORDS = 400

# Normalized forms (see verifier.normalize): said-verbs, and words that mark God / the Quran as the speaker.
SAID = {"قال", "وقال", "فقال", "يقول", "ويقول", "قوله", "وقوله", "فيقول"}
SPEAKER = {
    "تعالى", "وتعالى", "سبحانه", "وسبحانه", "جل", "وجل", "عز", "وعز", "وعلا", "الله", "ربنا", "ربكم",
}
CONTEXT = {"التنزيل", "القران", "الايه", "الايات", "ايه", "كتابه", "محكم"}  # "في محكم التنزيل", "في كتابه"

_QURAN_BRACKETS = "[﴾﴿]"
BRACKET_PATTERNS = (
    ("quran", re.compile(_QURAN_BRACKETS + "(.*?)" + _QURAN_BRACKETS, re.S)),
    ("guillemets", re.compile("«(.*?)»", re.S)),
    ("curly", re.compile("“(.*?)”", re.S)),
    ("straight", re.compile('"(.*?)"', re.S)),
    ("round", re.compile(r"\((.*?)\)", re.S)),
    ("square", re.compile(r"\[(.*?)\]", re.S)),
)
# End of an unbracketed attributed quote: sentence/clause punctuation or the start of another bracket.
_CLAUSE_END = re.compile("[.؟!؛،\n]|" + _QURAN_BRACKETS + "|[«“\"(\\[]")
_TRIM = " \t\r\n:.،؛؟!()[]«»“”\"﴾﴿-"


@dataclass(frozen=True)
class Word:
    norm: str
    start: int
    end: int


@dataclass(frozen=True)
class Region:
    start: int  # outer span, brackets included
    end: int
    text_start: int  # the claimed text itself
    text_end: int
    kind: str
    attributed: bool


def tokenize(text: str) -> list[Word]:
    """Whitespace tokens with their normalized form and position; punctuation-only tokens are dropped."""
    words = []
    for m in re.finditer(r"\S+", text):
        norm = normalize(m.group())
        if norm:
            words.append(Word(norm, m.start(), m.end()))
    return words


def _attributed_before(words: list[Word], pos: int) -> bool:
    """Is a speaker/context word (تعالى, التنزيل ...) among the few words just before `pos`?"""
    before = [w.norm for w in words if w.end <= pos][-ATTRIBUTION_LOOKBACK:]
    return any(w in SPEAKER or w in CONTEXT for w in before)


def _word_count(text: str) -> int:
    return len(normalize(text).split())


def find_regions(text: str, words: list[Word]) -> list[Region]:
    regions: list[Region] = []

    def overlaps(start: int, end: int) -> bool:
        return any(start < r.end and r.start < end for r in regions)

    for kind, pattern in BRACKET_PATTERNS:
        for m in pattern.finditer(text):
            if overlaps(m.start(), m.end()) or _word_count(m.group(1)) < REGION_MIN_WORDS:
                continue
            attributed = kind == "quran" or _attributed_before(words, m.start())
            regions.append(Region(m.start(), m.end(), m.start(1), m.end(1), kind, attributed))

    # Unbracketed: "قال تعالى إن مع العسر يسرا" -> the claim is what follows the attribution.
    i = 0
    while i < len(words):
        if words[i].norm in SAID:
            marker = next((k for k in range(i + 1, min(i + 4, len(words))) if words[k].norm in SPEAKER), None)
            if marker is not None:
                first = marker + 1
                while first < len(words) and words[first].norm in SPEAKER:
                    first += 1
                if first < len(words):
                    start = words[first].start
                    m = _CLAUSE_END.search(text, start)
                    end = m.start() if m else len(text)
                    if not overlaps(start, end) and _word_count(text[start:end]) >= REGION_MIN_WORDS:
                        regions.append(Region(start, end, start, end, "attributed", True))
                    while i < len(words) and words[i].start < end:
                        i += 1
                    continue
        i += 1
    return sorted(regions, key=lambda r: r.start)


def _contained(norms: list[str]) -> bool:
    phrase = " ".join(norms)
    return bool(verse_index().find_containing(phrase) or window_index().find_containing(phrase))


def find_runs(words: list[Word], blocked: set[int]) -> list[tuple[int, int]]:
    """Maximal runs [i, j) of >= SPAN_MIN_WORDS words that appear verbatim in the corpus."""
    runs, i = [], 0
    while i < len(words):
        if i in blocked or i + SPAN_MIN_WORDS > len(words):
            i += 1
            continue
        limit = i
        while limit < len(words) and limit not in blocked and limit - i < MAX_RUN_WORDS:
            limit += 1
        if limit - i < SPAN_MIN_WORDS or not _contained([w.norm for w in words[i : i + SPAN_MIN_WORDS]]):
            i += 1
            continue
        j = i + SPAN_MIN_WORDS
        while j < limit and _contained([w.norm for w in words[i : j + 1]]):
            j += 1
        runs.append((i, j))
        i = j
    return runs


def locate_quotes(text: str) -> list[Segment]:
    """Quran quotes in `text`, in reading order. Plain commentary is not reported."""
    words = tokenize(text)
    regions = find_regions(text, words)
    found: list[tuple[int, Segment]] = []

    for r in regions:
        claim = text[r.text_start : r.text_end].strip(_TRIM)
        if not claim:
            continue
        segment = verify_segment(claim)
        # Brackets and quote marks are also used for citations and asides: keep an unattributed
        # region only if it actually resembles the Quran.
        if r.attributed or segment.status != "baseless":
            found.append((r.start, segment))

    blocked = {k for k, w in enumerate(words) if any(r.start <= w.start < r.end for r in regions)}
    for i, j in find_runs(words, blocked):
        claim = text[words[i].start : words[j - 1].end].strip(_TRIM)
        segment = verify_segment(claim)
        if segment.status == "verified":
            found.append((words[i].start, segment))

    return [segment for _, segment in sorted(found, key=lambda item: item[0])]
