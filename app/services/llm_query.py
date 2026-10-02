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
                        "stance": {"type": "string", "enum": ["supports", "contradicts", "related", "unrelated"]},
                    },
                    "required": ["number", "text_says", "stance"],
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
    "or ethics; false for anything else, in which case return no verdicts. Otherwise give a verdict for every text: "
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
    "different situation is at most 'related'."
)


async def judge_claim(
    claim: str, excerpts: list[str], api_key: str | None = None
) -> tuple[bool, dict[int, str]]:
    """(is the claim on topic, stance of each text position). The model grades only the texts it is shown."""
    lines = "\n".join(f"{k}. {text[:300]}" for k, text in enumerate(excerpts))
    messages = [
        {"role": "system", "content": STANCE_PROMPT},
        {"role": "user", "content": f"Claim: {claim}\n\n{lines}"},
    ]
    content = await chat_json(messages, STANCE_SCHEMA, api_key)
    try:
        json.loads(content)
    except ValueError:  # truncated or malformed JSON: ask once more
        content = await chat_json(messages, STANCE_SCHEMA, api_key)
    try:
        data = json.loads(content)
        on_topic = bool(data["on_topic"])
        stances = {
            v["number"]: v["stance"]
            for v in data["verdicts"]
            if isinstance(v["number"], int) and 0 <= v["number"] < len(excerpts)
        }
    except (TypeError, ValueError, KeyError) as exc:
        raise ExtractionError(f"Model returned invalid JSON: {content!r}") from exc
    return on_topic, stances
