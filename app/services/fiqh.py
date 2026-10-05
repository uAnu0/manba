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

from app.schemas import FiqhAttribution, FiqhCheck, FiqhPassage, FiqhPosition
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
    if not ruling and re.search(r"\bسن[هة]\s+(?:مؤكد[هة]\s+)?(?:عند|في مذهب|على قول)\b", t):
        ruling = ["سنة"]  # "الوتر سنة عند الجمهور": attributed to a school, it is a ruling
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


# Rulings, as words: a school's position and a person's sentence are compared by the family of the ruling word, never by
# a model. The negated forms are read first ("لا يجب" is not "يجب").
RULING_FAMILIES = [
    ("غير واجب", _n("لا يجب|لا تجب|ليس بواجب|ليست بواجبة|غير واجب|غير واجبة|عدم الوجوب|عدم وجوب|لا يلزم")),
    ("لا يجوز", _n("لا يجوز|لا تجوز|عدم الجواز|عدم جواز|غير جائز|غير جائزة")),
    ("لا ينقض", _n("لا ينقض|لا تنقض|عدم النقض|عدم نقض|غير ناقض")),
    ("واجب", _n("واجب|واجبة|وجوب|يجب|تجب|فرض|فريضة|يفترض|لازم|يلزم")),
    ("سنة", _n("سنة|مسنون|مسنونة|يسن|تسن|مستحب|مستحبة|يستحب|استحباب|مندوب|مندوبة|يندب")),
    ("حرام", _n("حرام|محرم|محرمة|يحرم|تحرم|تحريم|حرمة")),
    ("مكروه", _n("مكروه|مكروهة|يكره|تكره|كراهة|كراهية")),
    ("جائز", _n("يجوز|تجوز|جائز|جائزة|جواز|مباح|مباحة|إباحة|يباح")),
    ("ينقض", _n("ينقض|تنقض|نقض|ناقض|ناقضة")),
    ("يبطل", _n("يبطل|تبطل|باطل|باطلة|بطلان|يفسد|تفسد|فاسد|فاسدة")),
]
_SAME = {"لا يجوز": {"لا يجوز", "حرام"}, "حرام": {"حرام", "لا يجوز"}, "غير واجب": {"غير واجب", "سنة", "جائز", "مكروه"}}


def rulings_of(text: str) -> list[str]:
    """The ruling families a sentence states, in order of first mention; a negated form hides its positive."""
    t = normalize(text)
    found: list[tuple[int, str]] = []
    masked = f" {t} "
    for label, forms in RULING_FAMILIES:
        for f in forms:
            for c in ("", "و", "ف", "ب", "ل"):
                k = masked.find(f" {c}{f}")
                while k >= 0:
                    found.append((k, label))
                    masked = masked[:k + 1] + "_" * (len(c) + len(f)) + masked[k + 1 + len(c) + len(f):]  # a negated phrase is not read again as positive
                    k = masked.find(f" {c}{f}")
    found.sort()
    return list(dict.fromkeys(label for _, label in found))


def positions_of(text: str) -> list[FiqhPosition]:
    """The sentences of a passage that name a school, verbatim (with the school names they mention and the ruling they state)."""
    out = []
    for sentence in _SENTENCE.split(text):
        sentence = sentence.strip()
        if len(sentence) < 15:
            continue
        t = normalize(sentence)
        names = [name for name, forms in SCHOOLS if _has(t, forms)]
        if names:
            rs = rulings_of(sentence)
            out.append(FiqhPosition(schools=names, text=sentence[:600], ruling=rs[0] if rs else None))
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


# A sentence that states a ruling is about the ruling of the act: the encyclopedia's paragraph that gives it ("حكم صلاة
# الوتر"، "الحكم التكليفي") ranks above paragraphs on the same act's time, manner or making up. Ranking only: nothing here
# decides agreement or disagreement, which is still read from the paragraph's own words.
_RULING_HEAD = re.compile("حكم|الحكم التكليفي|مشروعيت|حكمه")
_RULING_TEXT = _n("واجب|واجبة|وجوب|يجب|فرض|سنة مؤكدة|مسنون|مستحب|يستحب|يجوز|جواز|لا يجوز|حرام|يحرم|تحريم|مكروه|يكره|مباح|ذهب الجمهور|اختلف الفقهاء|اتفق الفقهاء")


def _ruling_first(hits: list[tuple[int, float, float]]) -> list[tuple[int, float, float]]:
    items = passages()
    if not hits:
        return hits
    best_entry = items[hits[0][0]].entry  # reorder within the entry that matched best; never pull in another entry
    out = []
    for i, score, share in hits:
        p = items[i]
        factor = 1.0
        if p.entry != best_entry:
            out.append((i, score, share))
            continue
        if _RULING_HEAD.search(normalize(p.heading or "")):
            factor *= 1.6
        if _has(normalize(p.text[:400]), _RULING_TEXT):
            factor *= 1.25
        out.append((i, score * factor, share))
    out.sort(key=lambda x: -x[1])
    return out


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
    "school_matches": ("نسبة القول إلى المذهب موافقة لما تنقله الموسوعة الفقهية.", "The attribution to the school matches the encyclopedia."),
    "school_differs": ("نسبة القول إلى المذهب تخالف ما تنقله الموسوعة الفقهية عنه.", "The attribution to the school differs from the encyclopedia."),
}
ATTENTION = {"school_differs", "consensus_claim_disputed", "stated_as_certain_disputed", "agreement_differs", "partly_disputed", "not_found"}


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
    return "ب" if status in ("agreement_reported", "agreement_differs", "found_no_marker", "not_fiqh", "school_matches") else "ج"


async def fiqh_check(claim: str, use_llm: bool = True, api_key: str | None = None, key_terms: list[str] | None = None) -> FiqhCheck:
    assertion, words = assertion_of(claim)
    if assertion == "none":
        return _result(claim, assertion, words, "not_fiqh", [], "keywords")
    hits = _ruling_first(fiqh_index().search(search_terms(claim, key_terms), POOL * 2))[:POOL] if passages() else []
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


# School names only as schools: "مالك" or "أحمد" alone is often a narrator ("أنس بن مالك"), not the school.
STRICT_SCHOOLS = [
    ("الحنفية", _n("الحنفية|الأحناف|أبو حنيفة|أبي حنيفة|أبا حنيفة")),
    ("المالكية", _n("المالكية|الإمام مالك")),
    ("الشافعية", _n("الشافعية|الشافعي")),
    ("الحنابلة", _n("الحنابلة|الحنبلية|الإمام أحمد|مذهب أحمد")),
    ("الجمهور", _n("الجمهور|جمهور الفقهاء|جمهور العلماء")),
]
_CLAUSE = re.compile(r"\s(?=(?:و|ف)?(?:ذهب|قال|يرى|صرح|نص|عند|اما|أما|بينما)\s)|[؛.]\s*")


def _school_sentences(text: str) -> list[str]:
    """The passage's sentences, with a sentence that ends on a colon ("وذهب الحنابلة:") joined to the one after it."""
    out: list[str] = []
    for part in _SENTENCE.split(text):
        part = part.strip()
        if out and out[-1].rstrip().endswith(":"):
            out[-1] = f"{out[-1]} {part}"
        elif part:
            out.append(part)
    return out


_HEAD_END = re.compile(r"\s(?:الى|إلى|على)\s+(?:ان|أن)\s|\sب(?:ان|أن)\s|\sان\s")
_NOT_SCHOOL = re.compile(r"(?:\sمن|\sبعض|\sاحد قولي|\sأحد قولي|\sروايه عن|\sرواية عن|\sقول عند|\sفي قول|\sقول ل|\sوجه عند|\sمتاخري|\sمتأخري)\s+(?:ال)?$")


def _subject(clause: str, forms: list[str]) -> bool:
    """The school is what the clause is about: named before "إلى أن / بأن", not as "من الحنابلة" (one scholar),
    "بعض الحنابلة", "أحد قولي الشافعي" or "رواية عن أحمد" (a minority view)."""
    m = _HEAD_END.search(f" {clause} ")
    head = f" {clause} "[: m.start() + 1] if m else f" {clause} "
    for f in forms:
        for c in ("", "و", "ف", "ب", "ل"):
            k = head.find(f" {c}{f}")
            if k >= 0 and not _NOT_SCHOOL.search(head[:k + 1]):
                return True
    return False


def school_ruling(text: str, school: str) -> tuple[str, list[str]] | None:
    """(the sentence, verbatim; the rulings it states for that school), read clause by clause."""
    forms = dict(STRICT_SCHOOLS)[school]
    for sentence in _school_sentences(text):
        clauses = [c for c in _CLAUSE.split(normalize(sentence)) if c and c.strip()]
        for k, clause in enumerate(clauses):
            if not _subject(clause, forms):
                continue
            got = rulings_of(clause)  # never borrowed from the next clause: that one may be about someone else
            if got:
                return sentence[:500], got
    return None


SCHOOL_EN = {"الحنفية": "Hanafis", "المالكية": "Malikis", "الشافعية": "Shafi'is", "الحنابلة": "Hanbalis", "الجمهور": "majority"}
RULING_EN = {"واجب": "obligatory", "غير واجب": "not obligatory", "سنة": "sunnah", "حرام": "forbidden", "لا يجوز": "not permitted",
             "مكروه": "disliked", "جائز": "permitted", "ينقض": "breaks wudu", "لا ينقض": "does not break wudu", "يبطل": "invalidates"}


def attribution_of(claim: str, shown: list[FiqhPassage]) -> FiqhAttribution | None:
    """The text says a school holds a ruling ("التسمية واجبة عند الحنابلة"): find that school's view in the passages shown
    and compare the ruling by its words. Nothing is inferred for a school the encyclopedia does not name."""
    t = normalize(claim)
    schools = [name for name, forms in STRICT_SCHOOLS if _has(t, forms)]
    rest = t
    for _, forms in STRICT_SCHOOLS:
        for f in forms:
            rest = rest.replace(f, " ")
    claimed = rulings_of(rest)
    if not schools or not claimed:
        return None
    school, want = schools[0], claimed[0]
    # Only the paragraph ranked first, the one that states the ruling: a later paragraph on the same act (its time, how to
    # make it up) states other rulings for the same school.
    for p in [q for q in shown if q.same_issue is not False][:1]:
        found = school_ruling(p.text, school)
        if not found:
            continue
        sentence, got = found
        ok = want in got or any(g in _SAME.get(want, set()) for g in got)
        return FiqhAttribution(school=school, claimed=want, reported=want if ok else got[0],
                               status="matches" if ok else "differs", text=sentence, cite=p.cite)
    return FiqhAttribution(school=school, claimed=want, status="not_reported")


def _result(claim: str, assertion: str, words: list[str], status: str, shown: list[FiqhPassage], by: str) -> FiqhCheck:
    attribution = attribution_of(claim, shown) if shown else None
    if attribution and attribution.status != "not_reported":
        status = "school_matches" if attribution.status == "matches" else "school_differs"
    ar, en = SUMMARIES[status]
    top = [q for q in shown if q.same_issue is not False][:1]
    schools = []
    for name, _ in STRICT_SCHOOLS:
        found = school_ruling(top[0].text, name) if top else None
        if found:
            schools.append(FiqhPosition(schools=[name], text=found[0], ruling=found[1][0]))
    if attribution and attribution.status == "not_reported":
        ar += f" ولم تُسمِّ فقرة الحكم في الموسوعة {attribution.school}، فلم نتحقق من نسبة القول إليهم."
        en += f" The encyclopedia's ruling paragraph does not name the {SCHOOL_EN.get(attribution.school, attribution.school)}, so the attribution was not checked."
    if attribution and attribution.status == "matches":
        ar = f"نسب النص الحكم «{attribution.claimed}» إلى {attribution.school}، والموسوعة الفقهية تنقله عنهم كذلك."
        en = f"The text attributes '{RULING_EN.get(attribution.claimed, attribution.claimed)}' to the {SCHOOL_EN.get(attribution.school, attribution.school)}; the encyclopedia reports the same for them."
    elif attribution and attribution.status == "differs":
        ar = f"نسب النص إلى {attribution.school} أن الحكم «{attribution.claimed}»، والذي تنقله الموسوعة الفقهية عنهم: «{attribution.reported}»."
        en = f"The text attributes '{RULING_EN.get(attribution.claimed, attribution.claimed)}' to the {SCHOOL_EN.get(attribution.school, attribution.school)}; the encyclopedia reports '{RULING_EN.get(attribution.reported, attribution.reported)}' for them."
    if by == "keywords" and shown:
        ar += " (مطابقة بالكلمات: تأكّد أن النص المنقول في المسألة نفسها.)"
        en += " (Keyword match: confirm the passage is about the same question.)"
    return FiqhCheck(
        claim=claim, assertion=assertion, assertion_words=words, status=status, attention=status in ATTENTION,
        content_level=_level(status) if status != "not_fiqh" else None, summary_ar=ar, summary_en=en,
        passages=shown, matched_by=by, source_ar=SOURCE_AR, source_en=SOURCE_EN, notice_ar=NOTICE_AR, notice_en=NOTICE_EN,
        attribution=attribution, schools=schools,
    )
