from typing import Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str


class VerifyRequest(BaseModel):
    text: str = Field(..., min_length=1)
    use_llm: bool = False  # also run the LLM claim extractor (needs OPENROUTER_API_KEY)


class Source(BaseModel):
    book: str
    chapter: str
    number: str
    matched_text: str
    other_matches_count: int = 0  # further corpus entries that match equally well (repeated verses, shared phrases)


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
