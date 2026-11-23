"""Shared input rules for every request model. Field types here clean the value first (Unicode NFC, control
characters out, whitespace tidied), then check length, then check it looks like real data for that kind of field.

    from core.validation import PersonName, Place, Text, Email, Search
    class Thing(Strict):
        full_name: PersonName          # 1..120, letters in any script, . ' - ( )
        native_place: Place(120)       # letters required, digits allowed
        title: Text(200)               # one line, 1..200, must say something
        body: Text(10_000, multiline=True)

Strict forbids properties the model doesn't declare. Rules are mirrored for instant feedback in
web-frontend/src/shared/validate.js and app-frontend/src/lib/validate.ts; the backend is the one that counts.
docs/input-validation-rules.md lists every rule."""
import re
import unicodedata
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, StringConstraints

# Bidi overrides can make "abc.exe" display as "exe.cba" (spoofing); they are never needed in names or text.
# ZWJ / ZWNJ (U+200C/D) are NOT removed: Gujarati and Hindi need them to shape conjuncts.
_BIDI = dict.fromkeys(map(ord, "‪‫‬‭‮⁦⁧⁨⁩"))
_SPACES = re.compile(r"[^\S\n]+")  # any whitespace except newline
_BLANK_LINES = re.compile(r"\n{3,}")
_KEYBOARD = ("qwertyuiop", "asdfghjkl", "zxcvbnm", "abcdefghijklmnopqrstuvwxyz", "1234567890")
_PLACEHOLDERS = {"test", "testing", "tester", "asdf", "qwerty", "dummy", "sample", "fake", "name", "fullname",
                 "firstname", "lastname", "na", "none", "null", "undefined", "unknown", "abc", "xyz", "xxx",
                 "noname"}
_NAME_PUNCT = set(" .'’-()")


def clean(value, multiline: bool = False):
    """NFC, no control characters, trimmed; one line: whitespace runs -> one space; multiline: tidy lines and at
    most one blank line in a row. Non-strings pass through so the type check reports them."""
    if not isinstance(value, str):
        return value
    v = unicodedata.normalize("NFC", value).translate(_BIDI).replace("\r\n", "\n").replace("\r", "\n")
    v = "".join(ch for ch in v if ch in "\n\t" or unicodedata.category(ch) != "Cc")
    if not multiline:
        return " ".join(v.split())
    v = "\n".join(_SPACES.sub(" ", line).strip() for line in v.split("\n"))
    return _BLANK_LINES.sub("\n\n", v).strip()


def _letters(v: str) -> str:
    return "".join(ch for ch in v if ch.isalpha())


_RUN4 = re.compile(r"(.)\1{3}")  # one character 4+ times in a row; linear, and inputs are length-capped first


def _repeats(v: str) -> bool:
    return bool(_RUN4.search(v))


def _mash(word: str) -> bool:
    """A run straight along the keyboard or alphabet: "asdf", "qwerty", "abcd", "123456"."""
    w = word.casefold()
    return len(w) >= 4 and any(w in row or w in row[::-1] for row in _KEYBOARD)


def meaningful(v: str) -> str:
    """Free text: has a letter or digit, and isn't one character over and over ("!!!!!", "aaaaaaa")."""
    if not any(ch.isalnum() for ch in v):
        raise ValueError("Enter some text, not only symbols")
    compact = v.replace(" ", "").replace("\n", "")
    if len(compact) >= 5 and len(set(compact.casefold())) == 1:
        raise ValueError("This doesn't look like real text")
    return v


def person_name(v: str) -> str:
    """Letters of any script (with their vowel signs), spaces and . ' ’ - ( ). No digits, no symbols."""
    for ch in v:
        if not (ch in _NAME_PUNCT or unicodedata.category(ch)[0] in "LM" or ch in "‌‍"):
            raise ValueError("Use letters only in a name")
    letters = _letters(v)
    if not letters:
        raise ValueError("Enter a name with letters")
    if _repeats(v.casefold()) or (len(letters) >= 3 and len(set(letters.casefold())) == 1):
        raise ValueError("This doesn't look like a real name")
    if letters.casefold() in _PLACEHOLDERS or any(_mash(w) for w in re.split(r"[\s.'’()-]+", v)):
        raise ValueError("Enter a real name")
    return v


def place(v: str) -> str:
    """Cities, states, villages: letters required; digits and everyday punctuation allowed ("Sector 21")."""
    if not _letters(v):
        raise ValueError("Enter a place name with letters")
    if _repeats(v.casefold()) or _letters(v).casefold() in _PLACEHOLDERS - {"na"} or _mash(_letters(v)):
        raise ValueError("Enter a real place name")
    return v


_EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
                    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}$")


def email(v: str) -> str:
    v = v.strip()
    local, _, domain = v.rpartition("@")
    if not _EMAIL.match(v) or ".." in local or local.startswith(".") or local.endswith(".") or len(local) > 64:
        raise ValueError("Enter a valid email address")
    return f"{local}@{domain.lower()}"  # domains are case-insensitive; the local part is the owner's


def _str(max_length: int, min_length: int, multiline: bool, *rules):
    return Annotated[(str, BeforeValidator(lambda v: clean(v, multiline)),  # tuple form: py3.10 has no * in []
                      StringConstraints(min_length=min_length, max_length=max_length),
                      *(AfterValidator(r) for r in rules))]


def Text(max_length: int, min_length: int = 1, multiline: bool = False):  # noqa: N802 (a type factory)
    """Titles, notes, reasons, descriptions. Keeps every character people type, < and & included:
    output is escaped where it's shown (React / React Native), never stripped here."""
    return _str(max_length, min_length, multiline, meaningful)


def Search(max_length: int = 120, min_length: int = 1):  # noqa: N802
    """Search boxes: cleaned only. Matched as data (bound parameters / ES query), never as syntax."""
    return _str(max_length, min_length, False)


def Place(max_length: int = 120):  # noqa: N802
    return _str(max_length, 1, False, place)


PersonName = _str(120, 1, False, person_name)
Email = Annotated[str, BeforeValidator(lambda v: clean(v)), StringConstraints(max_length=254), AfterValidator(email)]


class Strict(BaseModel):
    """Base for request bodies: an undeclared property is a 422, not silently dropped (mass assignment)."""
    model_config = ConfigDict(extra="forbid")


if __name__ == "__main__":  # self-check, from backend/: python -m core.validation
    assert clean("  Asha ‮  Patel\x00 ") == "Asha Patel"
    assert clean("a\r\n\r\n\r\n\r\nb  c ", multiline=True) == "a\n\nb c"
    assert clean("ક્‍ષ") == "ક્‍ષ"  # ZWJ kept
    for ok in ("Asha Patel", "D'Souza", "Asha P. Shah", "આશાબેન પટેલ", "राम-लाल", "M", "Om", "O’Neil", "Bharat (Late)"):
        assert person_name(ok) == ok, ok
    for bad in ("asdfghjkl", "!!!!", "1111111111", "Raaaaam", "aaa", "test", "N.A.", "Ram2", "<b>x</b>", "Qwerty Patel"):
        try:
            person_name(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    assert place("Sector 21") == "Sector 21"
    assert email(" Asha.P@Example.COM") == "Asha.P@example.com"
    for bad in ("a@b", "a..b@x.com", ".a@x.com", "a@-x.com", "a b@x.com"):
        try:
            email(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    assert meaningful("No") == "No" and meaningful("a < b & c") == "a < b & c"
    for bad in ("!!!!!!!!!", "....", "aaaaaaa"):
        try:
            meaningful(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    print("ok")
