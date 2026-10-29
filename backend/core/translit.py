import re

# Names typed in English letters -> Devanagari, then Gujarati by shifting code points: the two Unicode blocks are
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
            if tok in ("n", "m") and out and not prev_cons and nxt in CONS and nxt not in SONORANTS:
                out.append(ANUSVARA)  # Anand, Champa
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


def localized(text: str | None) -> dict[str, str]:
    """{"gu": ..., "hi": ...} for a name or place; {} for no text. Text already in one script is mirrored to the other."""
    if not text:
        return {}
    hi = re.sub(r"[A-Za-z]+", lambda m: _word(m.group()), text)
    hi = _shift(hi, 0x0A80, -0x180)  # typed in Gujarati: Hindi gets the Devanagari letters
    return {"gu": _shift(hi, 0x0900, 0x180), "hi": hi}


if __name__ == "__main__":  # self-check, from backend/: python -m core.translit
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
    ]:
        assert localized(en) == {"gu": gu, "hi": hi}, (en, localized(en))
    assert localized("દેસાઈ") == {"gu": "દેસાઈ", "hi": "देसाई"}
    assert localized("") == {} and localized(None) == {}
    assert localized("12 B-wing")["hi"] == "12 ब-विंग"
    print("ok")
