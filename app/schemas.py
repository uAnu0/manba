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
    use_meaning: bool = True  # meaning-based search with embeddings (needs an OpenRouter key and corpus_embeddings.npz)

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
    covers: list[str] = Field(default_factory=list)  # stance "partial": the parts of the claim this text itself addresses (model-written)
    says: Optional[str] = None  # the judge model's one-line note on what the text says (model-written, used by the explanation)


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
    similar: Optional[SimilarText] = None  # kind == "similar": a sentence close to a known text, nothing else found in it


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
