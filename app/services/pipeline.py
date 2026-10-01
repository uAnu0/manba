"""Text-level verification.

Local pass (always): split into sentences, verify each; long or unrecognised sentences go through the
quote finder so quotes inside commentary are located.

LLM pass (opt-in): an LLM reads the text and lists the quotes/claims it sees. The LLM never decides
anything about truth. Each claim it returns must appear in the original text (otherwise it is rejected),
is cut from the original wording, and is verified by the same local engine. A claim only replaces local
results that were NOT verified and that overlap it; verified local results are never touched.
"""
import re

from app.schemas import ExtractionInfo, Segment, VerifyResponse
from app.services.llm_extractor import extract_claims
from app.services.quote_finder import REGION_MIN_WORDS, Located, locate_quotes, tokenize, _TRIM
from app.services.verifier import normalize, verify_segment

# Up to this many words, a sentence that resembles a verse is checked as a whole: it is most likely a single
# quote, and an altered or partly invented one must be reported as such. Longer sentences are sermon-style
# prose with quotes inside, so the quotes are located first.
SENTENCE_REFINE_MIN_WORDS = 12

# If unmarked verbatim runs make up at least this share of a sentence, the sentence IS a quote (with a changed,
# added or dropped word somewhere), not commentary around quotes: keep it whole so the change is reported
# instead of being trimmed away behind the part that matches.
MAX_RUN_COVERAGE = 0.6

# A sentence that cites a hadith or verse is making (or discussing) a religious claim even when the LLM
# extracted nothing from it, e.g. "ويقول بعض الناس اختلاف أمتي رحمة، وهذا الحديث لا أصل له": it stays a claim
# and is never demoted to commentary. Praise formulas ("نبينا محمد", "سبحانه وتعالى") are deliberately not cues.
HARD_CUES = frozenset("حديث الحديث احاديث الاحاديث روى رواه روي اخرجه الايه ايه الايات القران قرانا".split())
SAID_VERBS = frozenset("قال وقال فقال يقول ويقول قالت قوله وقوله".split())
SOURCE_WORDS = frozenset("النبي رسول تعالى سبحانه".split())

_SENTENCE_BREAK = re.compile(r"(?<=[.!?؟\n])\s+")


def sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _SENTENCE_BREAK.finditer(text):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def _has_claim_cue(sentence: str) -> bool:
    norms = {w.norm for w in tokenize(sentence)}
    return bool(norms & HARD_CUES) or bool(norms & SAID_VERBS and norms & SOURCE_WORDS)


def _is_commentary_around_quotes(sentence: str, found: list[Located]) -> bool:
    if any(f.kind == "region" for f in found):
        return True  # marked claims are explicit; trust them
    covered = sum(len(f.segment.segment_text.split()) for f in found)
    return covered / len(sentence.split()) < MAX_RUN_COVERAGE


def verify_sentence(sentence: str, offset: int) -> list[Located]:
    whole = Located(offset, offset + len(sentence), verify_segment(sentence), "sentence")
    if whole.segment.status == "verified":
        return [whole]
    long_sentence = len(sentence.split()) > SENTENCE_REFINE_MIN_WORDS
    # A short sentence that resembles a verse (variant) is kept whole so that its alteration is reported;
    # one that resembles nothing may still contain a verbatim quote among commentary.
    if long_sentence or whole.segment.status == "baseless":
        found = locate_quotes(sentence)
    else:
        # Resembles a verse: still cut away an attribution ("قال تعالى ...") so that it does not count
        # as an alteration of the quote, but do not trim anything unmarked.
        found = locate_quotes(sentence, runs=False)
    if found and _is_commentary_around_quotes(sentence, found):
        return [Located(offset + f.start, offset + f.end, f.segment, f.kind) for f in found]
    return [whole]


def verify_local(text: str) -> list[Located]:
    return [item for a, b in sentence_spans(text) for item in verify_sentence(text[a:b], a)]


def _response(text: str, located: list[Located], extraction: ExtractionInfo | None = None) -> VerifyResponse:
    return VerifyResponse(
        original_text=text,
        word_count=len(text.split()),
        segments=[item.segment for item in located],
        extraction=extraction,
    )


def verify_text(text: str) -> VerifyResponse:
    return _response(text, verify_local(text))


def _find_claim(text: str, words, claim: str) -> tuple[int, int] | None:
    """Character span of `claim` in `text` if its words occur there consecutively (spelling-insensitive)."""
    target = normalize(claim).split()
    if len(target) < REGION_MIN_WORDS:
        return None
    norms = [w.norm for w in words]
    for i in range(len(norms) - len(target) + 1):
        if norms[i : i + len(target)] == target:
            return words[i].start, words[i + len(target) - 1].end
    return None


def merge_claims(text: str, local: list[Located], claims: list[str]) -> tuple[list[Located], ExtractionInfo]:
    words = tokenize(text)
    accepted: list[Located] = []
    rejected: list[str] = []
    for claim in claims:
        span = _find_claim(text, words, claim)
        if span is None:
            rejected.append(claim)
            continue
        start, end = span
        if any(l.segment.status == "verified" and l.start < end and start < l.end for l in local):
            continue  # already verified locally
        if any(a.start < end and start < a.end for a in accepted):
            continue  # duplicate or overlapping claim
        segment = verify_segment(text[start:end].strip(_TRIM))
        accepted.append(Located(start, end, segment))

    # A claim replaces the unverified local segment(s) it overlaps: they describe the same text.
    replaced = {
        id(l)
        for l in local
        if l.segment.status != "verified" and any(l.start < a.end and a.start < l.end for a in accepted)
    }
    merged = [l for l in local if id(l) not in replaced] + accepted
    # With the LLM having looked at the whole text, a sentence it found nothing in, and that resembles no verse
    # or hadith, is commentary. It stays in the response (never silently dropped) but is flagged as such.
    merged = [
        Located(l.start, l.end, l.segment.model_copy(update={"is_claim": False}), l.kind)
        if l.kind == "sentence" and l.segment.status == "baseless" and not _has_claim_cue(text[l.start : l.end])
        else l
        for l in merged
    ]
    info = ExtractionInfo(used=True, claims_found=len(claims), claims_accepted=len(accepted), rejected=rejected)
    return sorted(merged, key=lambda l: l.start), info


async def verify_text_llm(text: str) -> VerifyResponse:
    """Local pass plus the LLM extraction pass; falls back to the local result if the LLM step fails."""
    local = verify_local(text)
    try:
        claims = await extract_claims(text)
    except Exception as exc:  # no key, network, timeout, malformed output: the local result still stands
        return _response(text, local, ExtractionInfo(used=False, error=f"{type(exc).__name__}: {exc}"))
    merged, info = merge_claims(text, local, claims)
    return _response(text, merged, info)
