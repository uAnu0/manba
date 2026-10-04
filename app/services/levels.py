"""Content levels of the challenge's scientific pack ("مستويات المحتوى وضبط الاستجابة"), attached to every result.

(أ) settled, original information: the Quran, authentic hadith, pillars of Islam and faith. Answered directly with the source.
(ب) explanation, definition and reasoning: shown from approved material with the reference; nothing disputed stated as certain.
(ج) disputed or highly sensitive questions: limited to what is approved, the disagreement stated, or referral.
(د) a fatwa or a personal case: no independent ruling; general information and referral to a qualified person.

The level says how a result must be handled; it is not a grade of the text. A level is never given to something that was
not found (that is an abstention, shown as such).
"""
from app.schemas import ClaimResponse, Segment

SETTLED_STRENGTHS = {"quran", "sahihayn", "sahih"}


def segment_level(segment: Segment) -> str | None:
    """A quoted text: the Quran and authentic hadith are (أ); hasan (ب); weak, disputed or ungraded hadith need care (ج)."""
    if segment.status == "baseless" or segment.source is None:
        return None
    strength = segment.source.strength or ""
    if strength in SETTLED_STRENGTHS:
        return "أ"
    if strength == "hasan":
        return "ب"
    return "ج"


def claim_level(result: ClaimResponse) -> str | None:
    if result.outcome == "out_of_scope":
        return None
    if result.claim_type == "personal" or result.outcome == "refer_to_scholar":
        return "د"
    if result.outcome == "quote_checked" and result.quote_check:
        levels = [segment_level(s) for s in result.quote_check.segments if s.is_claim]
        levels = [lv for lv in levels if lv]
        return max(levels, key="أبجد".index) if levels else None
    if result.fiqh is not None and result.fiqh.content_level == "ج":
        return "ج"
    if result.outcome in ("mixed",) or result.refer_to_scholar:
        return "ج"  # evidence on both sides, or a sensitive topic flagged for a scholar
    if result.outcome == "supported" and any((i.source.strength or "") in SETTLED_STRENGTHS for i in result.supporting):
        return "أ" if result.fiqh is None else "ب"
    if result.outcome in ("no_clear_evidence", "evidence_only") and result.fiqh is None:
        return None
    return "ب"
