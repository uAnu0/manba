"""Extract verifiable religious claims from raw text using an LLM via OpenRouter."""
import asyncio
import json
import os
import re
import time

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GOOGLE_BASE_URL = os.getenv("GOOGLE_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "openai/gpt-4o-mini"
GOOGLE_DEFAULT_MODEL = "gemini-3.5-flash-lite"

# A model name may carry its provider: "google:gemini-2.5-flash" (Google's own API, with GEMINI_API_KEY: it has a free
# tier, so tests cost nothing) or "openrouter:openai/gpt-4o-mini". Without a prefix it is an OpenRouter model.
# LLM_PROVIDER (and JUDGE_PROVIDER, EXPLAIN_PROVIDER, EMBED_PROVIDER for one step) picks the default provider.


def provider_for(role: str = "") -> str:
    return (os.getenv(f"{role}_PROVIDER") if role else None) or os.getenv("LLM_PROVIDER") or "openrouter"


def role_default(role: str, openrouter_model: str, google_model: str) -> str:
    """The default model of a step, on the provider chosen for that step."""
    return f"google:{google_model}" if provider_for(role) == "google" else openrouter_model


def split_model(model: str) -> tuple[str, str]:
    for provider in ("google", "openrouter"):
        if model.startswith(provider + ":"):
            return provider, model[len(provider) + 1 :]
    return "openrouter", model


def llm_models() -> list[str]:
    """Chat models to try in order. LLM_MODEL may list several, separated by commas (e.g. free models that are
    often rate-limited): the next one is tried when a model fails."""
    configured = [m.strip() for m in (os.getenv("LLM_MODEL") or "").split(",") if m.strip()]
    return configured or [role_default("LLM", DEFAULT_MODEL, GOOGLE_DEFAULT_MODEL)]

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


# Google's free tier allows only a few requests per minute per model (about 5 for the Flash models, 15 for the Flash-Lite
# ones). Calls to a Google model are spaced to stay under the limit, and a 429 is retried after the wait Google asks for.
# GOOGLE_RPM overrides the limit; set it high on a paid key.
_next_slot: dict[str, float] = {}
_slot_lock = asyncio.Lock()


def _rpm(model: str) -> float:
    configured = os.getenv("GOOGLE_RPM")
    if configured:
        return float(configured)
    return 14.0 if "lite" in model else 4.5


async def _wait_turn(model: str) -> None:
    async with _slot_lock:
        now = time.monotonic()
        slot = max(now, _next_slot.get(model, 0.0))
        _next_slot[model] = slot + 60.0 / _rpm(model)
    if slot > now:
        await asyncio.sleep(slot - now)


def server_has_key() -> bool:
    return bool((os.getenv("OPENROUTER_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip())


def _get_client(api_key: str | None = None, provider: str = "openrouter") -> AsyncOpenAI:
    """`api_key` is a key supplied with the request (OpenRouter only); otherwise the server's shared key is used."""
    # Values pasted into hosting dashboards or piped from a shell often carry a trailing newline.
    if provider == "google":
        key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if not key:
            raise ExtractionError("no Gemini key: set GEMINI_API_KEY on the server")
        return AsyncOpenAI(base_url=GOOGLE_BASE_URL, api_key=key)
    api_key = (api_key or os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        raise ExtractionError("no OpenRouter key: set OPENROUTER_API_KEY on the server or send your own key")
    return AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)


async def chat_json(
    messages: list[dict],
    schema: dict,
    api_key: str | None = None,
    models: list[str] | None = None,
    temperature: float = 0,
    max_tokens: int | None = None,
) -> str:
    """The JSON text of a structured chat completion, trying each model (default: the configured ones) until one answers."""
    error: Exception | None = None
    for entry in models or llm_models():
        provider, model = split_model(entry)
        try:
            client = _get_client(api_key, provider)
            for attempt in range(3):
                if provider == "google":
                    await _wait_turn(model)
                try:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        response_format={"type": "json_schema", "json_schema": schema},
                        temperature=temperature,
                        **({"max_tokens": max_tokens} if max_tokens else {}),
                    )
                    break
                except Exception as exc:
                    wait = re.search(r"retry in ([\d.]+)s", str(exc))
                    if provider == "google" and "429" in str(exc) and wait and attempt < 2:
                        await asyncio.sleep(min(float(wait.group(1)) + 1.0, 70.0))
                        continue
                    raise
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
