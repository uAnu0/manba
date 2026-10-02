"""Let an LLM recall which Quran verses and hadith bear on a question; the corpus then checks every one of them.

Keyword search alone cannot bridge the gap between how a question is phrased and how the texts are worded
("الرشوة" vs "الراشي والمرتشي", "الانتحار" vs "من قتل نفسه"). A language model knows the well-known evidences, so it is
asked to *recite* them in Arabic. Its recitations are never shown: each is looked up in the local corpus, and only the
corpus text (with its real source and gradings) reaches the user. Whatever cannot be found there is discarded and
reported as rejected. The model neither answers the question nor produces a ruling.
"""
import json

from app.services.llm_extractor import ExtractionError, chat_json

SYSTEM_PROMPT = (
    "You are a retrieval helper for a Quran and hadith search tool. The user asks a question about Islam in any "
    "language. Do NOT answer it and do NOT give a ruling. List the evidence a scholar would cite for it: up to 6 "
    "Quran verses and up to 8 hadith from the books of Bukhari, Muslim, Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah, "
    "Malik, Ahmad and Darimi. Write each text in Arabic WITHOUT diacritics, as exactly as you remember it: for a hadith "
    "only the words of the Prophet (peace be upon him), no chain of narrators, no 'عن فلان'; at most 25 words per text; "
    "no commentary, numbering, grading or attribution. Prefer the most direct and best-known evidences. "
    "If you are unsure of a text, leave it out."
)

SUGGESTIONS_SCHEMA = {
    "name": "evidence_suggestions",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "verses": {"type": "array", "items": {"type": "string"}},
            "hadiths": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["verses", "hadiths"],
        "additionalProperties": False,
    },
}


async def suggest_evidence(question: str, api_key: str | None = None) -> list[str]:
    """The model's recitations (verses first, then hadith). Unverified: callers must check them against the corpus."""
    content = await chat_json(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}], SUGGESTIONS_SCHEMA, api_key
    )
    try:
        data = json.loads(content)
        texts = list(data["verses"]) + list(data["hadiths"])
    except (TypeError, ValueError, KeyError) as exc:
        raise ExtractionError(f"Model returned invalid JSON: {content!r}") from exc
    if not all(isinstance(t, str) for t in texts):
        raise ExtractionError(f"Model returned an unexpected shape: {content!r}")
    return [t.strip() for t in texts if t.strip()][:16]


RERANK_SCHEMA = {
    "name": "relevant_texts",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {"relevant": {"type": "array", "items": {"type": "integer"}}},
        "required": ["relevant"],
        "additionalProperties": False,
    },
}
RERANK_PROMPT = (
    "You rank search results. The user asks a question about Islam. Below are numbered Quran verses or hadith texts "
    "retrieved from a library. Do NOT answer the question. Return the numbers of the texts that are DIRECT evidence "
    "for the topic of the question (the ones a scholar would cite), best first, at most {n}. "
    "Return only numbers that appear in the list."
)


async def rerank(question: str, excerpts: list[str], limit: int, api_key: str | None = None) -> list[int]:
    """Positions (into `excerpts`) of the most relevant texts, best first. The model only picks from what it is
    shown: it writes no evidence, and anything outside the list is ignored."""
    lines = "\n".join(f"{k}. {text[:300]}" for k, text in enumerate(excerpts))
    content = await chat_json(
        [
            {"role": "system", "content": RERANK_PROMPT.format(n=limit)},
            {"role": "user", "content": f"Question: {question}\n\n{lines}"},
        ],
        RERANK_SCHEMA,
        api_key,
    )
    try:
        picked = json.loads(content)["relevant"]
    except (TypeError, ValueError, KeyError) as exc:
        raise ExtractionError(f"Model returned invalid JSON: {content!r}") from exc
    return [k for k in dict.fromkeys(picked) if isinstance(k, int) and 0 <= k < len(excerpts)][:limit]
