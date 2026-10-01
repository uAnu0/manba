"""Text-level verification: split into sentences, then verify each one."""
from app.schemas import Segment, VerifyResponse
from app.services.quote_finder import locate_quotes
from app.services.verifier import split_segments, verify_segment

# Up to this many words, a sentence that resembles a verse is checked as a whole: it is most likely a single
# quote, and an altered or partly invented one must be reported as such. Longer sentences are sermon-style
# prose with quotes inside, so the quotes are located first.
SENTENCE_REFINE_MIN_WORDS = 12


def verify_sentence(sentence: str) -> list[Segment]:
    whole = verify_segment(sentence)
    if whole.status == "verified":
        return [whole]
    long_sentence = len(sentence.split()) > SENTENCE_REFINE_MIN_WORDS
    # A short sentence that resembles a verse (variant) is kept whole so that its alteration is reported;
    # one that resembles nothing may still contain a verbatim quote among commentary.
    if long_sentence or whole.status == "baseless":
        return locate_quotes(sentence) or [whole]
    return [whole]


def verify_text(text: str) -> VerifyResponse:
    segments = [seg for sentence in split_segments(text) for seg in verify_sentence(sentence)]
    return VerifyResponse(original_text=text, word_count=len(text.split()), segments=segments)
