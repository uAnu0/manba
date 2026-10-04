"""Hadith gradings from Dorar (الدرر السنية), the hadith encyclopedia named in the challenge's scientific pack.

The pack's rule for hadith: "no hadith is attributed without a source and an approved grading in the data". The local corpus
covers nine books and has no grading for about 4,800 of its hadith (Musnad Ahmad, al-Darimi; al-Bukhari and Muslim need
none). Dorar's public search API (https://dorar.net/article/389) returns, for a search, up to 15 narrations, each with the
narrator, the scholar who graded it (المحدث), the book and page, and that scholar's ruling (خلاصة حكم المحدث), across
about 300,000 hadith. The rulings are shown as Dorar gives them, each with its scholar; they are never merged into one
grade of our own.

Dorar sits behind Cloudflare, which refuses most data-centre addresses, so the result cards call the API from the
reader's browser (JSONP, as the API documents) and fall back to this server endpoint. From a server that Dorar refuses,
this module returns `available: false` with the reason, and nothing else changes.
"""
import html
import re
import time
from collections import Counter, OrderedDict

import httpx

from app.schemas import DorarItem, DorarResult

API = "https://dorar.net/dorar_api.json"
TIMEOUT = 8.0
MAX_QUERY_WORDS = 10
TTL = 24 * 3600
_cache: OrderedDict[str, tuple[float, DorarResult]] = OrderedDict()

LABELS = {"الراوي": "narrator", "المحدث": "scholar", "المصدر": "source", "الصفحة أو الرقم": "page", "خلاصة حكم المحدث": "grade"}
_TAG = re.compile(r"<[^>]+>")
_DIAC = re.compile("[ً-ٰٟـ]")
_INFO_OPEN = re.compile(r'<div[^>]*class="hadith-info"[^>]*>')
_HADITH_OPEN = re.compile(r'<div[^>]*class="hadith"[^>]*>')
_LABEL = re.compile(r"(الراوي|المحدث|المصدر|الصفحة أو الرقم|خلاصة حكم المحدث)\s*:")

# The ruling's words, from the strongest to the weakest category. Order matters: "لا يصح" before "صحيح".
CATEGORIES = [
    ("fabricated", ("موضوع", "باطل", "لا أصل له", "لا اصل له", "مكذوب", "كذب")),
    ("daif", ("ضعيف", "ضعفه", "لا يعرف", "لين", "منكر", "لا يصح", "لا يثبت", "شاذ", "معلول", "مرسل", "منقطع", "واه", "فيه ضعف", "متروك", "مجهول")),
    ("hasan", ("حسن",)),
    ("sahih", ("صحيح", "ثابت", "متفق عليه", "على شرط", "إسناده جيد", "اسناده جيد", "رجاله ثقات")),
]


def _text(fragment: str) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", fragment)).split())


def category_of(grade: str) -> str:
    g = _DIAC.sub("", grade)
    for name, words in CATEGORIES:
        if any(w in g for w in words):
            return name
    return "other"


def parse(result_html: str) -> list[DorarItem]:
    """The narrations in Dorar's HTML result: text, narrator, scholar, book, page, ruling."""
    items = []
    parts = _INFO_OPEN.split(result_html)
    pairs = []
    for k in range(1, len(parts)):
        # the narration is the last "hadith" block before this "hadith-info"; the info runs to the next narration
        before = _HADITH_OPEN.split(parts[k - 1])
        info = _HADITH_OPEN.split(parts[k])[0]
        g = info.find("خلاصة حكم المحدث")
        cut = info.find("</div>", g) if g >= 0 else -1
        pairs.append((before[-1] if len(before) > 1 else "", info[:cut] if cut >= 0 else info))
    for body, info in pairs:
        text = re.sub(r"^\s*\d+\s*-\s*", "", _text(body))
        flat = _text(info)
        fields: dict[str, str] = {}
        marks = list(_LABEL.finditer(flat))
        for k, m in enumerate(marks):
            end = marks[k + 1].start() if k + 1 < len(marks) else len(flat)
            fields[LABELS[m.group(1)]] = flat[m.end() : end].strip(" |-")
        grade = fields.get("grade", "")
        items.append(DorarItem(text=text, category=category_of(grade), **{k: fields.get(k, "") for k in ("narrator", "scholar", "source", "page", "grade")}))
    return items


def summary_of(items: list[DorarItem]) -> dict[str, int]:
    return dict(Counter(i.category for i in items))


_ATTRIBUTION = re.compile(r"ﷺ|صلى الله عليه وسلم|قال رسول الله|قال النبي")
_NOT_LETTER = re.compile(r"[^\u0621-\u064A\s]")
_LEADING = {"و", "ف", "قال", "وقال", "فقال", "يقول", "ويقول", "رسول", "الله", "النبي", "صلى", "عليه", "وسلم", "رواه", "حديث", "في", "الحديث"}


def query_of(text: str) -> str:
    """The quoted words only (no attribution, punctuation or stray clitics), at most MAX_QUERY_WORDS of them."""
    words = _NOT_LETTER.sub(" ", _ATTRIBUTION.sub(" ", _DIAC.sub("", text))).split()
    k = 0
    while k < len(words) and words[k] in _LEADING:
        k += 1
    return " ".join(words[k : k + MAX_QUERY_WORDS])


async def search(text: str) -> DorarResult:
    query = query_of(text)
    if not query:
        return DorarResult(query=query, available=False, error="empty query")
    hit = _cache.get(query)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": "Manba/1.0 (+Islamic content review tool)"}) as client:
            response = await client.get(API, params={"skey": query})
        if response.status_code != 200 or "json" not in response.headers.get("content-type", "") and not response.text.lstrip().startswith("{"):
            return DorarResult(query=query, available=False, error=f"Dorar answered HTTP {response.status_code} to this server (Cloudflare often refuses data-centre addresses); the page asks Dorar from the browser instead")
        data = response.json()
        items = parse((data.get("ahadith") or {}).get("result", ""))
    except Exception as exc:
        return DorarResult(query=query, available=False, error=f"{type(exc).__name__}: {str(exc)[:160]}")
    result = DorarResult(query=query, available=True, items=items, summary=summary_of(items))
    _cache[query] = (time.time(), result)
    if len(_cache) > 2000:
        _cache.popitem(last=False)
    return result
