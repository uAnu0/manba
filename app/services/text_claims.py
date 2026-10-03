"""Check a paragraph or a whole sermon: find every quote and every religious claim in it and check each one.

Quotes are found locally (the quote finder and the verifier: no model). The remaining sentences go to the model once,
which only says which of them make a religious claim and copies the claim text; each copied text is checked to occur in
its sentence before it is used. Every claim is then run through the claim verifier, several at a time.
"""
import asyncio
import re
from collections import Counter

from app.schemas import ClaimLLMInfo, TextCheckResponse, TextClaimItem
from app.services.claim_card import verify_claim
from app.services.llm_query import find_claims
from app.services.pipeline import _redact, sentence_spans, verify_local
from app.services.quote_finder import tokenize
from app.services.similar import nearest_text

MAX_SENTENCES = 80
MAX_CLAIMS = 8  # claims checked per request (each is about four model calls)
PARALLEL = 5  # claims checked at the same time
MAX_PIECES = 60  # stretches compared by meaning per request (one cached embedding each)
MIN_CLAIM_WORDS = 3
FRAGMENT_WORDS = 5  # an unmarked verbatim run this short is common speech that happens to occur in a text, not a quotation
MIN_UNIT_WORDS = 4  # what is left of a sentence around a quote is checked as a claim only if it is at least this long


def _locate(sentence: str, claim: str) -> tuple[int, int] | None:
    """Character span of `claim` inside `sentence` if its words occur there consecutively (spelling-insensitive)."""
    words, target = tokenize(sentence), [w.norm for w in tokenize(claim)]
    if not target:
        return None
    norms = [w.norm for w in words]
    for i in range(len(norms) - len(target) + 1):
        if norms[i : i + len(target)] == target:
            return words[i].start, words[i + len(target) - 1].end
    return None


_CLAUSE = re.compile("[،؛:]")


def _pieces(text: str, spans: list[tuple[int, int]], covered: list[bool]) -> list[tuple[int, int]]:
    """The stretches compared with the corpus by meaning: every sentence no quote covers, and each of its clauses (a long
    sentence dilutes the match: "أحسنوا إلى ضعفائكم، وتعاهدوا مساكينكم؛ فإنما تنصرون وترزقون بضعفائكم")."""
    pieces: list[tuple[int, int]] = []
    for (a, b), done in zip(spans, covered):
        if done:
            continue
        pieces.append((a, b))
        start = a
        for m in list(_CLAUSE.finditer(text, a, b)) + [None]:
            end = m.start() if m else b
            if (start, end) != (a, b) and len(tokenize(text[start:end])) >= 3:
                pieces.append((start, end))
            if m:
                start = m.end()
    return pieces[:MAX_PIECES]


def _units(text: str, spans: list[tuple[int, int]], quote_spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The stretches handed to the claim finder: a sentence no quote touches whole, and from a sentence that holds a quote the
    parts around it ("واحذروا الغيبة وأكل لحوم الناس بالباطل؛ فإن" before «المسلم من سلم المسلمون من لسانه ويده»), so the
    statement beside a quote is checked too and the quoted words are not checked twice."""
    units: list[tuple[int, int]] = []
    for a, b in spans:
        cuts = sorted((max(a, s), min(b, e)) for s, e in quote_spans if s < b and e > a)
        if not cuts:
            units.append((a, b))
            continue
        pos = a
        for s, e in cuts + [(b, b)]:
            if s > pos:
                piece = text[pos:s]
                lead = len(piece) - len(piece.lstrip(" \t\r\n،؛:.!؟"))
                piece = piece.strip(" \t\r\n،؛:.!؟")
                if len(tokenize(piece)) >= MIN_UNIT_WORDS:
                    units.append((pos + lead, pos + lead + len(piece)))
            pos = max(pos, e)
    return units


_NEGATIONS = frozenset({"لا", "لم", "لن", "ليس", "ليست", "غير", "ما", "بدون", "no", "not", "never"})


def _core(word: str) -> str:
    """A word without a leading wa/fa clitic (ويأمر -> يأمر), for comparing a rewritten claim with its sentence."""
    return word[1:] if len(word) > 3 and word[0] in "وف" else word


def _accept_rewrite(sentence: str, claim: str, subject: str) -> tuple[str, tuple[int, int]] | None:
    """The model sometimes returns a claim that is a faithful trim of the sentence rather than an exact copy
    ("الإسلام يأمر بالصدقة" for "ويأمر بالصدقة"). It is accepted only if every word comes from the sentence (so nothing
    can be added), no negation of the sentence is dropped (so it cannot flip), and its words keep their order.
    Returns the claim text and its approximate span in the sentence, or None."""
    words = tokenize(sentence)
    cores = [_core(w.norm) for w in words]
    wanted = [_core(w.norm) for w in tokenize(claim)]
    if not wanted:
        return None
    positions, at = [], 0
    for w in wanted:
        try:
            at = cores.index(w, at)
        except ValueError:
            return None  # a word that is not in the sentence (or comes out of order)
        positions.append(at)
        at += 1
    if any(n in _NEGATIONS for n in cores) and not any(w in _NEGATIONS for w in wanted):
        return None
    return claim, (words[positions[0]].start, words[positions[-1]].end)


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


async def check_text(
    text: str, use_llm: bool = True, api_key: str | None = None, use_meaning: bool = True
) -> TextCheckResponse:
    llm = ClaimLLMInfo()

    # 1. Quotes, found without a model. A bracketed or attributed text that matches nothing is still shown (as not found).
    quotes = [
        item
        for item in verify_local(text)
        if (item.segment.status in ("verified", "semantic_variant") and item.segment.classification in ("quran", "hadith"))
        or item.kind == "region"
    ]
    def is_fragment(q) -> bool:  # an unmarked short verbatim run: a label on the text, it neither cuts claims nor replaces them
        return q.kind == "run" and q.segment.status == "verified" and len(tokenize(text[q.start : q.end])) <= FRAGMENT_WORDS

    quote_spans = [(q.start, q.end) for q in quotes if not is_fragment(q)]

    # 2. Sentences, and which of them the quotes already cover.
    spans = sentence_spans(text)
    truncated = len(spans) > MAX_SENTENCES
    spans = spans[:MAX_SENTENCES]
    sentences = [text[a:b] for a, b in spans]
    covered = [sum(_overlap(span, q) for q in quote_spans) >= 0.5 * (span[1] - span[0]) for span in spans]

    # 3. The claims in what the quotes leave of each sentence (one model call for the whole text).
    units = _units(text, spans, quote_spans)
    unit_texts = [text[a:b] for a, b in units]
    claims: list[tuple[int, int, str]] = []  # (start, end, text)
    if use_llm:
        try:
            for k, claim_text, subject in await find_claims(unit_texts, [False] * len(units), api_key=api_key):
                a, _ = units[k]
                span = _locate(unit_texts[k], claim_text)
                claim = claim_text
                if span is None:
                    accepted = _accept_rewrite(unit_texts[k], claim_text, subject)
                    if accepted:
                        claim, span = accepted
                start, end = (a + span[0], a + span[1]) if span else units[k]  # no usable copy: the whole stretch
                if span is None:
                    claim = text[start:end].strip()
                elif claim == claim_text and _locate(unit_texts[k], claim_text) is not None:
                    claim = text[start:end].strip()
                # A piece that does not name its subject ("ويأمر بالصدقة") gets it from the same sentence, when the
                # words the model gave really occur there before the piece.
                subject_span = _locate(unit_texts[k], subject) if subject else None
                if span and subject_span and subject_span[1] <= span[0] and not claim.startswith(subject):
                    claim = f"{unit_texts[k][subject_span[0] : subject_span[1]]} {claim}"
                if len(tokenize(claim)) < MIN_CLAIM_WORDS or any(_overlap((start, end), q) > 0.5 * (end - start) for q in quote_spans):
                    continue
                if all(c[2] != claim for c in claims):
                    claims.append((start, end, claim))
            llm.used = True
        except Exception as exc:
            llm.error = _redact(f"{type(exc).__name__}: {exc}")
    skipped = max(0, len(claims) - MAX_CLAIMS)
    claims = sorted(claims)[:MAX_CLAIMS]

    # 4. Check every claim, several at a time.
    sem = asyncio.Semaphore(PARALLEL)

    async def check(claim: str):
        async with sem:
            return await verify_claim(claim, True, api_key, use_meaning, with_similar=False)

    async def nearest(sentence: str):
        async with sem:
            return await nearest_text(sentence, api_key)

    # Sentences no quote covers are also compared with the corpus by meaning (one cached embedding each, no chat model).
    pieces = _pieces(text, spans, covered) if use_meaning else []
    results, nears = await asyncio.gather(
        asyncio.gather(*(check(c[2]) for c in claims), return_exceptions=True),
        asyncio.gather(*(nearest(text[a:b]) for a, b in pieces)),
    )

    items = [
        TextClaimItem(
            kind="quote", text=text[q.start : q.end].strip(), start=q.start, end=q.end, quote=q.segment,
            fragment=is_fragment(q),
        )
        for q in quotes
    ]
    for (start, end, claim), result in zip(claims, results):
        if isinstance(result, Exception):
            llm.error = (llm.error + "; " if llm.error else "") + _redact(f"{type(result).__name__}: {result}")
            continue
        items.append(TextClaimItem(kind="claim", text=claim, start=start, end=end, result=result))
    taken: list[tuple[int, int]] = []  # a part of the text already pointed out (the best match per stretch wins)
    ranked = sorted(((p, s) for p, s in zip(pieces, nears) if s is not None), key=lambda ps: (-ps[1].shared_share, -ps[1].similarity))
    for (a, b), similar in ranked:
        if any(_overlap((a, b), t) > 0 for t in taken):
            continue
        src = (similar.evidence.source.book, similar.evidence.source.number)
        if any(
            i.kind == "quote" and i.quote.source and (i.quote.source.book, i.quote.source.number) == src and _overlap((i.start, i.end), (a, b)) > 0
            for i in items
        ):
            continue  # that very text is already shown as a verified quote here
        taken.append((a, b))
        owner = next((i for i in items if i.kind == "claim" and _overlap((i.start, i.end), (a, b)) > 0), None)
        if owner is not None:
            owner.result.similar = similar
        else:
            items.append(TextClaimItem(kind="similar", text=text[a:b].strip(), start=a, end=b, similar=similar))
    items.sort(key=lambda i: i.start)

    summary = Counter(
        ("matched_phrase" if i.fragment else i.quote.status) if i.kind == "quote" else "similar_text" if i.kind == "similar" else i.result.outcome
        for i in items
    )
    busy = [(i.start, i.end) for i in items]
    commentary = sum(1 for span in spans if not any(_overlap(span, b) > 0 for b in busy))
    return TextCheckResponse(
        original_text=text,
        word_count=len(text.split()),
        items=items,
        sentences=len(spans),
        commentary_sentences=commentary,
        skipped_claims=skipped,
        truncated=truncated,
        summary=dict(summary),
        llm=llm,
    )
