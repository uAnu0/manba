"""Claim verification: route the claim, gather evidence for it and against it, and report where the evidence stands.

Never a verdict of "true" or "false". The card says what the sources we searched contain: direct evidence for the
claim, against it, both, or none, and how strong each source is (levels and gradings). A model routes the claim and
grades each retrieved text (supports / contradicts / related / unrelated); it writes no evidence. Personal questions and
sensitive topics are sent to a scholar.
"""
import asyncio

from app.schemas import ClaimLLMInfo, ClaimResponse, EvidenceItem
from app.services.evidence import excerpt, index, search_text, stem, terms
from app.services.evidence_card import JUDGE_POOL, NOTICE_AR, NOTICE_EN, extend, gather, referral
from app.services.llm_query import classify_claim, judge_claim
from app.services.pipeline import _redact, verify_text, verify_text_llm
from app.services.strength import STRONG

MAX_SIDE = 6  # texts shown per side (supporting, contradicting)
MAX_RELATED = 3
EVIDENCE_ONLY_LIMIT = 5
LONG_QUOTE_WORDS = 12  # longer text goes through LLM extraction to find the quotes in it

SUMMARIES = {
    "quote_checked": (
        "This is a quoted text. Here is what the sources say about it.",
        "هذا نص منقول؛ وهذا ما تقوله المصادر عنه.",
    ),
    "supported": (
        "The sources we searched contain direct evidence that supports this claim, and none against it.",
        "في المصادر التي بحثنا فيها أدلة مباشرة تؤيد هذا الادعاء، ولم نجد ما يعارضه.",
    ),
    "supported_weakly": (
        "The evidence we found for this claim comes only from hadith that are weak or have no grading here: treat it with caution.",
        "الأدلة التي وجدناها لهذا الادعاء من أحاديث ضعيفة أو غير مُدرجة الحكم عندنا؛ فليُتعامل معها بحذر.",
    ),
    "contradicted": (
        "The sources we searched contain direct evidence that contradicts this claim, and none for it.",
        "في المصادر التي بحثنا فيها أدلة مباشرة تخالف هذا الادعاء، ولم نجد ما يؤيده.",
    ),
    "mixed": (
        "There is evidence on both sides. A scholar is needed to weigh it.",
        "توجد أدلة من الجانبين؛ ويحتاج الأمر إلى عالم يوازن بينها.",
    ),
    "no_clear_evidence": (
        "We found no clear evidence about this claim in the sources we searched. That does not mean the claim is false.",
        "لم نجد دليلًا واضحًا في هذا الادعاء في المصادر التي بحثنا فيها؛ وهذا لا يعني أنه باطل.",
    ),
    "refer_to_scholar": (
        "This is a personal question or case. Please ask a qualified scholar.",
        "هذه مسألة تخص حالة شخصية؛ فنرجو سؤال عالم مؤهل.",
    ),
    "out_of_scope": (
        "This does not look like a religious claim, so nothing was searched.",
        "لا يبدو هذا ادعاءً دينيًا، لذلك لم يُبحث عنه.",
    ),
    "evidence_only": (
        "No model was available to judge the evidence. These are texts related to the claim, with no verdict.",
        "لم يتوفر نموذج لتقييم الأدلة. هذه نصوص ذات صلة بالادعاء دون حكم.",
    ),
}


WEIGHT = {"quran": 3.0, "sahihayn": 3.0, "sahih": 2.0, "hasan": 1.5, "disputed": 1.0, "daif": 0.5, "ungraded": 0.5}
MINORITY_SHARE = 0.25  # a side holding less than this share of the other side's weight does not make the claim "mixed"


def weight(items: list[EvidenceItem]) -> float:
    return sum(WEIGHT.get(i.source.strength or "", 1.0) for i in items)


def outcome_of(supporting: list[EvidenceItem], contradicting: list[EvidenceItem]) -> str:
    """Weigh the two sides by source strength. One stray text judged to point the other way (the judge is a model and
    sometimes misreads a verse) does not turn a clear case into "mixed"; it is still shown, with a note."""
    def strong(items: list[EvidenceItem]) -> bool:
        return any(i.source.strength in STRONG for i in items)

    s, c = weight(supporting), weight(contradicting)
    if s and c and min(s, c) / max(s, c) >= MINORITY_SHARE:
        return "mixed"
    if s and s >= c:
        return "supported" if strong(supporting) else "supported_weakly"
    if c and strong(contradicting):
        return "contradicted"
    return "no_clear_evidence"


RARE_STEM_IDF = 5.0  # fallback anchors: the claim's own rare words (about 1 text in 300)


def key_stems(claim: str, key_terms: list[str]) -> set[str]:
    """Word stems naming the claim's subject: the router's key terms, or the claim's own rare words if it gave none."""
    stems = {w for t in key_terms for w in terms(t)}
    if stems:
        return stems
    idf = index().idf
    return {w for w in terms(claim) if idf.get(w, float("inf")) >= RARE_STEM_IDF}


def unseen_stems(anchors: set[str]) -> set[str]:
    """Subject words that appear nowhere in the corpus (e.g. a modern food): a text cannot settle a claim about them."""
    idf = index().idf
    return {w for w in anchors if w not in idf}


def mentions(entry, anchors: set[str], required: frozenset[str] | set[str] = frozenset()) -> bool:
    """Does the text itself contain one of the claim's subject words (and every required one)? With no anchors there is nothing to check."""
    words = set(terms(search_text(entry)))
    return (not anchors or bool(anchors & words)) and required <= words


def _response(claim: str, claim_type: str, outcome: str, llm: ClaimLLMInfo, **fields) -> ClaimResponse:
    summary_en, summary_ar = SUMMARIES[outcome]
    return ClaimResponse(
        claim=claim,
        claim_type=claim_type,
        outcome=outcome,
        summary_en=summary_en,
        summary_ar=summary_ar,
        notice_ar=NOTICE_AR,
        notice_en=NOTICE_EN,
        llm=llm,
        **fields,
    )


def _order(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Quran first, then Sahih al-Bukhari / Muslim, then the rest; the search ranking decides within a level."""
    return sorted(items, key=lambda i: (i.source.level or 9, -i.score))


async def verify_claim(
    claim: str, use_llm: bool = True, api_key: str | None = None, use_meaning: bool = True
) -> ClaimResponse:
    llm = ClaimLLMInfo()

    # 1. The cheap local pass: if the text is itself a verse or hadith in the corpus it is a quote, whatever else it is.
    local = verify_text(claim)
    quote_hit = any(s.status == "verified" and s.classification in ("quran", "hadith") for s in local.segments)

    # 2. Route the claim. While the router answers, the evidence for the claim's own words is already being gathered
    # (it is the first query whatever the route, and a topic claim is the common case); it is dropped for the other routes.
    pool = {"quran": JUDGE_POOL, "hadith": JUDGE_POOL}
    base = asyncio.create_task(gather([claim], True, api_key, use_meaning, pool)) if use_llm and not quote_hit else None
    intent = None
    if use_llm:
        try:
            intent = await classify_claim(claim, api_key)
            llm.used = True
        except Exception as exc:
            llm.error = _redact(f"{type(exc).__name__}: {exc}")
    claim_type = intent["claim_type"] if intent else ("quote" if quote_hit else "unknown")
    if quote_hit and claim_type in ("topic", "unknown"):
        claim_type = "quote"
    key_terms = (intent or {}).get("key_terms_ar") or []
    restated = (intent or {}).get("claim_ar") or None
    opposite = (intent or {}).get("opposite_ar") or None
    routed = {"restated_claim": restated, "opposite_claim": opposite}

    if base is not None and claim_type not in ("topic", "unknown"):
        base.cancel()  # a quote, a personal question or an off-topic text needs no evidence search
    if claim_type == "quote":
        quote = local
        if llm.used and len(claim.split()) > LONG_QUOTE_WORDS:
            try:
                quote = await verify_text_llm(claim, api_key)
            except Exception:  # the local result stands
                pass
        return _response(claim, claim_type, "quote_checked", llm, quote_check=quote, **routed)
    if claim_type == "not_religious":
        return _response(claim, claim_type, "out_of_scope", llm, **routed)
    if claim_type == "personal":
        return _response(
            claim, claim_type, "refer_to_scholar", llm, refer_to_scholar=True,
            reason="A personal question or case needs a scholar who can hear the details.", **routed,
        )

    # 3. Topic claim (or unknown, without a model): gather evidence for the claim and for its opposite.
    # The model's restatement and "opposite" are only search aids and it sometimes turns a false claim into its
    # opposite, so the person's own words are always searched too (and always the first query).
    extra = [q for q in dict.fromkeys(q for q in (restated, opposite) if q) if q != claim]
    if base is not None:
        g = await base
        if extra:
            g = await extend(g, extra, api_key, use_meaning, pool)
    else:
        g = await gather([claim] + extra, llm.used, api_key, use_meaning, pool)
    llm.recited, llm.recited_found = g.info.suggested, g.info.found_in_corpus
    if g.info.error and not llm.error:
        llm.error = g.info.error
    flagged, why = referral(claim, 1)  # sensitive topics get a "ask a scholar" banner next to the evidence
    anchors = key_stems(claim, key_terms)
    required = unseen_stems(anchors)

    if llm.used:
        subject = claim  # stance is judged against the person's own words, never against the model's restatement
        try:
            results = await asyncio.gather(
                *(
                    judge_claim(subject, [excerpt(g.entries[i].text, c, g.query_words) for i, _, _ in g.pool[c]], api_key)
                    for c in pool
                )
            )
        except Exception as exc:
            llm.error = (llm.error + "; " if llm.error else "") + "judge: " + _redact(f"{type(exc).__name__}: {exc}")
            results = None
        if results is not None:
            if not any(r[0] for r in results):
                return _response(claim, claim_type, "out_of_scope", llm, **routed)
            sides: dict[str, list[EvidenceItem]] = {"supports": [], "contradicts": [], "related": []}
            for c, (_, stances, says) in zip(pool, results):
                for k, (i, score, sources) in enumerate(g.pool[c]):
                    stance = stances.get(k)
                    if stance in ("supports", "contradicts") and not mentions(g.entries[i], anchors, required):
                        stance = "related"  # a text that never names the claim's subject cannot settle the claim
                    if stance in sides:
                        item = g.item(c, i, score, sources)
                        item.stance = stance
                        item.says = says.get(k) or None
                        sides[stance].append(item)
            supporting = _order(sides["supports"])[:MAX_SIDE]
            contradicting = _order(sides["contradicts"])[:MAX_SIDE]
            related = _order(sides["related"])[:MAX_RELATED]
            outcome = outcome_of(supporting, contradicting)
            refer = flagged or outcome in ("mixed", "no_clear_evidence")
            reason = why if flagged else ("Ask a scholar to weigh the evidence." if outcome == "mixed" else None)
            other = contradicting if outcome in ("supported", "supported_weakly") else supporting if outcome == "contradicted" else []
            if other:
                note = f"{len(other)} text(s) below were judged to point the other way; please read them."
                reason = f"{reason} {note}" if reason else note
            return _response(
                claim, claim_type, outcome, llm, supporting=supporting, contradicting=contradicting, related=related,
                refer_to_scholar=refer, reason=reason, **routed,
            )

    # No model (or the judge failed): the texts nearest to the claim, with no stance and no verdict.
    items = [
        g.item(c, i, score, sources) for c in pool for i, score, sources in g.pool[c][:EVIDENCE_ONLY_LIMIT]
    ]
    return _response(
        claim, claim_type if claim_type != "unknown" else "unknown", "evidence_only", llm,
        related=_order(items), refer_to_scholar=True,
        reason=why or "No verdict was reached: ask a scholar.", **routed,
    )
