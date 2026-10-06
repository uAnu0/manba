from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


MAX_INPUT_WORDS = 500


def _limit_words(value: str) -> str:
    """Every text a person can submit is limited, so nobody can send a whole book."""
    words = len(value.split())
    if words > MAX_INPUT_WORDS:
        raise ValueError(f"Input is limited to {MAX_INPUT_WORDS} words; this text has {words}.")
    return value


class HealthResponse(BaseModel):
    status: str
    app: str


class VerifyRequest(BaseModel):
    text: str = Field(..., min_length=1)
    use_llm: bool = False  # also run the LLM claim extractor (needs OPENROUTER_API_KEY)

    _words = field_validator("text")(_limit_words)


class Grade(BaseModel):
    """A hadith grading by a named scholar, as given by the dataset (e.g. Al-Albani: Sahih)."""

    name: str
    grade: str


class Source(BaseModel):
    book: str
    chapter: str
    number: str
    matched_text: str
    other_matches_count: int = 0  # further corpus entries that match equally well (repeated verses, shared phrases)
    grades: list[Grade] = Field(default_factory=list)  # hadith only, when the dataset has them
    level: Optional[int] = None  # 1 Quran, 2 Sahih al-Bukhari / Sahih Muslim, 3 other hadith (see services/strength.py)
    strength: Optional[str] = None  # quran | sahihayn | sahih | hasan | daif | disputed | ungraded


class OfficialTranslation(BaseModel):
    """The approved translation a non-Arabic quote was compared with (QuranEnc for the Quran), shown exactly as published."""

    kind: Literal["quran", "hadith"]
    key: str  # e.g. english_saheeh
    title: str
    language: str
    version: Optional[str] = None
    text: str  # the official wording of this verse or hadith in that language
    source_url: str = ""
    match: float = 0.0  # share of the quoted words found, in order, in the official wording


class Segment(BaseModel):
    segment_text: str
    classification: Literal["quran", "hadith", "unverified"]
    status: Literal["verified", "semantic_variant", "baseless"]
    match_type: Literal["full", "partial"] = "full"  # "partial": verbatim quote of part of a longer entry
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: Optional[Source] = None
    differences: list[str] = Field(default_factory=list)
    # False for a sentence in which the LLM step found no quote or claim (ordinary commentary): it is still
    # returned, but it is not a claim that failed verification.
    is_claim: bool = True
    # Content level of the challenge's scientific pack (services/levels.py): أ settled text, ب explanation,
    # ج disputed or needs care, د personal case. None when nothing was found to classify.
    content_level: Optional[Literal["أ", "ب", "ج", "د"]] = None
    translation: Optional[OfficialTranslation] = None  # a quote in another language: the official translation it was matched with


class ExtractionInfo(BaseModel):
    """What the optional LLM extraction step did."""

    used: bool
    claims_found: int = 0
    claims_accepted: int = 0
    rejected: list[str] = Field(default_factory=list)  # claims the model returned that are not in the text
    error: Optional[str] = None


class VerifyResponse(BaseModel):
    original_text: str
    word_count: int
    segments: list[Segment]
    extraction: Optional[ExtractionInfo] = None


class EvidenceRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    use_llm: bool = False  # also let an LLM recite the evidence it knows (each text is checked against the corpus)
    use_meaning: bool = True  # meaning-based search with embeddings (needs an OpenRouter key and data/corpus_embeddings.npz)

    _words = field_validator("question")(_limit_words)


class EvidenceItem(BaseModel):
    classification: Literal["quran", "hadith"]
    score: float
    matched_terms: list[str] = Field(default_factory=list)
    source: Source  # matched_text is an excerpt; for a hadith it starts after the chain of narrators
    full_text: str  # the whole corpus text, including the chain of narrators for a hadith
    found_by: list[Literal["meaning", "keyword", "suggestion"]] = Field(default_factory=list)
    # meaning: nearest by embedding; keyword: matching words; suggestion: recalled by the LLM and then found in the corpus
    similarity: Optional[float] = None  # cosine similarity of the meaning search (1.0 = identical meaning)
    exact_wording: bool = True  # False when the LLM's recitation differed slightly from the corpus text
    relevance: Optional[Literal["direct", "related"]] = None  # the LLM judge's verdict, when the LLM step ran
    stance: Optional[Literal["supports", "contradicts", "related", "partial"]] = None  # claim verification: how it bears on the claim
    covers_all: Optional[bool] = None  # the judge's view: this text addresses the whole claim (False: only part of it, weighed at half)
    covers: list[str] = Field(default_factory=list)  # stance "partial": the parts of the claim this text itself addresses (model-written)
    says: Optional[str] = None  # the judge model's one-line note on what the text says (model-written, used by the explanation)
    context_ar: Optional[str] = None  # a verse only: the tafsir's commentary on it, verbatim (services/tafsir.context_of)
    context_source: Optional[str] = None  # the tafsir's name


class QueryInfo(BaseModel):
    """What the optional LLM step did: texts it recalled, how many the corpus confirmed, and which it could not."""

    used: bool
    suggested: int = 0
    found_in_corpus: int = 0
    rejected: list[str] = Field(default_factory=list)  # recalled texts that are not in the corpus (never shown as evidence)
    error: Optional[str] = None
    meaning_used: bool = False  # the embedding search ran
    reranked: bool = False  # an LLM judged each retrieved candidate and dropped the unrelated ones (it writes no evidence)
    meaning_error: Optional[str] = None


class EvidenceResponse(BaseModel):
    question: str
    search_terms: list[str]
    query: QueryInfo
    quran: list[EvidenceItem]
    hadith: list[EvidenceItem]
    refer_to_scholar: bool
    in_scope: bool = True  # False when the LLM judge says the question is not about Islam
    reason: Optional[str] = None
    notice_ar: str
    notice_en: str


class ClaimRequest(BaseModel):
    claim: str = Field(..., min_length=3, max_length=3000)
    use_llm: bool = True  # routing and judging the evidence need a model; without it only keyword/meaning evidence is returned
    use_meaning: bool = True

    _words = field_validator("claim")(_limit_words)


class ClaimLLMInfo(BaseModel):
    used: bool = False
    error: Optional[str] = None
    recited: int = 0  # texts the model recalled for the claim
    recited_found: int = 0  # of those, how many exist in the corpus


class SimilarText(BaseModel):
    """The verse or hadith closest to a sentence that matched nothing word for word: a pointer, never a verification."""

    evidence: EvidenceItem
    similarity: float  # cosine of the meaning search
    shared_share: float  # share of the sentence's distinctive words that this text also contains
    shared_words: int
    missing_words: list[str] = Field(default_factory=list)  # words of the sentence that are NOT in that text


class DorarItem(BaseModel):
    """One narration as Dorar's hadith encyclopedia gives it, with the ruling of the scholar named (not ours)."""

    text: str
    narrator: str = ""
    scholar: str = ""  # المحدث
    source: str = ""  # المصدر
    page: str = ""  # الصفحة أو الرقم
    grade: str = ""  # خلاصة حكم المحدث, verbatim
    category: Literal["sahih", "hasan", "daif", "fabricated", "other"]  # read by code from the ruling's words, for display only


class DorarResult(BaseModel):
    query: str
    available: bool
    items: list[DorarItem] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    error: Optional[str] = None


class FiqhPosition(BaseModel):
    """A sentence of the encyclopedia that names one or more schools, quoted verbatim."""

    schools: list[str]
    text: str
    ruling: Optional[str] = None  # read by code from the sentence's own words: واجب، سنة، حرام، مكروه، جائز، غير واجب...


class FiqhAttribution(BaseModel):
    """The text attributes a ruling to a school ("واجبة عند الحنابلة"): what the encyclopedia reports for that school."""

    school: str
    claimed: str  # the ruling the text attributes
    reported: Optional[str] = None  # the ruling the encyclopedia's sentence on that school states
    status: Literal["matches", "differs", "not_reported"]
    text: str = ""  # the encyclopedia's sentence, verbatim
    cite: str = ""


class FiqhPassage(BaseModel):
    """One numbered paragraph of the Kuwaiti Fiqh Encyclopedia, with where it is printed."""

    entry: str  # the encyclopedia entry (مادة)
    section: str = ""
    heading: str = ""  # the paragraph's own heading, e.g. "زكاة الحلي"
    number: int = 0  # paragraph number within the entry
    volume: int
    page: int
    text: str
    agreement: Literal["agreement", "disagreement", "both", "none"]  # read by code from the encyclopedia's own wording
    positions: list[FiqhPosition] = Field(default_factory=list)
    ruling_sentence: Optional[str] = None  # the passage's sentence on the issue, copied by the model and found in the passage
    direction: Optional[Literal["same", "different", "unclear"]] = None  # does the person's ruling match what the passage reports
    same_issue: Optional[bool] = None  # model's decision; None for a keyword match nobody confirmed
    score: float = 0.0
    cite: str


class FiqhCheck(BaseModel):
    claim: str
    assertion: Literal["consensus", "definite", "hedged", "none"]  # how the person's sentence states the ruling
    assertion_words: list[str] = Field(default_factory=list)
    status: Literal[
        "consensus_claim_disputed",  # claims consensus; the encyclopedia reports disagreement
        "stated_as_certain_disputed",  # a flat ruling on a question the encyclopedia reports as disputed
        "disagreement_acknowledged",  # the text itself mentions the disagreement or attributes the opinion
        "agreement_reported",  # the encyclopedia reports agreement, and the ruling matches
        "agreement_differs",  # the encyclopedia reports an agreed ruling different from the text's
        "partly_disputed",  # agreement on part, disagreement on another part
        "found_no_marker",  # found, without explicit agreement or disagreement
        "school_matches",  # the text attributes the ruling to a school, and the encyclopedia reports that school's view the same way
        "school_differs",  # the text attributes to a school a ruling the encyclopedia reports differently for it
        "not_found",
        "not_fiqh",
    ]
    attention: bool = False
    content_level: Optional[Literal["أ", "ب", "ج", "د"]] = None
    summary_ar: str
    summary_en: str
    passages: list[FiqhPassage] = Field(default_factory=list)
    matched_by: Literal["model", "keywords"]
    source_ar: str
    source_en: str
    notice_ar: str
    notice_en: str
    error: Optional[str] = None
    attribution: Optional[FiqhAttribution] = None
    schools: list[FiqhPosition] = Field(default_factory=list)  # each school the ruling paragraph names, with the ruling it states for it


class FiqhRequest(BaseModel):
    claim: str = Field(..., min_length=3, max_length=2000)
    use_llm: bool = True

    _words = field_validator("claim")(_limit_words)


class ClaimResponse(BaseModel):
    claim: str
    claim_type: Literal["quote", "topic", "personal", "not_religious", "unknown"]
    restated_claim: Optional[str] = None  # what the router understood (model-written: shown so the person can check it)
    opposite_claim: Optional[str] = None  # searched for counter-evidence
    outcome: Literal[
        "quote_checked",  # the claim is a quote: see quote_check
        "supported",  # direct evidence for the claim, at least one strong source, none against
        "supported_weakly",  # evidence for the claim, but only from weak or ungraded hadith
        "supported_in_part",  # texts support some parts of the claim; nothing found covers all of it
        "contradicted",  # direct evidence against the claim, none for it
        "mixed",  # evidence on both sides: a scholar is needed
        "no_clear_evidence",
        "refer_to_scholar",  # a personal question or case: a scholar must answer it
        "out_of_scope",
        "evidence_only",  # no model was available to judge: texts found, no stance
    ]
    summary_en: str
    summary_ar: str
    quote_check: Optional[VerifyResponse] = None
    supporting: list[EvidenceItem] = Field(default_factory=list)
    contradicting: list[EvidenceItem] = Field(default_factory=list)
    partial: list[EvidenceItem] = Field(default_factory=list)  # texts that support only some parts of the claim
    related: list[EvidenceItem] = Field(default_factory=list)
    refer_to_scholar: bool = False
    reason: Optional[str] = None
    notice_ar: str
    notice_en: str
    similar: Optional[SimilarText] = None  # a known text this wording is close to (see services/similar.py)
    fiqh: Optional[FiqhCheck] = None  # a sentence that states a fiqh ruling: what the fiqh encyclopedia reports (services/fiqh.py)
    content_level: Optional[Literal["أ", "ب", "ج", "د"]] = None  # level of the scientific pack (services/levels.py)
    llm: ClaimLLMInfo = Field(default_factory=ClaimLLMInfo)


class TextCheckRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=12000)
    use_llm: bool = True  # finding and judging claims needs a model; without it only the quotes are checked
    use_meaning: bool = True

    _words = field_validator("text")(_limit_words)


class TextClaimItem(BaseModel):
    kind: Literal["quote", "claim", "similar"]
    text: str  # as written in the input
    start: int
    end: int
    quote: Optional[Segment] = None  # kind == "quote": what the verifier found
    result: Optional[ClaimResponse] = None  # kind == "claim": the claim check
    fragment: bool = False  # kind == "quote": an unmarked run of five words or fewer that happens to occur in a text: a matched phrase, not a quotation
    similar: Optional[SimilarText] = None  # kind == "similar": a sentence close to a known text, nothing else found in it
    content_level: Optional[Literal["أ", "ب", "ج", "د"]] = None  # level of the scientific pack (services/levels.py)
    translated_ar: Optional[str] = None  # a claim written in another language: the machine translation that was searched (model-written)
    verdict_kind: Optional[Literal["bad", "fix", "khl", "ref", "neu", "ok"]] = None
    needs_action: bool = True


class BadgeInfo(BaseModel):
    """The serial of a clean review, signed by the server (services/badge.py). Anyone can check it at /api/badge/{code}."""

    code: str  # MNB-XXXX-XXXX-XXXX-XXXX
    date: str  # the day of the review, YYYY-MM-DD
    mode: str  # "full": quotes, claims and rulings with the AI's help; "matching": direct matching only (no model)
    items: int  # how many texts and rulings were checked


class BadgeVerifyRequest(BaseModel):
    code: str = Field(..., max_length=128)
    text: Optional[str] = Field(default=None, max_length=60000)


class BadgeRecoverResponse(BaseModel):
    found: bool  # a serial the signature accepts was found within a few confusable characters of the one given
    code: Optional[str] = None  # that serial
    corrected: bool = False  # it differs from the one given
    checked: bool = True  # False when the server cannot check signatures (no signing key): the serial was not changed


class BadgeVerifyResponse(BaseModel):
    valid: bool
    code: str
    date: Optional[str] = None
    mode: Optional[str] = None
    text_matches: Optional[bool] = None  # only when a text was sent: is it the very text that was reviewed?
    reason: Optional[str] = None


class TextCheckResponse(BaseModel):
    original_text: str
    word_count: int
    items: list[TextClaimItem]
    sentences: int
    commentary_sentences: int  # sentences with neither a quote nor a claim
    skipped_claims: int = 0  # claims beyond the per-request limit (the text is still not checked for them)
    truncated: bool = False  # the text had more sentences than the limit
    summary: dict[str, int] = Field(default_factory=dict)  # count per outcome / quote status
    llm: ClaimLLMInfo = Field(default_factory=ClaimLLMInfo)
    language: str = "ar"  # language of the input: ar, en, fr, ur, id, tr, es, other
    translations_used: list[str] = Field(default_factory=list)  # titles of the official translations searched
    content_type: str = "text"  # khutbah | article | post | lesson | question | text (services/genre.py)
    content_type_ar: str = "النص"
    content_type_cues: list[str] = Field(default_factory=list)  # the words that decided it
    blocking: int = 0  # findings that must change before publishing (services/badge.py; the page shows the same count)
    badge: Optional[BadgeInfo] = None  # given only when nothing blocks publishing
    review_complete: bool = False
    badge_unavailable: Optional[str] = None


class TafsirEntry(BaseModel):
    source_id: str
    name_ar: str
    name_en: str
    author_ar: str
    text: str  # as the author wrote it (only markup removed)
    covers_from: Optional[str] = None  # the author commented on a group of verses at once: the first and last verse of the group
    covers_to: Optional[str] = None


class TafsirVerse(BaseModel):
    ref: str  # sura:ayah
    entries: list[TafsirEntry] = Field(default_factory=list)


class TafsirResponse(BaseModel):
    ref: str
    verses: list[TafsirVerse]
    available: list[str] = Field(default_factory=list)  # the tafsirs this server has


class OcrRequest(BaseModel):
    image: str = Field(..., max_length=4_500_000)  # a PNG, JPEG or WebP data URL: one page, already shrunk by the browser
    page: int = Field(1, ge=1, le=999)


class OcrDiff(BaseModel):
    before: str = ""  # up to three words of the first reading before the difference
    a: str  # what the first reading has there (may be empty: the second reading has extra words)
    b: str  # what the second reading has there (may be empty: the second reading lacks these words)
    after: str = ""


class OcrResponse(BaseModel):
    page: int
    text: str  # the first reading: the text that is used
    text_b: Optional[str] = None  # the second reading
    diffs: list[OcrDiff] = Field(default_factory=list)  # words on which the two readings differ: to check against the page
    words: int
    model_a: str
    model_b: str
    note: Optional[str] = None


class ExplainRequest(BaseModel):
    claim: str = Field(..., min_length=3, max_length=3000)
    result: Optional[ClaimResponse] = None  # a claim-check result as returned by /api/claim (or an item of /api/check)
    segment: Optional[Segment] = None  # or one quoted-text result from /api/verify or /api/check

    _words = field_validator("claim")(_limit_words)


class ExplainText(BaseModel):
    n: int
    kind: str  # quran | hadith | quote
    label: str  # the source in Arabic, or the quoted text
    stance_ar: str = ""
    strength_ar: str = ""
    grades_ar: str = ""


class ExplainPoint(BaseModel):
    text: str  # Arabic
    cites: list[int]  # numbers into `texts`


class ExplainResponse(BaseModel):
    claim: str
    outcome: str  # the verdict the explanation is about (never changed by the writer)
    summary_ar: str = ""
    points: list[ExplainPoint]
    caution: Optional[str] = None
    texts: list[ExplainText]
    ai_written: bool  # False: built by code from the same facts (the writer failed or failed the checks)
    model: Optional[str] = None
    note: Optional[str] = None  # why the AI-written explanation was not used
