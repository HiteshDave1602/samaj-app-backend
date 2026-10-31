import re

from core.translit_words import SUFFIXES, WORDS

# Names typed in English letters -> Devanagari: known words from translit_words.WORDS, the rest, then Gujarati by shifting code points: the two Unicode blocks are
# laid out in parallel (क U+0915 -> ક U+0A95). Rule-based, so some spellings come out wrong ("vapi" -> वपी);
# members correct theirs and the correction is stored next to the auto value.
# ponytail: hand rules tuned for Indian names; swap for an ML transliterator (AI4Bharat IndicXlit) if corrections pile up.
CONS = {
    "chh": "छ", "ksh": "क्ष",
    "kh": "ख", "gh": "घ", "ch": "च", "jh": "झ", "th": "थ", "dh": "ध", "ph": "फ", "bh": "भ", "sh": "श",
    "k": "क", "g": "ग", "c": "क", "j": "ज", "t": "त", "d": "द", "n": "न", "p": "प", "f": "फ", "b": "ब", "m": "म",
    "y": "य", "r": "र", "l": "ल", "v": "व", "w": "व", "s": "स", "h": "ह", "z": "ज", "q": "क", "x": "क्स",
}
VOWELS = {  # independent letter, sign after a consonant
    "aa": ("आ", "ा"), "ai": ("ऐ", "ै"), "au": ("औ", "ौ"), "ou": ("औ", "ौ"), "ee": ("ई", "ी"), "ii": ("ई", "ी"),
    "oo": ("ऊ", "ू"), "uu": ("ऊ", "ू"),
    "a": ("अ", ""), "e": ("ए", "े"), "i": ("इ", "ि"), "o": ("ओ", "ो"), "u": ("उ", "ु"),
}
# At the end of a name the vowel is usually long: Kavita, Chikhali, Raju, Desai.
FINAL = {"a": "ा", "i": "ी", "u": "ू", "ai": "ाई"}
VIRAMA, ANUSVARA = "्", "ं"
SONORANTS = ("y", "r", "l", "v", "w", "s", "sh", "h", "n", "m")  # n/m before these stay letters: Kamya, Sunny
LABIALS = ("p", "ph", "b", "bh")
TOKENS = sorted([*CONS, *VOWELS], key=len, reverse=True)
LANGS = ("gu", "hi")


def _word(w: str) -> str:
    w = w.lower()
    out, prev_cons, i = [], False, 0
    while i < len(w):
        tok = next((t for t in TOKENS if w.startswith(t, i)), w[i])
        i += len(tok)
        nxt = next((t for t in TOKENS if w.startswith(t, i)), "")
        if tok in VOWELS:
            ind, sign = VOWELS[tok]
            if prev_cons:
                out.append(FINAL.get(tok, sign) if i == len(w) else sign)
            else:
                out.append(ind)
            prev_cons = False
        elif tok == "y" and prev_cons and i == len(w):
            out.append(FINAL["i"])  # Sunny, Bunty
            prev_cons = False
        elif tok in CONS:
            if out and not prev_cons and nxt in CONS and nxt not in SONORANTS and (
                tok == "n" or (tok == "m" and nxt in LABIALS)
            ):
                out.append(ANUSVARA)  # Anand, Champa; m stays a letter before others: Mamta
                continue
            if prev_cons:
                out.append(VIRAMA)
            out.append(CONS[tok])
            prev_cons = True
        else:
            out.append(tok)
            prev_cons = False
    return "".join(out)


def _shift(s: str, lo: int, by: int) -> str:
    return "".join(chr(ord(c) + by) if lo <= ord(c) <= lo + 0x7F else c for c in s)


def _gu(hi: str) -> str:
    # Gujarati has no nukta letters: ड़ ढ़ are written ડ ઢ
    hi = hi.replace("ड़", "ड").replace("ढ़", "ढ").replace("़", "")
    return _shift(hi, 0x0900, 0x180)


def _pair(w: str) -> tuple[str, str]:
    """(Gujarati, Hindi) for one English word: the word list, else a known ending split off, else the letter rules."""
    k = w.lower()
    v = WORDS.get(k)
    if v is None:
        suffix = next((s for s in SUFFIXES if k.endswith(s) and len(k) - len(s) >= 2), None)
        if suffix:  # Shantaben, Rameshbhai
            (g1, h1), (g2, h2) = _pair(k[: -len(suffix)]), _pair(suffix)
            return g1 + g2, h1 + h2
        v = _word(k)
    return v if isinstance(v, tuple) else (_gu(v), v)


def localized(text: str | None, words: bool = True) -> dict[str, str]:
    """{"gu": ..., "hi": ...} for a name or place; {} for no text. Text already in one script is mirrored to the other.
    words=False is the letter rules alone (what rows written before the word list hold)."""
    if not text:
        return {}
    gu, hi = [], []
    for part in re.split(r"([A-Za-z]+)", text):
        if part.isascii() and part.isalpha():
            g, h = _pair(part) if words else (None, _word(part))
            gu.append(g or _gu(h))
            hi.append(h)
        else:
            h = _shift(part, 0x0A80, -0x180)  # typed in Gujarati: Hindi gets the Devanagari letters
            gu.append(_gu(h))
            hi.append(h)
    return {"gu": "".join(gu), "hi": "".join(hi)}


if __name__ == "__main__":  # self-check, from backend/: python -m core.translit
    # letter rules alone
    for en, hi, gu in [
        ("desai", "देसाई", "દેસાઈ"),
        ("Kavita Desai", "कविता देसाई", "કવિતા દેસાઈ"),
        ("Trushit", "त्रुशित", "ત્રુશિત"),
        ("Mahek", "महेक", "મહેક"),
        ("Jiya", "जिया", "જિયા"),
        ("Chikhali", "चिखली", "ચિખલી"),
        ("Anand", "अनंद", "અનંદ"),
        ("kamya", "कम्या", "કમ્યા"),
        ("Sunny", "सुन्नी", "સુન્ની"),
        ("Bhavesh Shah", "भवेश शह", "ભવેશ શહ"),
        ("Mamta", "मम्ता", "મમ્તા"),  # word list has the usual ममता
        ("Champa", "चंपा", "ચંપા"),
    ]:
        assert localized(en, words=False) == {"gu": gu, "hi": hi}, (en, localized(en, words=False))
    # word list, endings, Gujarati/Hindi differences, nukta letters
    for en, hi, gu in [
        ("Ahmedabad", "अहमदाबाद", "અમદાવાદ"),
        ("Bhavesh Shah", "भावेश शाह", "ભાવેશ શાહ"),
        ("Patel", "पटेल", "પટેલ"),
        ("Surat", "सूरत", "સુરત"),
        ("Shantaben Chaturvedi", "शांताबेन चतुर्वेदी", "શાંતાબેન ચતુર્વેદી"),
        ("Rameshbhai", "रमेशभाई", "રમેશભાઈ"),
        ("Junagadh", "जूनागढ़", "જૂનાગઢ"),
        ("Kavita Desai", "कविता देसाई", "કવિતા દેસાઈ"),
    ]:
        assert localized(en) == {"gu": gu, "hi": hi}, (en, localized(en))
    assert localized("દેસાઈ") == {"gu": "દેસાઈ", "hi": "देसाई"}
    assert localized("") == {} and localized(None) == {}
    assert localized("12 B-wing")["hi"] == "12 ब-विंग"
    print("ok")
