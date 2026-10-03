"""Let an LLM recall which Quran verses and hadith bear on a question; the corpus then checks every one of them.

Keyword search alone cannot bridge the gap between how a question is phrased and how the texts are worded
("الرشوة" vs "الراشي والمرتشي", "الانتحار" vs "من قتل نفسه"). A language model knows the well-known evidences, so it is
asked to *recite* them in Arabic. Its recitations are never shown: each is looked up in the local corpus, and only the
corpus text (with its real source and gradings) reaches the user. Whatever cannot be found there is discarded and
reported as rejected. The model neither answers the question nor produces a ruling.
"""
import asyncio
import json
import os

from app.services.cache import async_cache
from app.services.llm_extractor import ExtractionError, chat_json, llm_models, role_default

# Judging is output-bound (a verdict per text), so texts can be judged in small chunks in parallel: the wait is that of
# one small call. Measured on the golden sets: for the claim judge (stance of each text) chunks of 10 changed nothing
# (claims 28/30, no reversals), for the evidence card's relevance judge they cost about 5 points of recall
# (64% against 69% of the expected texts), so that one still judges all the candidates in one call.
JUDGE_CHUNK = int(os.getenv("JUDGE_CHUNK", "30"))  # evidence card: relevance of each text
# The model that decides whether a text supports a claim. It is the step where a lenient model does the most harm
# (it called a general verse on dawn prayer "direct support" for a claim with extra conditions), so it has its own
# setting; benchmarked 28/30 on the overreach cases against 23/30 for gpt-4o-mini (claude-haiku-4.5 scored 30/30 but costs several times more). JUDGE_MODEL may list fallbacks.
DEFAULT_JUDGE_MODEL = "google/gemini-2.5-flash"


def judge_models() -> list[str]:
    configured = [m.strip() for m in (os.getenv("JUDGE_MODEL") or "").split(",") if m.strip()]
    return (configured or [role_default("JUDGE", DEFAULT_JUDGE_MODEL, "gemini-3.1-flash-lite")]) + [m for m in llm_models() if m not in configured]


CLAIM_JUDGE_CHUNK = int(os.getenv("CLAIM_JUDGE_CHUNK", "10"))  # claim check: stance of each text

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


_ONLY = {
    "verses": " For this request list ONLY Quran verses (leave hadiths empty).",
    "hadiths": " For this request list ONLY hadith (leave verses empty).",
}


async def _recite(question: str, only: str, api_key: str | None) -> list[str]:
    content = await chat_json(
        [{"role": "system", "content": SYSTEM_PROMPT + _ONLY[only]}, {"role": "user", "content": question}],
        SUGGESTIONS_SCHEMA,
        api_key,
    )
    try:
        texts = list(json.loads(content)[only])
    except (TypeError, ValueError, KeyError) as exc:
        raise ExtractionError(f"Model returned invalid JSON: {content!r}") from exc
    if not all(isinstance(t, str) for t in texts):
        raise ExtractionError(f"Model returned an unexpected shape: {content!r}")
    return [t.strip() for t in texts if t.strip()]


@async_cache()
async def suggest_evidence(question: str, api_key: str | None = None) -> list[str]:
    """The model's recitations (verses first, then hadith). Unverified: callers must check them against the corpus.

    Verses and hadith are requested in two parallel calls, so the wait is that of the shorter list."""
    verses, hadiths = await asyncio.gather(_recite(question, "verses", api_key), _recite(question, "hadiths", api_key))
    return (verses + hadiths)[:16]


JUDGE_SCHEMA = {
    "name": "judgments",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "on_topic": {"type": "boolean"},
            "claim_parts": {"type": "array", "items": {"type": "string"}},
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
        "required": ["on_topic", "claim_parts", "verdicts"],
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


@async_cache()
async def _judge_chunk(question: str, excerpts: list[str], api_key: str | None = None) -> tuple[bool, dict[int, str]]:
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


async def _twice(call):
    """Run a model call; if it fails (a rate limit, a truncated answer) try once more before giving up."""
    try:
        return await call()
    except Exception:
        return await call()


async def judge(question: str, excerpts: list[str], api_key: str | None = None) -> tuple[bool, dict[int, str]]:
    """Grade every text (direct / related / unrelated), in parallel chunks of JUDGE_CHUNK."""
    chunks = [excerpts[k : k + JUDGE_CHUNK] for k in range(0, len(excerpts), JUDGE_CHUNK)] or [[]]
    results = await asyncio.gather(
        *(_twice(lambda chunk=chunk: _judge_chunk(question, chunk, api_key=api_key)) for chunk in chunks)
    )
    verdicts = {k * JUDGE_CHUNK + n: v for k, (_, part) in enumerate(results) for n, v in part.items()}
    return any(on_topic for on_topic, _ in results), verdicts


# ---- claim verification -------------------------------------------------------------------------------------------

INTENT_SCHEMA = {
    "name": "claim_intent",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "claim_type": {"type": "string", "enum": ["quote", "topic", "personal", "not_religious"]},
            "claim_ar": {"type": "string"},
            "opposite_ar": {"type": "string"},
            "key_terms_ar": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["claim_type", "claim_ar", "opposite_ar", "key_terms_ar"],
        "additionalProperties": False,
    },
}
INTENT_PROMPT = (
    "You route claims for a tool that checks religious claims against the Quran and hadith. The user's text is in any "
    "language. Decide claim_type: "
    "'quote' = the text is, or presents itself as, a Quran verse or hadith, or attributes words to God or the "
    "Prophet (for example 'قال النبي ...', 'God says ...'); "
    "'topic' = a statement about what Islam, the Quran or the hadith says, allows, forbids, recommends or teaches "
    "(for example 'Islam forbids X', 'X is haram', 'the Prophet used to do X'); "
    "'personal' = a RELIGIOUS question about the user's own situation or one that asks for a personal ruling "
    "('can I ...', 'my husband ...'); "
    "'not_religious' = anything that is not about religion, even if it is phrased personally (cooking, weather, "
    "general facts). "
    "claim_ar: for 'topic' restate the claim as ONE short Arabic statement in the words the Quran and hadith would "
    "use. It MUST keep exactly the meaning and direction of the claim: if the claim says something is permitted, "
    "the restatement says it is permitted; never turn a claim into its opposite or into the more common view. "
    "For 'quote' copy the quoted text; otherwise an empty string. "
    "opposite_ar: for 'topic' the opposite claim in Arabic (if the claim says X is forbidden, say X is permitted), used "
    "to look for counter-evidence; otherwise an empty string. "
    "key_terms_ar: for 'topic', 2 to 5 Arabic words that name the SPECIFIC act or subject of the claim (not the ruling "
    "words such as حرام or يبيح, and not generic categories such as الطعام or الأعمال), in the forms and synonyms the "
    "Quran and hadith use; for example for 'Islam forbids interest': الربا ربا; for 'Islam allows eating tomatoes': "
    "الطماطم البندورة; otherwise an empty list. Do not judge whether the claim is true."
)


@async_cache()
async def classify_claim(claim: str, api_key: str | None = None) -> dict:
    content = await chat_json(
        [{"role": "system", "content": INTENT_PROMPT}, {"role": "user", "content": claim}], INTENT_SCHEMA, api_key
    )
    try:
        data = json.loads(content)
        return {
            "claim_type": data["claim_type"],
            "claim_ar": str(data["claim_ar"]).strip(),
            "opposite_ar": str(data["opposite_ar"]).strip(),
            "key_terms_ar": [str(t).strip() for t in data["key_terms_ar"] if str(t).strip()],
        }
    except (TypeError, ValueError, KeyError) as exc:
        raise ExtractionError(f"Model returned invalid JSON: {content!r}") from exc


STANCE_SCHEMA = {
    "name": "stances",
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
                        "text_says": {"type": "string"},
                        "covers_all": {"type": "boolean"},
                        "covered_parts": {"type": "array", "items": {"type": "string"}},
                        "stance": {"type": "string", "enum": ["supports", "contradicts", "related", "unrelated"]},
                    },
                    "required": ["number", "text_says", "covers_all", "covered_parts", "stance"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["on_topic", "verdicts"],
        "additionalProperties": False,
    },
}
STANCE_PROMPT = (
    "You judge evidence for a claim in a tool that checks religious claims against the Quran and hadith. Below is a "
    "claim and numbered Quran verses or hadith texts retrieved from a library. Do NOT decide whether the claim is true "
    "and do not write any evidence. First on_topic: true only if the claim is about Islam, Islamic law, belief, worship "
    "or ethics; false for anything else, in which case return no verdicts. Otherwise first list claim_parts: the separate "
    "things the claim asserts (its subject, the act or ruling, and every added condition such as a time, a place, a "
    "reason or a result), each in a few words. Then give a verdict for every text: "
    "'supports' = the text says, or clearly implies, what the claim says; "
    "'contradicts' = the text says, or clearly implies, the opposite of the claim; "
    "'related' = same subject but it does not settle the claim; "
    "'unrelated' = nothing to do with the claim. "
    "For every text first write text_says: in at most 12 words, what the text itself says (its subject and its "
    "ruling or message), then give the stance by comparing text_says with the claim's subject AND its direction. "
    "Mind the direction: a text that commands, praises or forbids the OPPOSITE of what the claim says 'contradicts' it. "
    "For example, for the claim 'Islam commands disobeying parents', a text that commands honouring parents "
    "'contradicts'; for 'Islam forbids interest', a text that curses the one who takes interest 'supports'. "
    "A text that merely shares a word with the claim is 'unrelated', and a text about a different ruling or a "
    "different situation is at most 'related'. "
    "When the claim says Islam allows, permits or commands an act, a text that forbids or condemns that same act "
    "(for example a verse forbidding killing a soul wrongfully, for 'Islam allows killing innocent people', or a verse "
    "forbidding taking wealth unlawfully by bribing judges, for 'Islam allows bribery') 'contradicts' it, even when the "
    "prohibition is stated in general terms. But a text that gives a different answer to the same kind of question "
    "('who is the best believer', 'which deed is most beloved') does not contradict the claim: it is 'related'. "
    "Also set covers_all: true only if the text itself addresses EVERY part in claim_parts, including each added "
    "condition. A text that supports only some parts (for example it recommends the act in general but says nothing "
    "about the time, the reason or the result the claim adds) has covers_all false and is never 'supports'. For a "
    "'contradicts' verdict covers_all is true only if the text itself addresses the claim's main assertion (a general "
    "principle such as 'every soul is recompensed' does not address a specific claim about orphans). For every "
    "text also list covered_parts: the entries of claim_parts, copied exactly, that the text itself addresses in the "
    "claim's direction (an empty list if none). The claim is judged as the person worded it: do not widen it to match the text."
)


@async_cache()
async def _judge_claim_chunk(
    claim: str, excerpts: list[str], api_key: str | None = None
) -> tuple[bool, dict[int, str], dict[int, str], dict[int, list[str]]]:
    """(is the claim on topic, stance of each text position, the model's note on what each text says, the claim parts a
    partly supporting text addresses). The model grades only the texts it is shown."""
    lines = "\n".join(f"{k}. {text[:300]}" for k, text in enumerate(excerpts))
    messages = [
        {"role": "system", "content": STANCE_PROMPT},
        {"role": "user", "content": f"Claim: {claim}\n\n{lines}"},
    ]
    models = judge_models()
    content = await chat_json(messages, STANCE_SCHEMA, api_key, models=models, temperature=0.0, max_tokens=2500)
    try:
        json.loads(content)
    except ValueError:  # truncated or malformed JSON: ask once more
        content = await chat_json(messages, STANCE_SCHEMA, api_key, models=models, temperature=0.0, max_tokens=2500)
    try:
        data = json.loads(content)
        on_topic = bool(data["on_topic"])
        valid = [v for v in data["verdicts"] if isinstance(v["number"], int) and 0 <= v["number"] < len(excerpts)]
        # A text counts as support only if the model says it covers every part of the claim: the code enforces this.
        def covered(v) -> list[str]:  # the model's own short notes on the parts a text addresses (shown as such, never evidence)
            notes = [str(p).strip()[:140] for p in (v.get("covered_parts") or []) if isinstance(p, str) and str(p).strip()]
            return list(dict.fromkeys(notes))[:4]

        def stance_of(v) -> str:
            if v["stance"] == "supports" and v.get("covers_all") is not True:
                return "partial" if covered(v) else "related"
            if v["stance"] == "contradicts" and v.get("covers_all") is not True:
                return "contradicts_part"  # the code decides below whether the text is about the claim's subject at all
            return v["stance"]

        stances = {v["number"]: stance_of(v) for v in valid}
        says = {v["number"]: str(v.get("text_says", "")).strip() for v in valid}
        covers = {v["number"]: covered(v) for v in valid if stances[v["number"]] == "partial"}
    except (TypeError, ValueError, KeyError) as exc:
        raise ExtractionError(f"Model returned invalid JSON: {content!r}") from exc
    return on_topic, stances, says, covers


async def judge_claim(
    claim: str, excerpts: list[str], api_key: str | None = None
) -> tuple[bool, dict[int, str], dict[int, str], dict[int, list[str]]]:
    """Grade every text against the claim (supports / contradicts / related / unrelated), in parallel chunks.
    Returns (on topic, stance per position, the model's one-line note per position)."""
    chunks = [excerpts[k : k + CLAIM_JUDGE_CHUNK] for k in range(0, len(excerpts), CLAIM_JUDGE_CHUNK)] or [[]]
    results = await asyncio.gather(
        *(_twice(lambda chunk=chunk: _judge_claim_chunk(claim, chunk, api_key=api_key)) for chunk in chunks)
    )
    stances = {k * CLAIM_JUDGE_CHUNK + n: v for k, (_, part, _, _) in enumerate(results) for n, v in part.items()}
    says = {k * CLAIM_JUDGE_CHUNK + n: v for k, (_, _, part, _) in enumerate(results) for n, v in part.items()}
    covers = {k * CLAIM_JUDGE_CHUNK + n: v for k, (_, _, _, part) in enumerate(results) for n, v in part.items()}
    return any(r[0] for r in results), stances, says, covers


# ---- finding the claims in a longer text --------------------------------------------------------------------------

TRIAGE_SCHEMA = {
    "name": "claims_in_text",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "sentence": {"type": "integer"},
                        "text": {"type": "string"},
                        "subject": {"type": "string"},
                    },
                    "required": ["sentence", "text", "subject"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["claims"],
        "additionalProperties": False,
    },
}
TRIAGE_PROMPT = (
    "You read a sermon or social-media text split into numbered sentences. Find the sentences that make a checkable "
    "RELIGIOUS CLAIM: a statement about what Islam, the Quran, the hadith or the Prophet says, allows, forbids, "
    "commands, recommends or teaches, or a statement that something is or is not a verse or a hadith. Skip commentary, "
    "greetings, prayers, personal stories, general advice, questions, and every sentence marked [QUOTE] (quotes are "
    "checked elsewhere). For each claim return the sentence number and the claim text copied EXACTLY from that "
    "sentence. When a sentence holds several claims, return ONE ITEM PER CLAIM, each copied exactly, even if the piece is "
    "not a full sentence. If a piece does not name what it is about (for example 'ويأمر بالصدقة'), put in subject the "
    "words from the same sentence that name it (for example 'الإسلام'), copied exactly; otherwise subject is an empty "
    "string. Do not rewrite, translate or complete anything. If there are no claims return an empty list."
)


@async_cache()
async def find_claims(
    sentences: list[str], quote_flags: list[bool], api_key: str | None = None
) -> list[tuple[int, str, str]]:
    """(sentence number, claim text, subject) for the claims in numbered sentences. The caller must check that each claim text
    really occurs in its sentence: the model is told to copy, and nothing it writes is trusted."""
    lines = "\n".join(
        f"{k}. {'[QUOTE] ' if quote else ''}{text[:400]}" for k, (text, quote) in enumerate(zip(sentences, quote_flags))
    )
    content = await chat_json(
        [{"role": "system", "content": TRIAGE_PROMPT}, {"role": "user", "content": lines}], TRIAGE_SCHEMA, api_key
    )
    try:
        data = json.loads(content)
        return [
            (c["sentence"], str(c["text"]).strip(), str(c["subject"]).strip())
            for c in data["claims"]
            if isinstance(c["sentence"], int) and 0 <= c["sentence"] < len(sentences) and str(c["text"]).strip()
        ]
    except (TypeError, ValueError, KeyError) as exc:
        raise ExtractionError(f"Model returned invalid JSON: {content!r}") from exc
