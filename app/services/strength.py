"""How much weight a source carries: the deck's levels and a plain strength label.

Level 1: the Quran. Level 2: Sahih al-Bukhari and Sahih Muslim. Level 3: every other hadith, shown with the gradings
scholars gave it (we report them, we do not grade). Level 4 is a text with no source (set by the verifier).
Strength is a label for display and for deciding how firmly a claim is supported; it is not a ruling.
"""
SAHIHAYN = frozenset({"صحيح البخاري", "صحيح مسلم"})
STRONG = frozenset({"quran", "sahihayn", "sahih", "hasan"})

_WEAK_WORDS = ("daif", "da'if", "weak", "mawdu", "munkar", "fabricated", "batil")


def level_of(classification: str, book: str) -> int | None:
    if classification == "quran":
        return 1
    if classification == "hadith":
        return 2 if book in SAHIHAYN else 3
    return None


def strength_of(classification: str, book: str, grades: tuple[tuple[str, str], ...] | list = ()) -> str | None:
    """quran | sahihayn | sahih | hasan | daif | disputed (scholars disagree) | ungraded."""
    if classification == "quran":
        return "quran"
    if classification != "hadith":
        return None
    if book in SAHIHAYN:
        return "sahihayn"
    categories = set()
    for _, grade in grades:
        g = grade.lower()
        if "sahih" in g:
            categories.add("sahih")
        elif "hasan" in g:
            categories.add("hasan")
        elif any(w in g for w in _WEAK_WORDS):
            categories.add("daif")
    if "daif" in categories and categories & {"sahih", "hasan"}:
        return "disputed"  # scholars disagree: never shown as a plain sahih or hasan
    for label in ("sahih", "hasan", "daif"):
        if label in categories:
            return label
    return "ungraded"
