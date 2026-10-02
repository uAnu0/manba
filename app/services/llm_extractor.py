"""Extract verifiable religious claims from raw text using an LLM via OpenRouter."""
import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4o-mini"


def llm_models() -> list[str]:
    """Chat models to try in order. LLM_MODEL may list several, separated by commas (e.g. free models that are
    often rate-limited): the next one is tried when a model fails."""
    configured = [m.strip() for m in (os.getenv("LLM_MODEL") or "").split(",") if m.strip()]
    return configured or [DEFAULT_MODEL]

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


def server_has_key() -> bool:
    return bool((os.getenv("OPENROUTER_API_KEY") or "").strip())


def _get_client(api_key: str | None = None) -> AsyncOpenAI:
    """`api_key` is a key supplied with the request; otherwise the server's shared OPENROUTER_API_KEY is used."""
    # Values pasted into hosting dashboards or piped from a shell often carry a trailing newline.
    api_key = (api_key or os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        raise ExtractionError("no OpenRouter key: set OPENROUTER_API_KEY on the server or send your own key")
    return AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)


async def chat_json(messages: list[dict], schema: dict, api_key: str | None = None) -> str:
    """The JSON text of a structured chat completion, trying each configured model until one answers."""
    client = _get_client(api_key)
    error: Exception | None = None
    for model in llm_models():
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_schema", "json_schema": schema},
                temperature=0,
            )
            content = response.choices[0].message.content
            if content:
                return content
            error = ExtractionError(f"{model} returned an empty answer")
        except Exception as exc:  # rate limit, model unavailable, unsupported parameter ...
            error = exc
    raise error or ExtractionError("no chat model configured")


async def extract_claims(text: str, api_key: str | None = None) -> list[str]:
    if not text.strip():
        return []

    content = await chat_json(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}], CLAIMS_SCHEMA, api_key
    )
    try:
        claims = json.loads(content)["claims"]
    except (TypeError, ValueError, KeyError) as exc:
        raise ExtractionError(f"Model returned invalid JSON: {content!r}") from exc
    if not isinstance(claims, list) or not all(isinstance(c, str) for c in claims):
        raise ExtractionError(f"Model returned an unexpected shape: {content!r}")
    return [c.strip() for c in claims if c.strip()]
