"""Source-backed review receipts. Unresolved or incomplete reviews cannot earn one.

V2 uses a 128-bit text digest and 128-bit MAC, a dedicated secret, and exact UTF-8
text. Legacy 32-bit receipts are deliberately not accepted by this verifier.
"""
import base64
import datetime as dt
import hashlib
import hmac
import os
import re
from zoneinfo import ZoneInfo

from app.schemas import BadgeInfo, BadgeVerifyResponse, TextCheckResponse

EPOCH = dt.date(2026, 1, 1)
NOT_IN_TR = "not found in the official translations searched"
RANK = {"bad": 0, "fix": 1, "khl": 2, "ref": 3, "neu": 4, "ok": 5}
FIQH_KINDS = {
    "school_differs": "bad", "consensus_claim_disputed": "bad", "agreement_differs": "bad",
    "stated_as_certain_disputed": "khl", "partly_disputed": "khl",
    "school_matches": "ok", "disagreement_acknowledged": "ok", "agreement_reported": "ok",
    "found_no_marker": "neu", "not_found": "neu",
}


def _key() -> bytes | None:
    secret = os.getenv("BADGE_SECRET", "").strip()
    if len(secret.encode()) < 32:
        return None
    return hashlib.sha256(b"manba-badge-v2|" + secret.encode()).digest()


def fingerprint(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()[:16]


def _segment_kind(sg) -> str:
    if sg is None:
        return "bad"
    s = sg.source
    if sg.translation is not None or NOT_IN_TR in (sg.differences or []):
        if sg.translation is None:
            return "bad"
        if sg.status != "verified":
            return "fix"
    quran = sg.classification == "quran" or (s is not None and s.book == "القرآن الكريم")
    if sg.status == "verified" and s is not None:
        if quran:
            return "ok"
        return {"sahihayn": "ok", "sahih": "ok", "hasan": "ok", "daif": "bad", "disputed": "khl"}.get(s.strength or "", "fix")
    if sg.status == "semantic_variant" and s is not None:
        return "fix"
    return "bad"


def kind_of(item) -> str:
    if item.kind == "quote":
        return _segment_kind(item.quote)
    if item.kind == "similar":
        return "fix"
    r = item.result
    if r is None:
        return "neu"
    qc = r.quote_check
    if r.outcome == "quote_checked" and qc is not None and qc.segments:
        kinds = [_segment_kind(sg) for sg in qc.segments if sg.is_claim is not False]
        if kinds:
            return min(kinds, key=RANK.get)
    if r.fiqh is not None and r.fiqh.status in FIQH_KINDS:
        return FIQH_KINDS[r.fiqh.status]
    # Evidence stances come from a model, so they cannot certify a claim.
    return {"supported_in_part": "fix", "supported_weakly": "fix", "contradicted": "bad",
            "mixed": "khl", "refer_to_scholar": "ref"}.get(r.outcome, "neu")


def counted(response: TextCheckResponse) -> list:
    return [i for i in response.items if not i.fragment and not
            (i.kind == "claim" and i.result is not None and i.result.outcome == "out_of_scope")]


def assess(response: TextCheckResponse, text: str, today: dt.date | None = None) -> TextCheckResponse:
    response.badge = None
    response.badge_unavailable = None
    items = counted(response)
    for item in response.items:
        item.verdict_kind = kind_of(item)
        item.needs_action = item.verdict_kind != "ok"
        r = item.result
        if r is not None and (r.refer_to_scholar or r.llm.error or
                              (r.fiqh is not None and (r.fiqh.error or r.fiqh.matched_by != "model" or
                               (r.fiqh.attribution is not None and r.fiqh.attribution.status == "not_reported")))):
            item.needs_action = True
            if item.verdict_kind == "ok":
                item.verdict_kind = "neu"
    response.blocking = sum(i.needs_action for i in items)
    response.review_complete = bool(response.llm and response.llm.used and not response.llm.error
                                    and not response.truncated and not response.skipped_claims
                                    and not any(i.result is not None and
                                                (i.result.llm.error or (i.result.fiqh is not None and i.result.fiqh.error))
                                                for i in response.items))
    if not response.review_complete:
        response.badge_unavailable = "incomplete_review"
    elif response.blocking or not items:
        response.badge_unavailable = "unresolved_findings" if items else "nothing_checked"
    else:
        key = _key()
        if key is None:
            response.badge_unavailable = "signing_unavailable"
        else:
            day = today or dt.datetime.now(ZoneInfo("Asia/Riyadh")).date()
            days = (day - EPOCH).days
            if not 0 <= days <= 0x7FFF:
                response.badge_unavailable = "signing_unavailable"
                return response
            payload = (days | 0x8000).to_bytes(2, "big") + fingerprint(text)
            mac = hmac.new(key, b"v2" + payload, hashlib.sha256).digest()[:16]
            response.badge = BadgeInfo(code=_encode(payload + mac), date=day.isoformat(), mode="full", items=len(items))
    return response


def _encode(raw: bytes) -> str:
    b = base64.b32encode(raw).decode().rstrip("=")
    return "MNB2-" + "-".join(b[k:k + 4] for k in range(0, len(b), 4))


def _decode(code: str) -> bytes | None:
    shown = code.strip().upper()
    if not re.fullmatch(r"MNB2-(?:[A-Z2-7]{4}-){13}[A-Z2-7]{3}", shown):
        return None
    b = shown[5:].replace("-", "")
    try:
        raw = base64.b32decode(b + "=" * ((-len(b)) % 8))
        return raw if _encode(raw) == shown else None
    except ValueError:
        return None


def verify(code: str, text: str | None = None) -> BadgeVerifyResponse:
    shown = code.strip().upper()
    if shown.startswith("MNB-"):
        return BadgeVerifyResponse(valid=False, code=shown, reason="legacy_serial")
    raw = _decode(code)
    if raw is None:
        return BadgeVerifyResponse(valid=False, code=shown, reason="malformed")
    key = _key()
    if key is None:
        return BadgeVerifyResponse(valid=False, code=shown, reason="signing_unavailable")
    payload, mac = raw[:18], raw[18:]
    if not hmac.compare_digest(hmac.new(key, b"v2" + payload, hashlib.sha256).digest()[:16], mac):
        return BadgeVerifyResponse(valid=False, code=shown, reason="not_issued")
    days = int.from_bytes(payload[:2], "big")
    out = BadgeVerifyResponse(valid=True, code=shown, date=(EPOCH + dt.timedelta(days=days & 0x7FFF)).isoformat(),
                              mode="full" if days & 0x8000 else "matching")
    if text is not None:
        out.text_matches = hmac.compare_digest(fingerprint(text), payload[2:18])
    return out


# Letters and digits that a picture of the serial confuses (S and 5, Z and 2, G and 6, I and L): all of them are valid in the serial's alphabet,
# so the only way to tell which was meant is to ask the signature.
CONFUSABLE = {"S": "5", "5": "S", "Z": "2", "2": "Z", "G": "6", "6": "G", "I": "L", "L": "I"}


def recover(code: str, max_swaps: int = 3) -> BadgeVerifyResponse | None:
    """A serial that was READ from a picture (OCR) may have a few of the confusable characters wrong. Returns the verified result of the serial that
    differs from the one given in at most `max_swaps` of those characters, or None. It only ever accepts a serial the signature accepts, so it
    cannot make a wrong serial valid; with no signing key it checks nothing and returns None."""
    import itertools

    shown = code.strip().upper()
    first = verify(shown)
    if first.valid or first.reason in ("legacy_serial", "signing_unavailable"):
        return first if first.valid else None
    body = shown[5:].replace("-", "") if shown.startswith("MNB2-") else ""
    if len(body) != 55:
        return None
    spots = [i for i, ch in enumerate(body) if ch in CONFUSABLE]
    for k in range(1, max_swaps + 1):
        for combo in itertools.combinations(spots, k):
            chars = list(body)
            for i in combo:
                chars[i] = CONFUSABLE[chars[i]]
            candidate = "MNB2-" + "-".join("".join(chars)[j:j + 4] for j in range(0, 55, 4))
            result = verify(candidate)
            if result.valid:
                return result
    return None
