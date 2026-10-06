"""What kind of text was entered: a sermon, a social-media post, an article, a lesson, a question, or plain text.

The report speaks to the reviewer about that text ("هذه الخطبة غير جاهزة للإلقاء", "لا تنشر هذا المنشور قبل…"). The kind is read
from the text's own conventions (the khutbah's opening and address, a post's "انشرها تؤجر", a question's "هل يجوز"), so the
words that decided it are returned and shown; the reviewer can change it in the report. No model is used.
Vowel marks and the stretching mark are removed before matching, so a fully vowelled sermon reads like a plain one.
"""
import re

from app.schemas import TextCheckResponse

LABELS_AR = {"khutbah": "الخطبة", "post": "المنشور", "article": "المقال", "lesson": "الدرس", "question": "السؤال", "text": "النص"}

CUES = {
    "khutbah": [
        r"إن الحمد لله", r"الحمد لله نحمده", r"أما بعد", r"عباد الله", r"أيها المسلمون", r"أيها المؤمنون", r"أيها الإخوة",
        r"أيها الناس", r"اتقوا الله", r"الخطبة الثانية", r"أقول قولي هذا", r"معاشر المسلمين", r"خطبة",
        r"الحمد لله الذي", r"معاشر المؤمنين", r"يا عباد الله", r"أيها الأحبة", r"إخوة الإيمان", r"أوصيكم ونفسي", r"بارك الله لي ولكم",
        r"praise be to allah", r"dear brothers", r"brothers and sisters", r"o servants of allah", r"khutbah", r"fear allah",
    ],
    "post": [
        r"انشرها", r"انشر\b", r"شارك", r"تؤجر", r"لا تجعلها تقف عندك", r"أرسلها", r"صدقة جارية", r"#\S+", r"[\U0001F300-\U0001FAFF]",
        r"\bshare\b", r"\bforward\b", r"\brepost\b", r"\blike and\b",
    ],
    "question": [r"هل يجوز", r"ما حكم", r"ما الحكم", r"سؤال", r"أفتونا", r"\bis it (?:permissible|allowed|haram|halal)\b", r"what is the ruling"],
    "lesson": [r"الدرس", r"درسنا", r"في هذا الدرس", r"المحاضرة", r"الفائدة الأولى", r"\blesson\b", r"\blecture\b"],
    "article": [r"المقال", r"مقالة", r"خلاصة القول", r"الخاتمة", r"\barticle\b", r"\bin conclusion\b"],
}
_COMPILED = {k: [re.compile(p, re.IGNORECASE) for p in v] for k, v in CUES.items()}
_MARKS = re.compile("[\u064B-\u065F\u0670\u0640]")   # vowel marks, the dagger alef and the stretching mark


def _bare(text: str) -> str:
    return _MARKS.sub("", text)


def content_type(text: str) -> tuple[str, list[str]]:
    text = _bare(text)
    scores: dict[str, int] = {}
    seen: dict[str, list[str]] = {}
    head = text[:600]
    for kind, patterns in _COMPILED.items():
        for p in patterns:
            m = p.search(text)
            if m:
                # an opening formula counts double: a sermon opens with praise, a question opens by asking
                scores[kind] = scores.get(kind, 0) + (2 if m.start() < 120 or (kind == "khutbah" and p.search(head)) else 1)
                seen.setdefault(kind, []).append(m.group(0))
    if text.strip().endswith(("?", "؟")) and len(text.split()) < 80:
        scores["question"] = scores.get("question", 0) + 2
    if not scores and len(text.split()) > 220:
        return "article", []
    if not scores:
        return "text", []
    kind = max(scores, key=lambda k: (scores[k], k == "khutbah"))
    if scores[kind] < 2:
        return "text", seen.get(kind, [])[:3]
    return kind, seen.get(kind, [])[:3]


def label(response: TextCheckResponse, text: str) -> TextCheckResponse:
    kind, cues = content_type(text)
    response.content_type, response.content_type_ar, response.content_type_cues = kind, LABELS_AR[kind], cues
    return response
