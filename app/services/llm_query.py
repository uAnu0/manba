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


JUDGE_SCHEMA = {
    "name": "judgments",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "on_topic": {"type": "boolean"},
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer"},
                        "relevance": {"type": "string", "enum": ["direct", "related", "unrelated"]},
                    },
                    "required": ["number", "relevance"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["on_topic", "verdicts"],
        "additionalProperties": False,
    },
}
JUDGE_PROMPT = (
    "You judge search results for a Quran and hadith search tool. The user asks a question. Below are numbered Quran "
    "verses or hadith texts retrieved from a library. Do NOT answer the question and do not write any evidence. "
    "First decide on_topic: true only if the question is about Islam, Islamic law, belief, worship or ethics as "
    "found in the Quran and hadith; false for anything else (cooking, weather, general facts, chit-chat). "
    "If on_topic is false, return no verdicts. Otherwise give a verdict for every text: "
    "'direct' = a scholar would cite this text as evidence on the topic of the question; "
    "'related' = it is about the same subject but is not what the question asks; "
    "'unrelated' = it has nothing to do with the question. Be strict: a text that merely shares a word with the "
    "question is 'unrelated'."
)


async def judge(question: str, excerpts: list[str], api_key: str | None = None) -> tuple[bool, dict[int, str]]:
    """(is the question on topic, verdict per text position). The model only grades texts it is shown: it writes no
    evidence, and verdicts for positions outside the list are ignored."""
    lines = "\n".join(f"{k}. {text[:300]}" for k, text in enumerate(excerpts))
    content = await chat_json(
        [{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": f"Question: {question}\n\n{lines}"}],
        JUDGE_SCHEMA,
        api_key,
    )
    try:
        data = json.loads(content)
        on_topic = bool(data["on_topic"])
        verdicts = {
            v["number"]: v["relevance"]
            for v in data["verdicts"]
            if isinstance(v["number"], int) and 0 <= v["number"] < len(excerpts)
        }
    except (TypeError, ValueError, KeyError) as exc:
        raise ExtractionError(f"Model returned invalid JSON: {content!r}") from exc
    return on_topic, verdicts
