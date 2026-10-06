"""Text written in another language: quotes are checked against official translations, claims through Arabic.

A verse quoted in English is not compared with an English text someone typed from memory: it is searched in the approved
translations published by QuranEnc (data/translations/<key>.json.gz, as published, with version), and the verse found leads to
the Arabic text of the Mushaf. A hadith quoted in English is searched in the English editions of seven books
(data/translations/hadith_en.json.gz), keyed by the same book and number as the Arabic corpus, so its Arabic text, source and
gradings come from the corpus. A sentence that states a claim is translated into Arabic by the model (shown as a machine
translation, used only for searching) and checked like any Arabic claim, the fiqh check included.

Code decides every verdict here: the share of the quoted words found, in order, in the official wording.
"""
import asyncio
import gzip
import json
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from app.schemas import ClaimLLMInfo, OfficialTranslation, Segment, TextCheckResponse, TextClaimItem
from app.services.claim_card import verify_claim
from app.services.fiqh import _Bm25
from app.services.levels import segment_level
from app.services.llm_extractor import chat_json
from app.services.pipeline import _redact, verify_local
from app.services.verifier import _source, load_corpus

DIR = Path(__file__).resolve().parents[2] / "data" / "translations"
SAME = 0.85  # share of the quoted words found in order in the official wording: the same translation
CLOSE = 0.6  # below SAME and at least this: the verse is identified, but the wording differs
CLOSE_HADITH = 0.62  # hadith renderings vary more and the books are larger: a hadith must match more to be identified
MIN_QUOTE_WORDS = 4
MAX_CLAIMS = 12

_STOP = {
    "en": "the and of is to that in it for was he his with allah prophet said says not be are this you they",
    "fr": "le la les et des est que qui dans pour une un du au il elle dit ne pas allah prophète",
    "id": "yang dan di itu dengan tidak ini dari untuk dalam adalah ke kepada allah nabi",
    "tr": "ve bir bu için ile olan de da ne gibi çok allah peygamber dedi",
    "es": "el la los las y que de es en un una por con para dijo no allah profeta",
}
_STOP = {k: set(v.split()) for k, v in _STOP.items()}
_URDU = set("ٹڈڑںےۓھگچپژ")


def language_of(text: str) -> str:
    arabic = sum(1 for c in text if "؀" <= c <= "ۿ")
    latin = sum(1 for c in text if c.isalpha() and c.isascii() or "À" <= c <= "ɏ")
    if arabic >= latin:
        return "ur" if sum(1 for c in text if c in _URDU) >= 3 else "ar"
    words = re.findall(r"[^\W\d_]+", text.lower())
    counts = {k: sum(1 for w in words if w in s) for k, s in _STOP.items()}
    best = max(counts, key=counts.get)
    return best if counts[best] >= 2 else "other"


def _tokens(text: str) -> list[str]:
    text = re.sub(r"\[\d+\]|\(\d+\)", " ", text)
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[^\W\d_]+", text)


@lru_cache(maxsize=None)
def _translations(lang: str) -> tuple[dict, ...]:
    found = []
    for path in sorted(DIR.glob("*.json.gz")) if DIR.exists() else []:
        if path.name.startswith("hadith_"):
            continue
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        if data["meta"].get("language") == lang:
            found.append(data)
    return tuple(found)


class _Index:
    def __init__(self, docs: list[tuple[dict, str, str]]):
        self.docs = docs  # (meta, ref, text)
        self.toks = [_tokens(t) for _, _, t in docs]
        self.bm25 = _Bm25(self.toks, 0.2)

    def best(self, quote: str, limit: int = 25) -> tuple[int, float] | None:
        q = _tokens(quote)
        if len(q) < 3:
            return None
        scores, _ = self.bm25.scores(q)
        top = sorted(scores, key=lambda i: -scores[i])[:limit]
        best = None
        for i in top:
            share, _ = self.compare(q, i)
            if best is None or share > best[1]:
                best = (i, share)
        return best

    def weight(self, w: str) -> float:
        return self.bm25.idf.get(w, max(self.bm25.idf.values(), default=1.0))  # a word no text has weighs the most

    def compare(self, q: list[str], i: int) -> tuple[float, list[str]]:
        """(share of the quote's weight found in order in text i, the quote's words not found there). A word weighs its
        idf, so "adultery" in place of "interest" counts far more than "the" or "and"."""
        m = SequenceMatcher(None, q, self.toks[i], autojunk=False)
        hit = [False] * len(q)
        for blk in m.get_matching_blocks():
            for k in range(blk.a, blk.a + blk.size):
                hit[k] = True
        total = sum(self.weight(w) for w in q) or 1.0
        share = sum(self.weight(w) for w, h in zip(q, hit) if h) / total
        missing = [w for w, h in zip(q, hit) if not h and self.weight(w) > 2.0]
        return share, list(dict.fromkeys(missing))


@lru_cache(maxsize=None)
def quran_index(lang: str) -> _Index | None:
    docs = [(t["meta"], ref, text) for t in _translations(lang) for ref, text in t["verses"].items()]
    return _Index(docs) if docs else None


@lru_cache(maxsize=1)
def hadith_index() -> _Index | None:
    path = DIR / "hadith_en.json.gz"
    if not path.exists():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    meta = {"key": "hadith_en", "title": "English translations of the hadith books (fawazahmed0/hadith-api)", "language": "en",
            "version": None, "source": data["meta"]["source"]}
    return _Index([(meta, f"{i['book']}|{i['number']}", i["text"]) for i in data["items"]])


@lru_cache(maxsize=1)
def _arabic() -> tuple[dict, dict]:
    quran, hadith = {}, {}
    for e in load_corpus():
        if e.classification == "quran" and e.verses == 1:
            quran[e.number] = e
        elif e.classification == "hadith" and e.number:
            hadith.setdefault((e.book, e.number), e)
    return quran, hadith


# ---------- finding quotes in the text ----------
_QUOTED = re.compile(r"[\"“”«»]([^\"“”«»]{12,})[\"“”«»]")
_CUE = re.compile(
    r"(allah\s+(?:says|said|tells us|has said)|the\s+qur'?an\s+says|(?:the\s+)?prophet[^.:]{0,40}?\s+said|messenger of allah[^.:]{0,40}?\s+said|"
    r"allah\s+dit|le\s+prophète[^.:]{0,40}?\s+a\s+dit|allah\s+berfirman|nabi[^.:]{0,40}?\s+bersabda|allah\s+dice|el\s+profeta[^.:]{0,40}?\s+dijo|"
    r"allah\s+buyuruyor|peygamber[^.:]{0,40}?\s+buyurdu)\s*[:,]?\s*",
    re.IGNORECASE,
)
_REF = re.compile(r"(?:qur'?an|quran|surah|sura|sourate|surat|sure)?\s*[\[(]?\s*(\d{1,3})\s*[:.]\s*(\d{1,3})\s*[\])]?", re.IGNORECASE)


def _sentences(text: str) -> list[tuple[int, int]]:
    out, start = [], 0
    for m in re.finditer(r"(?<=[.!?؟।])\s+|\n+", text):
        if text[start:m.start()].strip():
            out.append((start, m.start()))
        start = m.end()
    if text[start:].strip():
        out.append((start, len(text)))
    return out


def find_quotes(text: str) -> list[tuple[int, int, str, str]]:
    """(start, end, quoted words, hint) for quoted passages and for the words after "Allah says", "the Prophet said"..."""
    found: list[tuple[int, int, str, str]] = []
    for m in _QUOTED.finditer(text):
        if len(_tokens(m.group(1))) >= MIN_QUOTE_WORDS:
            before = text[max(0, m.start() - 80):m.start()].lower()
            hint = "hadith" if re.search(r"prophet|messenger|narrat|hadith|prophète|nabi|profeta|peygamber", before) else (
                "quran" if re.search(r"allah|qur|surah|verse|ayah|sourate|ayat|ayet", before) else "")
            found.append((m.start(), m.end(), m.group(1), hint))
    for a, b in _sentences(text):
        if any(s < b and e > a for s, e, _, _ in found):
            continue
        m = _CUE.search(text, a, b)
        if m:
            words = text[m.end():b].strip(" .,;:")
            if len(_tokens(words)) >= MIN_QUOTE_WORDS:
                hint = "hadith" if re.search(r"prophet|messenger|prophète|nabi|profeta|peygamber", m.group(1), re.I) else "quran"
                found.append((m.end(), m.end() + len(text[m.end():b].rstrip(" .,;:")), words, hint))
    return sorted(found)


def match_quote(quote: str, lang: str, hint: str = "", ref: tuple[int, int] | None = None) -> Segment:
    quran_ar, hadith_ar = _arabic()
    candidates = []
    qi = quran_index(lang)
    if qi and hint != "hadith":
        hit = qi.best(quote)
        if hit:
            candidates.append(("quran", qi, *hit))
    hi = hadith_index() if lang == "en" else None
    if hi and hint != "quran":
        hit = hi.best(quote)
        if hit:
            candidates.append(("hadith", hi, *hit))
    if not candidates:
        return Segment(segment_text=quote, classification="unverified", status="baseless", confidence=0.0)
    kind, index, i, share = max(candidates, key=lambda c: (c[3], c[0] == hint))
    meta, key, official = index.docs[i]
    share, missing = index.compare(_tokens(quote), i)
    if share < (CLOSE if kind == "quran" else CLOSE_HADITH):
        return Segment(segment_text=quote, classification=kind if hint else "unverified", status="baseless", confidence=round(share, 2),
                       differences=["not found in the official translations searched"])
    entry = quran_ar.get(key) if kind == "quran" else hadith_ar.get(tuple(key.split("|", 1)))
    status = "verified" if share >= SAME and not missing else "semantic_variant"
    differences = []
    if missing:
        differences.append("words not in the official translation: " + ", ".join(missing[:12]))
    if kind == "quran" and ref and f"{ref[0]}:{ref[1]}" != key:
        differences.append(f"the reference given is {ref[0]}:{ref[1]}; these words are {key}")
        status = "semantic_variant"  # right words, wrong citation: it still needs correcting
    seg = Segment(
        segment_text=quote, classification=kind, status=status, confidence=round(share, 2),
        source=_source(entry) if entry else None, differences=differences,
        translation=OfficialTranslation(
            kind=kind, key=meta["key"], title=meta["title"], language=meta["language"], version=meta.get("version"),
            text=official, source_url=meta.get("source", ""), match=round(share, 2),
        ),
    )
    seg.content_level = segment_level(seg)
    return seg


# ---------- claims, through Arabic ----------
TRANSLATE_SCHEMA = {
    "name": "translated_sentences",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {"sentences": {"type": "array", "items": {"type": "object", "properties": {
            "index": {"type": "integer"}, "religious_claim": {"type": "boolean"}, "arabic": {"type": "string"}},
            "required": ["index", "religious_claim", "arabic"], "additionalProperties": False}}},
        "required": ["sentences"], "additionalProperties": False,
    },
}
TRANSLATE_PROMPT = (
    "You help an Islamic content review tool. For each numbered sentence (any language), say whether it states a religious "
    "claim or ruling that could be checked against the Quran, hadith or fiqh books (religious_claim), and translate it into "
    "plain Modern Standard Arabic, keeping the claim exactly as strong or weak as written: do not correct it, soften it, add "
    "evidence or add any word of your own. Use the usual Arabic fiqh terms (e.g. obligatory = واجب, forbidden = حرام, "
    "permissible = يجوز, dowry = المهر, consensus = الإجماع)."
)


async def _translate(sentences: list[str], api_key: str | None) -> list[tuple[bool, str]]:
    lines = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences))
    content = await chat_json([{"role": "system", "content": TRANSLATE_PROMPT}, {"role": "user", "content": lines}],
                              TRANSLATE_SCHEMA, api_key, temperature=0.0, max_tokens=3000)
    data = json.loads(content)
    out = [(False, "")] * len(sentences)
    seen = set()
    for row in data.get("sentences", []):
        k = row.get("index")
        if isinstance(k, int) and not isinstance(k, bool) and 0 <= k < len(sentences) and k not in seen:
            seen.add(k)
            out[k] = (bool(row.get("religious_claim")), (row.get("arabic") or "").strip())
            if row.get("religious_claim") and not out[k][1]:
                raise ValueError("missing claim translation")
    if len(seen) != len(sentences):
        raise ValueError("incomplete sentence translations")
    return out


async def check_foreign(text: str, lang: str, use_llm: bool = True, api_key: str | None = None, use_meaning: bool = True) -> TextCheckResponse:
    llm = ClaimLLMInfo()
    items: list[TextClaimItem] = []
    taken: list[tuple[int, int]] = []

    # Arabic quotes inside the text are checked as usual.
    for loc in verify_local(text):
        if loc.segment.status in ("verified", "semantic_variant") and loc.segment.classification in ("quran", "hadith"):
            items.append(TextClaimItem(kind="quote", text=text[loc.start:loc.end], start=loc.start, end=loc.end, quote=loc.segment,
                                       content_level=loc.segment.content_level))
            taken.append((loc.start, loc.end))

    for a, b, words, hint in find_quotes(text):
        if any(s < b and e > a for s, e in taken):
            continue
        near = _REF.search(text[b:b + 40]) or _REF.search(text[max(0, a - 40):a])
        ref = (int(near.group(1)), int(near.group(2))) if near and hint != "hadith" else None
        seg = match_quote(words, lang, hint, ref)
        items.append(TextClaimItem(kind="quote", text=text[a:b], start=a, end=b, quote=seg, content_level=seg.content_level))
        taken.append((a, b))

    # Check the text beside a quote as well as sentences containing no quotes.
    rest = []
    for a, b in _sentences(text):
        pos = a
        cuts = sorted((max(a, s), min(b, e)) for s, e in taken if s < b and e > a)
        for s, e in cuts + [(b, b)]:
            if s > pos and len(_tokens(text[pos:s])) >= 3:
                rest.append((pos, s))
            pos = max(pos, e)
    truncated = len(rest) > MAX_CLAIMS * 2
    skipped = 0
    rest = rest[:MAX_CLAIMS * 2]
    if use_llm and rest:
        try:
            translated = await _translate([text[a:b] for a, b in rest], api_key)
            llm.used = True
            todo = [(span, ar) for span, (is_claim, ar) in zip(rest, translated) if is_claim and ar]
            skipped = max(0, len(todo) - MAX_CLAIMS)
            todo = todo[:MAX_CLAIMS]
            sem = asyncio.Semaphore(4)

            async def one(ar: str):
                async with sem:
                    return await verify_claim(ar, True, api_key, use_meaning, with_similar=False)

            results = await asyncio.gather(*(one(ar) for _, ar in todo))
            for ((a, b), ar), result in zip(todo, results):
                if result.outcome == "out_of_scope":
                    continue
                items.append(TextClaimItem(kind="claim", text=text[a:b].strip(), start=a, end=b, result=result,
                                           content_level=result.content_level, translated_ar=ar))
        except Exception as exc:
            llm.error = _redact(f"{type(exc).__name__}: {exc}")
    items.sort(key=lambda i: i.start)

    summary: dict[str, int] = {}
    for i in items:
        key = f"quote_{i.quote.status}" if i.kind == "quote" else i.result.outcome
        summary[key] = summary.get(key, 0) + 1
    sentences = _sentences(text)
    return TextCheckResponse(
        original_text=text, word_count=len(text.split()), items=items, sentences=len(sentences),
        truncated=truncated, skipped_claims=skipped,
        commentary_sentences=max(0, len(sentences) - len(items)), summary=summary, llm=llm, language=lang,
        translations_used=[t["meta"]["title"] for t in _translations(lang)] + (["English hadith (fawazahmed0/hadith-api)"] if lang == "en" else []),
    )
