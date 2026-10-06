"""A serial read from a picture can have look-alike characters wrong; recover() puts them right only when the signature then accepts the serial."""
import hashlib
import hmac

import pytest

from app.services import badge as B


@pytest.fixture(autouse=True)
def signing(monkeypatch):
    monkeypatch.setenv("BADGE_SECRET", "x" * 40)


def issued(text="النص المراجع", days=77):
    payload = (days | 0x8000).to_bytes(2, "big") + B.fingerprint(text)
    mac = hmac.new(B._key(), b"v2" + payload, hashlib.sha256).digest()[:16]
    return B._encode(payload + mac)


def swap(code, positions):
    chars = list(code)
    for i in positions:
        chars[i] = B.CONFUSABLE[chars[i]]
    return "".join(chars)


def spots(code):
    return [i for i, ch in enumerate(code) if i >= 5 and ch in B.CONFUSABLE]


def test_a_correct_serial_is_returned_as_it_is():
    code = issued()
    assert B.recover(code).code == code


@pytest.mark.parametrize("n", [1, 2, 3])
def test_up_to_three_look_alike_mistakes_are_put_right(n):
    code = issued()
    wrong = swap(code, spots(code)[:n])
    assert wrong != code and B.verify(wrong).valid is False
    assert B.recover(wrong).code == code


def test_four_mistakes_are_not_guessed():
    code = issued()
    assert B.recover(swap(code, spots(code)[:4])) is None


def test_a_mistake_that_is_not_a_look_alike_is_not_fixed():
    code = issued()
    i = next(i for i in range(5, len(code)) if code[i] in "ABCDEFH" and code[i] != "-")
    wrong = code[:i] + ("M" if code[i] != "M" else "N") + code[i + 1:]
    assert B.recover(wrong) is None


def test_it_cannot_turn_a_serial_that_was_never_issued_into_a_valid_one():
    fake = "MNB2-" + "-".join(["SSSS"] * 13) + "-SSS"
    assert B.recover(fake) is None


def test_without_a_signing_key_nothing_is_checked(monkeypatch):
    monkeypatch.delenv("BADGE_SECRET")
    assert B.recover("MNB2-" + "-".join(["AAAA"] * 13) + "-AAA") is None
