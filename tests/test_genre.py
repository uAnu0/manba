"""The kind of text is read from its own conventions: a vowelled sermon is a sermon just like an unvowelled one."""
import re

from app.services.genre import content_type

PLAIN_SERMON = ("الحمد لله الذي جعل الذكر طمأنينة للقلوب، وأشهد أن لا إله إلا الله وحده لا شريك له، وأشهد أن محمدا عبده ورسوله.\n"
                "أما بعد، معاشر المؤمنين: فاتقوا الله في السر والعلن، وتمسكوا بحبل الله المتين.")
VOWELLED_SERMON = ("الْحَمْدُ لِلَّهِ الَّذِي جَعَلَ الذِّكْرَ طُمَأْنِينَةً لِلْقُلُوبِ، وَأَشْهَدُ أَنْ لَا إِلَهَ إِلَّا اللَّهُ وَحْدَهُ لَا شَرِيكَ لَهُ، وَأَشْهَدُ أَنَّ مُحَمَّدًا عَبْدُهُ وَرَسُولُهُ.\n"
                   "أَمَّا بَعْدُ، مَعَاشِرَ الْمُؤْمِنِينَ: فَاتَّقُوا اللَّهَ فِي السِّرِّ وَالْعَلَنِ، وَتَمَسَّكُوا بِحَبْلِ اللَّهِ الْمَتِينِ.")


def test_a_plain_sermon_is_a_sermon():
    assert content_type(PLAIN_SERMON)[0] == "khutbah"


def test_a_fully_vowelled_sermon_is_a_sermon_too():
    kind, cues = content_type(VOWELLED_SERMON)
    assert kind == "khutbah" and cues


def test_the_cues_shown_are_bare_words_without_vowel_marks():
    _, cues = content_type(VOWELLED_SERMON)
    assert all(not re.search("[\u064B-\u0652]", c) for c in cues)


def test_a_post_a_question_and_a_plain_text_keep_their_kinds():
    assert content_type("انشرها تؤجر ولا تجعلها تقف عندك #خير")[0] == "post"
    assert content_type("هل يجوز الجمع بين الصلاتين في السفر؟")[0] == "question"
    assert content_type("العلم نور والجهل ظلام.")[0] == "text"


def test_a_vowelled_question_is_still_a_question():
    assert content_type("هَلْ يَجُوزُ الْجَمْعُ بَيْنَ الصَّلَاتَيْنِ فِي السَّفَرِ؟")[0] == "question"
