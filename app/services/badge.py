"""The Manba badge: a short serial for a review in which nothing blocked publishing, signed by the server.

The serial holds the day of the review, whether the AI took part ("full") or only direct matching ran, and a fingerprint of the
exact text, all signed with a server key (HMAC-SHA256). Nothing is stored: anyone can check a serial at /api/badge/{code}, and
sending the text with it shows whether it is the very text that was reviewed (one changed letter gives another fingerprint).

Which findings block publishing is decided here with the same rules the reviewer's page uses (app.js: segVerdict, claimVerdict,
similarVerdict), so the page and the badge never disagree.
"""
import base64
import datetime as dt
import hashlib
import hmac
import os
import re

from app.config import settings
from app.schemas import BadgeInfo, BadgeVerifyResponse, TextCheckResponse

EPOCH = dt.date(2026, 1, 1)
NOT_IN_TR = "not found in the official translations searched"
BLOCKING_FIQH = {"school_differs", "consensus_claim_disputed", "agreement_differs"}
BLOCKING_OUTCOME = {"supported_in_part": "fix", "supported_weakly": "fix", "contradicted": "bad"}
RANK = {"bad": 0, "fix": 1, "khl": 2, "ref": 3, "neu": 4, "ok": 5}


def _key() -> bytes:
    secret = os.getenv("BADGE_SECRET", "").strip() or settings.api_access_token or os.getenv("OPENROUTER_API_KEY", "").strip() or "manba-local-dev"
    return hashlib.sha256(b"manba-badge|" + secret.encode()).digest()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def fingerprint(text: str) -> bytes:
    return hashlib.sha256(_norm(text).encode()).digest()[:4]


def _segment_kind(sg) -> str:
    if sg is None:
        return "bad"
    s = sg.source
    if getattr(sg, "translation", None) is not None or NOT_IN_TR in (sg.differences or []):
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
    qc = getattr(r, "quote_check", None)
    if r.outcome == "quote_checked" and qc is not None and qc.segments:
        kinds = [_segment_kind(sg) for sg in qc.segments if getattr(sg, "is_claim", None) is not False]
        if kinds:
            return min(kinds, key=RANK.get)
    if r.fiqh is not None and r.fiqh.status:
        return "bad" if r.fiqh.status in BLOCKING_FIQH else "khl"
    return BLOCKING_OUTCOME.get(r.outcome, "neu")


def counted(response: TextCheckResponse) -> list:
    return [
        i for i in response.items
        if not i.fragment and not (i.kind == "claim" and i.result is not None and i.result.outcome == "out_of_scope")
    ]


def _encode(raw: bytes) -> str:
    b = base64.b32encode(raw).decode().rstrip("=")
    return "MNB-" + "-".join(b[k : k + 4] for k in range(0, len(b), 4))


def _decode(code: str) -> bytes | None:
    c = re.sub(r"[^A-Z2-7]", "", (code or "").upper().replace("MNB", "", 1))
    if len(c) != 16:
        return None
    try:
        return base64.b32decode(c)
    except ValueError:
        return None


def assess(response: TextCheckResponse, text: str, today: dt.date | None = None) -> TextCheckResponse:
    """Set response.blocking and, when nothing blocks and something was checked, response.badge."""
    items = counted(response)
    response.blocking = sum(1 for i in items if kind_of(i) in ("bad", "fix"))
    if response.blocking or not items or response.truncated:
        return response
    day = today or dt.date.today()
    full = bool(response.llm and response.llm.used)
    days = min((day - EPOCH).days, 0x7FFF) | (0x8000 if full else 0)
    payload = days.to_bytes(2, "big") + fingerprint(text)
    mac = hmac.new(_key(), b"v1" + payload, hashlib.sha256).digest()[:4]
    response.badge = BadgeInfo(code=_encode(payload + mac), date=day.isoformat(), mode="full" if full else "matching", items=len(items))
    return response


def verify(code: str, text: str | None = None) -> BadgeVerifyResponse:
    raw = _decode(code)
    shown = code.strip().upper()
    if raw is None:
        return BadgeVerifyResponse(valid=False, code=shown, reason="malformed")
    payload, mac = raw[:6], raw[6:]
    if not hmac.compare_digest(hmac.new(_key(), b"v1" + payload, hashlib.sha256).digest()[:4], mac):
        return BadgeVerifyResponse(valid=False, code=_encode(raw), reason="not_issued")
    days = int.from_bytes(payload[:2], "big")
    out = BadgeVerifyResponse(
        valid=True, code=_encode(raw), date=(EPOCH + dt.timedelta(days=days & 0x7FFF)).isoformat(),
        mode="full" if days & 0x8000 else "matching",
    )
    if text is not None and text.strip():
        out.text_matches = hmac.compare_digest(fingerprint(text), payload[2:6])
    return out
