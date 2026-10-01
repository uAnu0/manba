"""Extract verifiable religious claims from raw text using an LLM via OpenRouter."""
import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "openai/gpt-4o-mini"

SYSTEM_PROMPT = (
    "You extract verifiable religious content from raw text such as a sermon or a social media post. "
    "Return every distinct item that is a Quranic quote, a Prophetic tradition (hadith) quote, "
    "or a specific religious claim attributed to the Quran, the Prophet, or Islamic scripture. "
    "Rules: copy each item exactly as written in the text, in its original language, without translating, "
    "correcting, completing or paraphrasing it, because it will be checked word for word against a reference corpus. "
    "Split separate quotes or claims into separate items. "
    "Skip general commentary, greetings and personal opinions. "
    "If there is nothing to extract, return an empty list."
)

# OpenAI-style strict structured outputs require an object at the root, so the list is wrapped.
CLAIMS_SCHEMA = {
    "name": "extracted_claims",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {"claims": {"type": "array", "items": {"type": "string"}}},
        "required": ["claims"],
        "additionalProperties": False,
    },
}


class ExtractionError(RuntimeError):
    pass


def _get_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ExtractionError("OPENROUTER_API_KEY is not set")
    return AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)


async def extract_claims(text: str) -> list[str]:
    if not text.strip():
        return []

    response = await _get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_schema", "json_schema": CLAIMS_SCHEMA},
        temperature=0,
    )

    content = response.choices[0].message.content
    try:
        claims = json.loads(content)["claims"]
    except (TypeError, ValueError, KeyError) as exc:
        raise ExtractionError(f"Model returned invalid JSON: {content!r}") from exc
    if not isinstance(claims, list) or not all(isinstance(c, str) for c in claims):
        raise ExtractionError(f"Model returned an unexpected shape: {content!r}")
    return [c.strip() for c in claims if c.strip()]
