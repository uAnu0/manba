"""Read the text of a scanned page with two independent model readings, and say where they disagree.

A verification tool cannot afford an OCR step that "improves" the text: a misquoted verse read back as the real one would hide the very
thing we look for. So the model is told to copy what is printed, and a SECOND, different model reads the same page. Words on which the two
readings differ (typically a word one of them filled in from memory) are returned so the person can check them against the page before
the text is verified. The first reading is the text that is used; nothing is stored, and no cache is kept (the images are large).
In tests the first reader copied altered quotes exactly and the second one once added words ("عز وجل") that were not on the page, which
this comparison flags.
"""
import asyncio
import base64
import difflib
import json
import re

from app.schemas import OcrDiff, OcrResponse
from app.services.llm_extractor import chat_json, role_default
from app.services.verifier import normalize

MAX_IMAGE_BYTES = 3_000_000  # a page image after the browser has shrunk it; the host's request limit is about 4.5 MB
DATA_URL = re.compile(r"^data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\s]+)$")

SCHEMA = {
    "name": "transcription",
    "strict": True,
    "schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False},
}
PROMPT = (
    "Transcribe the text in this image exactly as it is written, character by character, keeping the diacritics you can see and the "
    "line breaks of paragraphs. Do NOT correct, complete, normalise or fix any word, even when the text looks like a known verse or "
    "hadith and a word seems wrong or missing: copy what is printed. If a word is unclear, write what you see. Do not translate and do "
    "not add anything of your own. Return JSON {\"text\": ...}."
)


def reader_models() -> tuple[str, str]:
    """(first reading, second reading): two different models, on the provider the person chose."""
    return (
        role_default("OCR", "google/gemini-3.1-flash-lite", "gemini-3.1-flash-lite"),
        role_default("OCR", "google/gemini-3.5-flash-lite", "gemini-3.5-flash-lite"),
    )


def check_image(data_url: str) -> str:
    """The image as a base64 data URL if it is a small enough PNG, JPEG or WebP; ValueError otherwise."""
    m = DATA_URL.match(data_url or "")
    if not m:
        raise ValueError("send the page as a PNG, JPEG or WebP data URL")
    if len(m.group(2)) * 3 // 4 > MAX_IMAGE_BYTES:
        raise ValueError("the page image is too large: it must be under 3 MB (the page shrinks it before sending)")
    base64.b64decode(re.sub(r"\s", "", m.group(2)), validate=True)  # refuses a damaged payload
    return data_url


async def _read(model: str, data_url: str) -> str:
    messages = [{"role": "user", "content": [{"type": "text", "text": PROMPT}, {"type": "image_url", "image_url": {"url": data_url}}]}]
    content = await chat_json(messages, SCHEMA, None, models=[model], temperature=0, max_tokens=4000)
    return str(json.loads(content).get("text", "")).strip()


def _tokens(text: str) -> tuple[list[str], list[str]]:
    """(the words as written, their comparison form without vowel marks and with unified letters); punctuation alone is dropped."""
    raw, norm = [], []
    for word in text.split():
        n = normalize(word)
        if n:
            raw.append(word)
            norm.append(n)
    return raw, norm


def compare(a: str, b: str) -> list[OcrDiff]:
    """Where reading B differs from reading A, in words of A. Vowel marks and letter variants do not count as differences."""
    raw_a, norm_a = _tokens(a)
    raw_b, norm_b = _tokens(b)
    diffs = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, norm_a, norm_b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        diffs.append(
            OcrDiff(
                before=" ".join(raw_a[max(0, i1 - 3) : i1]),
                a=" ".join(raw_a[i1:i2]),
                b=" ".join(raw_b[j1:j2]),
                after=" ".join(raw_a[i2 : i2 + 3]),
            )
        )
    return diffs


async def read_page(data_url: str, page: int = 1) -> OcrResponse:
    first, second = reader_models()
    results = await asyncio.gather(_read(first, data_url), _read(second, data_url), return_exceptions=True)
    a, b = results
    if isinstance(a, Exception):
        raise a
    note = None
    diffs: list[OcrDiff] = []
    text_b = None
    if isinstance(b, Exception):
        note = "The second reading was not available, so nothing could be cross-checked: check the text against the page."
    else:
        text_b = b
        diffs = compare(a, b)
    return OcrResponse(page=page, text=a, text_b=text_b, diffs=diffs, words=len(a.split()), model_a=first.split(":")[-1], model_b=second.split(":")[-1], note=note)
