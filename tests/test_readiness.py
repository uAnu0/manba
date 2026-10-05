"""Regression checks for receipts and misleading readiness outcomes (no paid API)."""
import asyncio
import datetime as dt
import json

import pytest

from app.schemas import ClaimLLMInfo, ClaimResponse, FiqhPassage, Segment, Source, TextCheckResponse, TextClaimItem
from app.services import badge, fiqh, foreign, text_claims, llm_query
from app.services.claim_card import outcome_of


def quote(strength="quran"):
    return TextClaimItem(kind="quote", text="نص", start=0, end=3,
                         quote=Segment(segment_text="نص", classification="quran" if strength == "quran" else "hadith",
                                       status="verified", confidence=1,
                                       source=Source(book="القرآن الكريم" if strength == "quran" else "سنن أبي داود",
                                                     chapter="", number="1:1", matched_text="نص", strength=strength)))


def response(items=None, **kw):
    return TextCheckResponse(original_text="نص", word_count=1, items=[quote()] if items is None else items,
                             sentences=1, commentary_sentences=0, llm=ClaimLLMInfo(used=True), **kw)


@pytest.fixture(autouse=True)
def dedicated_secret(monkeypatch):
    monkeypatch.setenv("BADGE_SECRET", "test-only-secret-that-is-at-least-32-bytes")


@pytest.mark.parametrize("changes", [{"skipped_claims": 1}, {"truncated": True}])
def test_incomplete_review_never_earns_receipt(changes):
    r = response(**changes)
    badge.assess(r, "نص")
    assert r.badge is None and not r.review_complete


@pytest.mark.parametrize("strength", ["daif", "disputed", "ungraded"])
def test_unresolved_hadith_blocks_receipt(strength):
    r = badge.assess(response([quote(strength)]), "نص")
    assert r.blocking == 1 and r.badge is None and r.items[0].needs_action


@pytest.mark.parametrize("outcome", ["supported", "mixed", "evidence_only", "no_clear_evidence", "refer_to_scholar"])
def test_model_or_unresolved_claims_cannot_certify(outcome):
    claim = ClaimResponse(claim="نص", claim_type="topic", outcome=outcome, summary_ar="", summary_en="",
                          notice_ar="", notice_en="")
    item = TextClaimItem(kind="claim", text="نص", start=0, end=3, result=claim)
    r = badge.assess(response([quote(), item]), "نص")
    assert r.blocking == 1 and r.badge is None


def test_exact_text_receipt_and_tampering():
    text = "نص  عربي\n"
    r = badge.assess(response(), text, dt.date(2026, 10, 5))
    code = r.badge.code
    assert code.startswith("MNB2-")
    assert badge.verify(code, text).text_matches is True
    for changed in [text.strip(), text.replace("  ", " "), text + "x", ""]:
        assert badge.verify(code, changed).text_matches is False
    wrong = code[:-1] + ("A" if code[-1] != "A" else "B")
    assert not badge.verify(wrong).valid
    assert not badge.verify("junk" + code).valid
    assert badge.verify("MNB-AEKR-KF22-6P67-JHUU").reason == "legacy_serial"


def test_no_key_fallback_or_partial_mode(monkeypatch):
    monkeypatch.delenv("BADGE_SECRET", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "shared-key")
    r = badge.assess(response(), "نص")
    assert r.badge is None and r.badge_unavailable == "signing_unavailable"
    r.llm.used = False
    badge.assess(r, "نص")
    assert not r.review_complete and r.badge is None


def passage(text, **kw):
    return FiqhPassage(entry="اختبار", section="", heading="", number=1, volume=1, page=1,
                       text=text, agreement="agreement", score=1, cite="اختبار", **kw)


def test_model_direction_alone_does_not_settle_fiqh():
    p = passage("اتفق الفقهاء على أن المهر واجب", direction="same", same_issue=True)
    assert fiqh._status("definite", [p], "المهر غير واجب") == "found_no_marker"
    p.ruling_sentence = p.text
    assert fiqh._status("definite", [p], "المهر غير واجب") == "agreement_differs"


def test_school_match_does_not_erase_false_consensus():
    p = passage("ذهب الحنفية إلى أن الوتر واجب. وذهب الجمهور إلى أنه سنة مؤكدة.", same_issue=True)
    p.agreement = "disagreement"
    r = fiqh._result("الوتر واجب عند الحنفية بالإجماع", "consensus", ["بالإجماع"], "consensus_claim_disputed", [p], "model")
    assert r.status == "consensus_claim_disputed"


def test_ruling_words_have_boundaries():
    assert fiqh.assertion_of("هذه واجبات منزلية للطلاب")[0] == "none"


def test_first_school_match_cannot_validate_all_schools():
    p = passage("ذهب الحنفية إلى أن الوتر واجب. وذهب الجمهور إلى أنه سنة مؤكدة.", same_issue=True)
    p.agreement = "disagreement"
    r = fiqh._result("الوتر واجب عند الحنفية والمالكية", "hedged", [], "disagreement_acknowledged", [p], "model")
    assert r.status == "found_no_marker" and r.attribution is None


def test_opposing_evidence_is_never_discarded():
    from app.schemas import EvidenceItem
    def evidence(strength):
        return EvidenceItem(classification="hadith", score=1, matched_terms=[], source=quote(strength).quote.source, full_text="نص")
    assert outcome_of([evidence("sahih")] * 10, [evidence("daif")]) == "mixed"


def test_claim_triage_gets_the_entire_sentence(monkeypatch):
    async def chat(messages, *args, **kw):
        assert "الوتر واجب بالإجماع" in messages[1]["content"]
        return '{"claims": []}'
    monkeypatch.setattr(llm_query, "chat_json", chat)
    llm_query.find_claims.cache_clear()
    asyncio.run(llm_query.find_claims(["مقدمة " * 100 + "الوتر واجب بالإجماع"], [False]))


def test_foreign_mixed_sentence_keeps_claim_beside_quote(monkeypatch):
    captured = []
    async def translate(sentences, key):
        captured.extend(sentences)
        return [(False, "")] * len(sentences)
    monkeypatch.setattr(foreign, "_translate", translate)
    text = 'Allah says: "Indeed, with hardship comes ease", and all scholars agree that jewellery zakat is obligatory.'
    asyncio.run(foreign.check_foreign(text, "en", True, use_meaning=False))
    assert any("all scholars agree" in s for s in captured)


def test_foreign_omitted_translation_is_a_failure(monkeypatch):
    async def chat(*args, **kw):
        return json.dumps({"sentences": [{"index": 0, "religious_claim": False, "arabic": ""}]})
    monkeypatch.setattr(foreign, "chat_json", chat)
    with pytest.raises(ValueError, match="incomplete"):
        asyncio.run(foreign._translate(["one sentence", "another sentence"], None))


def test_attributed_unquoted_text_is_checked_even_if_model_skips(monkeypatch):
    async def triage(*args, **kw):
        return []
    monkeypatch.setattr(text_claims, "find_claims", triage)
    r = asyncio.run(text_claims.check_text("قال رسول الله: اطلبوا العلم ولو في الصين.", use_meaning=False))
    assert any(i.kind == "quote" and i.quote.status == "baseless" for i in r.items)


def test_more_than_eight_claims_records_skips(monkeypatch):
    async def triage(*args, **kw):
        return []
    monkeypatch.setattr(text_claims, "find_claims", triage)
    text = ". ".join(f"أمر رقم {i} واجب" for i in range(10))
    r = asyncio.run(text_claims.check_text(text, use_meaning=False))
    assert r.skipped_claims == 2
    assert badge.assess(r, text).badge is None


def test_changed_taa_marbuta_is_not_verified():
    from app.services.verifier import verify_segment
    assert verify_segment("فبما رحمة من الله لنت لهم").status == "verified"
    assert verify_segment("فبما رحمه من الله لنت لهم").status == "semantic_variant"


def test_explicit_changed_vowels_are_not_verified():
    from app.services.verifier import verify_segment
    assert verify_segment("قُلْ هُوَ اللَّهُ أَحِدٌ").status == "semantic_variant"
    assert verify_segment("قُلْ هُوَ اللَّهُ أَحَدٌ").status == "verified"


def test_explicit_changed_hamza_is_not_verified():
    from app.services.verifier import verify_segment
    assert verify_segment("أن مع العسر يسرا").status == "semantic_variant"
    assert verify_segment("إن مع العسر يسرا").status == "verified"
