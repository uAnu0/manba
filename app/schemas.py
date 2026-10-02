from typing import Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str


class VerifyRequest(BaseModel):
    text: str = Field(..., min_length=1)
    use_llm: bool = False  # also run the LLM claim extractor (needs OPENROUTER_API_KEY)


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


class QueryInfo(BaseModel):
    """What the optional LLM step did: texts it recalled, how many the corpus confirmed, and which it could not."""

    used: bool
    suggested: int = 0
    found_in_corpus: int = 0
    rejected: list[str] = Field(default_factory=list)  # recalled texts that are not in the corpus (never shown as evidence)
    error: Optional[str] = None
    meaning_used: bool = False  # the embedding search ran
    reranked: bool = False  # an LLM chose the final texts among the retrieved candidates (it writes no evidence)
    meaning_error: Optional[str] = None


class EvidenceResponse(BaseModel):
    question: str
    search_terms: list[str]
    query: QueryInfo
    quran: list[EvidenceItem]
    hadith: list[EvidenceItem]
    refer_to_scholar: bool
    reason: Optional[str] = None
    notice_ar: str
    notice_en: str
