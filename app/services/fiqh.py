"""Fiqh check: does a sentence state a disputed question as settled, or claim a consensus that the sources do not report?

The scientific pack of the challenge sets the rule for general fiqh: answers come from an approved fiqh book "and must not
become a personal fatwa or an automatic independent preference (ترجيح)", and disputed questions are "never presented as
certain". So this module never says which opinion is right. It finds where the Kuwaiti Fiqh Encyclopedia discusses the
issue a sentence rules on, and reports, in the encyclopedia's own words:

- whether the encyclopedia states agreement (اتفق الفقهاء، أجمعوا، بلا خلاف) or disagreement (اختلف، ذهب ... وذهب، خلافًا لـ)
  on that issue (read by code from fixed wording, never by a model),
- the sentences that name the schools (الحنفية، المالكية، الشافعية، الحنابلة، الجمهور), quoted verbatim,
- volume and page of the printed edition.

It then compares that with how the sentence is worded: claimed consensus, a flat ruling, or a hedged one ("عند الجمهور",
"على الراجح", "اختلف العلماء").

A model, when available, only decides which retrieved passages discuss the same issue and copies the sentence of the
passage that states the ruling; the copy must occur in the passage or it is dropped. Without a model the best keyword
match is shown, labelled as a keyword match for the reader to confirm.
"""
import gzip
import json
import math
import re
from array import array
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.schemas import FiqhCheck, FiqhPassage, FiqhPosition
from app.services.cache import async_cache
from app.services.evidence import stem, terms
from app.services.llm_extractor import ExtractionError, chat_json
from app.services.verifier import normalize

ROOT = Path(__file__).resolve().parents[2]
FIQH_PATH = ROOT / "data" / "fiqh" / "kuwaiti.jsonl.gz"
SOURCE_AR = "الموسوعة الفقهية الكويتية"
SOURCE_EN = "Kuwaiti Fiqh Encyclopedia (Ministry of Awqaf, Kuwait)"

K1, B = 1.2, 0.75
MAX_DF_SHARE = 0.25
POOL = 12  # passages shown to the model
SHOW = 3  # passages shown to the reader
KEYWORD_MIN_SHARE = 0.6  # without a model, a passage must hold this share of the claim's (idf-weighted) words
MAX_POSITIONS = 6

NOTICE_AR = (
    "هذا بيانٌ لما تنقله الموسوعة الفقهية الكويتية في المسألة، بألفاظها ومواضعها، وليس فتوى ولا ترجيحًا بين الأقوال. "
    "لمعرفة الحكم في حالة بعينها يُرجع إلى عالم مؤهل."
)
NOTICE_EN = (
    "This reports what the Kuwaiti Fiqh Encyclopedia says on the question, in its own words and with volume and page. "
    "It is not a fatwa and does not prefer one opinion over another. For a particular case, ask a qualified scholar."
)


def _n(words: str) -> list[str]:
    return [normalize(w) for w in words.split("|")]


# ---------- wording of the person's sentence ----------
RULING_WORDS = _n(
    "سنة مؤكدة|من السنة|مسنون|يسن|تسن|حرام|محرم|محرمة|يحرم|تحرم|حرمة|لا يجوز|لا تجوز|يجوز|تجوز|جائز|جائزة|مباح|مباحة|واجب|واجبة|يجب|تجب|وجوب|فرض|فريضة|"
    "سنة مؤكدة|مستحب|مستحبة|يستحب|مكروه|مكروهة|يكره|باطل|باطلة|يبطل|تبطل|لا يصح|لا تصح|يصح|تصح|بدعة|نجس|نجسة|طاهر|"
    "ينقض|لا ينقض|يفسد|تفسد|شرط|ركن|لا تجب|لا يجب|حلال|يقع|لا يقع"
)
CONSENSUS_WORDS = _n(
    "بالإجماع|إجماعا|أجمع العلماء|أجمع الفقهاء|أجمعت الأمة|أجمع المسلمون|اتفق العلماء|اتفق الفقهاء|اتفقت المذاهب|باتفاق العلماء|"
    "باتفاق الفقهاء|بلا خلاف|لا خلاف|يتفقون|متفقون|يتفق المسلمون|يتفق العلماء|بلا نزاع|العلماء متفقون|جميع العلماء|كل العلماء|المذاهب الأربعة متفقة|عند جميع المذاهب|محل إجماع"
)
HEDGE_WORDS = _n(
    "على الراجح|الراجح|الأرجح|الأصح|في قول|على قول|عند الجمهور|جمهور العلماء|جمهور الفقهاء|الجمهور|اختلف|خلاف|بعض العلماء|"
    "بعض الفقهاء|عند الحنفية|عند المالكية|عند الشافعية|عند الحنابلة|في مذهب|قولين|أقوال|الأحوط|الأظهر|المشهور|على الصحيح"
)
# words of a ruling are not what the question is about: they are dropped from the search
_RULING_STEMS = {stem(w) for phrase in RULING_WORDS + CONSENSUS_WORDS + HEDGE_WORDS for w in phrase.split()} | {
    stem(normalize(w)) for w in "العلماء الفقهاء الإسلام شرعا حكم أهل العلم المسلمين".split()
}

# ---------- wording of the encyclopedia ----------
AGREE = _n(
    "اتفق الفقهاء|اتفق العلماء|اتفقوا|اتفق الأئمة|أجمع|الإجماع|إجماعا|بالإجماع|بلا خلاف|لا خلاف|لا نعلم خلافا|لا يعلم خلاف|باتفاق|"
    "محل اتفاق|اتفاقا|متفق عليه بين"
)
DISAGREE = _n(
    "اختلف الفقهاء|اختلف العلماء|اختلفوا|واختلف|على قولين|على أقوال|ثلاثة أقوال|ثلاثة آراء|خلافا ل|وخالف|في رواية|وفي رواية|"
    "وفي قول|والقول الثاني|وذهب|ذهب الجمهور|ذهب جمهور|جمهور الفقهاء|وقال بعضهم|ويرى بعض|في المسألة خلاف|وعن أحمد رواية|ومقابل الأصح"
)
SCHOOLS = [
    ("الحنفية", _n("الحنفية|أبو حنيفة|أبي حنيفة|الأحناف")),
    ("المالكية", _n("المالكية|مالك رحمه")),
    ("الشافعية", _n("الشافعية|الشافعي")),
    ("الحنابلة", _n("الحنابلة|أحمد|الحنبلية")),
    ("الجمهور", _n("الجمهور|جمهور الفقهاء")),
    ("الظاهرية", _n("الظاهرية|ابن حزم")),
]
_NEGATED_KHILAF = re.compile(r"(لا|بلا|لا نعلم|لا يعلم) خلاف")
_SENTENCE = re.compile(r"(?<=[.؛:])\s+")


def _has(text_n: str, phrases: list[str]) -> list[str]:
    """Phrases that start a word of the text, also after a clinging و / ف / ب / ل ("والحنابلة", "فذهب")."""
    padded = f" {text_n} "
    return list(dict.fromkeys(p for p in phrases if any(f" {c}{p}" in padded for c in ("", "و", "ف", "ب", "ل", "وب", "ول"))))


_YEAR = re.compile(r"\bسن[هة]\s+\d")


def assertion_of(sentence: str) -> tuple[str, list[str]]:
    """How the person's sentence states a ruling: consensus | hedged | definite | none (no ruling word at all)."""
    t = _YEAR.sub(" ", normalize(sentence))
    consensus = _has(t, CONSENSUS_WORDS)
    if consensus:
        return "consensus", consensus
    ruling = _has(t, RULING_WORDS)
    if not ruling and t.split() and t.split()[-1] in ("سنه", "سنة"):
        ruling = ["سنة"]  # "صلاة الضحى سنة": "سنة" closing the sentence is a ruling, "سنة 1400" or "سنة جيدة" is a year
    if not ruling:
        return "none", []
    hedge = _has(t, HEDGE_WORDS)
    if hedge:
        return "hedged", hedge
    return "definite", ruling


def agreement_of(text: str) -> str:
    """What the encyclopedia's own wording says: agreement | disagreement | both | none."""
    t = normalize(text)
    agree = bool(_has(t, AGREE))
    rest = _NEGATED_KHILAF.sub(" ", t)
    disagree = bool(_has(rest, DISAGREE)) or " خلاف " in f" {rest} "
    if agree and disagree:
        return "both"
    return "agreement" if agree else "disagreement" if disagree else "none"


def positions_of(text: str) -> list[FiqhPosition]:
    """The sentences of a passage that name a school, verbatim (with the school names they mention)."""
    out = []
    for sentence in _SENTENCE.split(text):
        sentence = sentence.strip()
        if len(sentence) < 15:
            continue
        t = normalize(sentence)
        names = [name for name, forms in SCHOOLS if _has(t, forms)]
        if names:
            out.append(FiqhPosition(schools=names, text=sentence[:600]))
        if len(out) >= MAX_POSITIONS:
            break
    return out


# ---------- the corpus ----------
@dataclass(frozen=True)
class Passage:
    id: int
    entry: str
    section: str
    heading: str
    number: int
    volume: int
    page: int
    text: str


@lru_cache(maxsize=1)
def passages() -> tuple[Passage, ...]:
    if not FIQH_PATH.exists():
        return ()
    with gzip.open(FIQH_PATH, "rt", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    return tuple(Passage(r["id"], r["e"], r["s"], r.get("h", ""), r["n"], r["v"], r["p"], r["t"]) for r in rows)


class _Bm25:
    def __init__(self, docs_terms: list[list[str]], max_df_share: float):
        docs: dict[str, array] = defaultdict(lambda: array("I"))
        tfs: dict[str, array] = defaultdict(lambda: array("H"))
        self.lengths = array("I")
        for i, words in enumerate(docs_terms):
            self.lengths.append(len(words))
            for w, tf in Counter(words).items():
                docs[w].append(i)
                tfs[w].append(min(tf, 65535))
        self.docs, self.tfs = dict(docs), dict(tfs)
        n = max(len(docs_terms), 1)
        self.avgdl = sum(self.lengths) / n or 1.0
        self.idf = {w: math.log(1 + (n - len(d) + 0.5) / (len(d) + 0.5)) for w, d in self.docs.items()}
        self.max_df = max_df_share * n

    def scores(self, words: list[str]) -> tuple[dict[int, float], dict[int, set[str]]]:
        scores: dict[int, float] = defaultdict(float)
        held: dict[int, set[str]] = defaultdict(set)
        for w in words:
            d = self.docs.get(w)
            if d is None or len(d) > self.max_df:
                continue
            idf = self.idf[w]
            for i, tf in zip(d, self.tfs[w]):
                norm = 1 - B + B * self.lengths[i] / self.avgdl
                scores[i] += idf * tf * (K1 + 1) / (tf + K1 * norm)
                held[i].add(w)
        return scores, held


class FiqhIndex:
    """Two BM25 indexes: the passage text (very common words skipped), and the entry name with the paragraph's own heading
    (no word skipped: "ذهب" is too common in the text, where it means "held", to be searched there, but in a heading such
    as "حلية الذهب للنساء" it names the subject)."""

    HEAD_WEIGHT = 2.0

    def __init__(self, items: tuple[Passage, ...]):
        self.items = items
        self.text = _Bm25([terms(p.text) for p in items], MAX_DF_SHARE)
        self.head = _Bm25([terms(f"{p.heading} {p.entry}") for p in items], 1.0)

    def search(self, words: list[str], limit: int) -> list[tuple[int, float, float]]:
        """(passage index, score, share of the query words the passage holds in its text or its heading)."""
        words = list(dict.fromkeys(words))
        if not words:
            return []
        text_scores, text_held = self.text.scores(words)
        head_scores, head_held = self.head.scores(words)
        total = len(words)
        out = []
        for i in set(text_scores) | set(head_scores):
            held = text_held.get(i, set()) | head_held.get(i, set())
            if not held:
                continue
            share = len(held) / total
            score = (text_scores.get(i, 0.0) + self.HEAD_WEIGHT * head_scores.get(i, 0.0)) * share
            out.append((i, score, share))
        out.sort(key=lambda x: -x[1])
        return out[:limit]


@lru_cache(maxsize=1)
def fiqh_index() -> FiqhIndex:
    return FiqhIndex(passages())


# The encyclopedia's headings use one word where people use another ("حلية الذهب للنساء" for "لبس المرأة الذهب").
SYNONYMS = {stem(normalize(a)): [stem(normalize(b)) for b in bs.split()] for a, bs in {
    "المرأة": "النساء", "النساء": "المرأة", "الرجل": "الرجال", "الرجال": "الرجل", "الصيام": "الصوم", "الصوم": "الصيام",
    "الخمر": "الأشربة المسكر", "الأغاني": "الغناء", "الموسيقى": "المعازف الغناء", "الحجاب": "العورة", "اللحية": "الشعر",
}.items()}


def query_terms(claim: str, extra: list[str] | None = None) -> list[str]:
    words = [w for w in terms(claim) if w not in _RULING_STEMS]
    for t in extra or []:
        words += [w for w in terms(t) if w not in _RULING_STEMS]
    return list(dict.fromkeys(words))


def search_terms(claim: str, extra: list[str] | None = None) -> list[str]:
    words = query_terms(claim, extra)
    return list(dict.fromkeys(words + [syn for w in words for syn in SYNONYMS.get(w, [])]))


def _passage_out(p: Passage, score: float, ruling: str | None = None, direction: str | None = None, same: bool | None = None) -> FiqhPassage:
    basis = ruling or p.text
    return FiqhPassage(
        entry=p.entry, section=p.section, heading=p.heading, number=p.number, volume=p.volume, page=p.page, text=p.text,
        agreement=agreement_of(basis) if ruling and agreement_of(basis) != "none" else agreement_of(p.text),
        positions=positions_of(p.text), ruling_sentence=ruling, direction=direction, same_issue=same, score=round(score, 3),
        cite=f"{SOURCE_AR}، ج{p.volume}، ص{p.page}، مادة «{p.entry}»" + (f"، فقرة {p.number}" if p.number else ""),
    )


# ---------- the model step: which passages discuss the same issue ----------
PICK_PROMPT = (
    "You help an Islamic content review tool. You get a sentence that states a fiqh ruling, and numbered passages from "
    "the Kuwaiti Fiqh Encyclopedia. Do NOT give a ruling, do NOT say which opinion is right, do NOT add knowledge of your "
    "own. For each passage decide only whether it discusses the SAME specific issue as the sentence (the same act, in the "
    "same case; a passage on a neighbouring issue is not the same). For a passage on the same issue, copy exactly, word "
    "for word from the passage (diacritics may be left out), the one sentence that states the ruling or the opinions on "
    "that issue; and say whether the ruling stated in the person's sentence matches what that passage reports: 'same' "
    "(it is the ruling the passage reports, or one of the opinions it reports), 'different' (the passage reports no "
    "opinion with that ruling), or 'unclear'. Also say if the sentence is about fiqh at all (in_scope)."
)
PICK_SCHEMA = {
    "name": "fiqh_passages",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "in_scope": {"type": "boolean"},
            "passages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer"},
                        "same_issue": {"type": "boolean"},
                        "ruling_sentence": {"type": "string"},
                        "direction": {"type": "string", "enum": ["same", "different", "unclear"]},
                    },
                    "required": ["number", "same_issue", "ruling_sentence", "direction"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["in_scope", "passages"],
        "additionalProperties": False,
    },
}


@async_cache()
async def pick_passages(claim: str, texts: tuple[str, ...], api_key: str | None = None) -> dict:
    from app.services.llm_query import judge_models

    lines = "\n\n".join(f"{k}. {t[:1200]}" for k, t in enumerate(texts))
    content = await chat_json(
        [{"role": "system", "content": PICK_PROMPT}, {"role": "user", "content": f"Sentence: {claim}\n\nPassages:\n{lines}"}],
        PICK_SCHEMA, api_key, models=judge_models(), temperature=0.0, max_tokens=3000,
    )
    try:
        return json.loads(content)
    except ValueError as exc:
        raise ExtractionError(f"Model returned invalid JSON: {content[:200]!r}") from exc


def _occurs(sentence: str, text: str) -> str | None:
    """The copied sentence as written in the passage (with its diacritics), or None if it is not in the passage."""
    want = normalize(sentence).split()
    if len(want) < 3:
        return None
    for part in _SENTENCE.split(text):
        if " ".join(want) in normalize(part):
            return part.strip()
    words = normalize(text).split()
    joined = " ".join(words)
    return sentence.strip() if " ".join(want) in joined else None


# ---------- the check ----------
SUMMARIES = {
    "consensus_claim_disputed": (
        "النص يدّعي الإجماع أو الاتفاق، والموسوعة الفقهية تنقل في هذه المسألة خلافًا بين الفقهاء.",
        "The text claims consensus, but the encyclopedia reports disagreement among the jurists on this question.",
    ),
    "stated_as_certain_disputed": (
        "النص يعرض الحكم بصيغة القطع، والموسوعة الفقهية تنقل في المسألة خلافًا؛ فالأولى بيان الخلاف أو نسبة القول إلى قائله.",
        "The text states the ruling as settled, but the encyclopedia reports disagreement: the opinions should be attributed or the disagreement mentioned.",
    ),
    "disagreement_acknowledged": (
        "النص يشير إلى الخلاف أو ينسب القول، وهذا موافق لما تنقله الموسوعة من خلاف في المسألة.",
        "The text acknowledges the disagreement, in line with what the encyclopedia reports.",
    ),
    "agreement_reported": (
        "تنقل الموسوعة الفقهية الاتفاق في هذه المسألة، والحكم المذكور في النص موافق لما نقلته.",
        "The encyclopedia reports agreement on this question, and the text's ruling matches it.",
    ),
    "agreement_differs": (
        "تنقل الموسوعة الفقهية في هذه المسألة حكمًا متفقًا عليه يختلف عمّا ذكره النص؛ فيُراجع النص.",
        "The encyclopedia reports an agreed ruling on this question that differs from the text's: the text needs review.",
    ),
    "partly_disputed": (
        "تنقل الموسوعة الاتفاق في جانب من المسألة والخلاف في جانب آخر؛ فليُراجع موضع الحكم في النص المنقول أدناه.",
        "The encyclopedia reports agreement on part of the question and disagreement on another part: compare the passage below.",
    ),
    "found_no_marker": (
        "وجدنا المسألة في الموسوعة دون تصريح باتفاق أو خلاف؛ النص المنقول أدناه للمراجعة.",
        "The question is in the encyclopedia without an explicit statement of agreement or disagreement; the passage is below for review.",
    ),
    "not_found": (
        "لم نجد هذه المسألة في الموسوعة الفقهية الكويتية؛ فلا نبني عليها حكمًا، ويُرجع فيها إلى مختص.",
        "We did not find this question in the Kuwaiti Fiqh Encyclopedia, so nothing is concluded; refer it to a specialist.",
    ),
    "not_fiqh": ("لا يتضمن النص حكمًا فقهيًا.", "The text states no fiqh ruling."),
}
ATTENTION = {"consensus_claim_disputed", "stated_as_certain_disputed", "agreement_differs", "partly_disputed", "not_found"}


def _status(assertion: str, shown: list[FiqhPassage]) -> str:
    if not shown:
        return "not_found"
    marks = {p.agreement for p in shown if p.same_issue is not False}
    direction = next((p.direction for p in shown if p.direction in ("same", "different")), None)
    if "disagreement" in marks:
        return {"consensus": "consensus_claim_disputed", "definite": "stated_as_certain_disputed"}.get(assertion, "disagreement_acknowledged")
    if "both" in marks:
        return "consensus_claim_disputed" if assertion == "consensus" else "partly_disputed" if assertion != "hedged" else "disagreement_acknowledged"
    if "agreement" in marks:
        return "agreement_differs" if direction == "different" else "agreement_reported"
    return "found_no_marker"


def _level(status: str) -> str:
    """Content level of the scientific pack: (ب) explanation with the reference shown, (ج) a disputed question."""
    return "ب" if status in ("agreement_reported", "agreement_differs", "found_no_marker", "not_fiqh") else "ج"


async def fiqh_check(claim: str, use_llm: bool = True, api_key: str | None = None, key_terms: list[str] | None = None) -> FiqhCheck:
    assertion, words = assertion_of(claim)
    if assertion == "none":
        return _result(claim, assertion, words, "not_fiqh", [], "keywords")
    hits = fiqh_index().search(search_terms(claim, key_terms), POOL) if passages() else []
    error = None
    if use_llm and hits:
        try:
            pool = [passages()[i] for i, _, _ in hits]
            data = await pick_passages(claim, tuple(p.text for p in pool), api_key)
            if data.get("in_scope") is False:
                return _result(claim, assertion, words, "not_fiqh", [], "model")
            shown = []
            for v in data.get("passages", []):
                k = v.get("number")
                if not isinstance(k, int) or not 0 <= k < len(pool) or not v.get("same_issue"):
                    continue
                ruling = _occurs(v.get("ruling_sentence") or "", pool[k].text)
                shown.append(_passage_out(pool[k], hits[k][1], ruling, v.get("direction"), True))
            shown.sort(key=lambda p: -p.score)
            return _result(claim, assertion, words, _status(assertion, shown[:SHOW]), shown[:SHOW], "model")
        except Exception as exc:  # no key, network, malformed answer: fall back to the keyword match below
            error = f"{type(exc).__name__}: {str(exc)[:160]}"
    shown = [
        _passage_out(passages()[i], score, same=None)
        for i, score, share in hits[:SHOW]
        if share >= KEYWORD_MIN_SHARE and set(terms(passages()[i].heading + " " + passages()[i].entry)) & set(query_terms(claim, key_terms))
    ]
    result = _result(claim, assertion, words, _status(assertion, shown[:1]) if shown else "not_found", shown[:SHOW], "keywords")
    result.error = error
    return result


def _result(claim: str, assertion: str, words: list[str], status: str, shown: list[FiqhPassage], by: str) -> FiqhCheck:
    ar, en = SUMMARIES[status]
    if by == "keywords" and shown:
        ar += " (مطابقة بالكلمات: تأكّد أن النص المنقول في المسألة نفسها.)"
        en += " (Keyword match: confirm the passage is about the same question.)"
    return FiqhCheck(
        claim=claim, assertion=assertion, assertion_words=words, status=status, attention=status in ATTENTION,
        content_level=_level(status) if status != "not_fiqh" else None, summary_ar=ar, summary_en=en,
        passages=shown, matched_by=by, source_ar=SOURCE_AR, source_en=SOURCE_EN, notice_ar=NOTICE_AR, notice_en=NOTICE_EN,
    )
