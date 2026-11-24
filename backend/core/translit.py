import re
import unicodedata

from core.translit_words import INITIALS, SUFFIXES, WORDS

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


# ---- Gujarati/Hindi -> English letters, for names typed in either script. Transliteration only: a name is spelled
# out, never translated, so "પટેલ" is Patel, not a dictionary word. Word-list spellings come back as listed.
NUKTA = "़"
R_CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "f", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
}
R_NUKTA = {"ज": "z", "फ": "f"}  # ज़ फ़; other nukta letters read as the plain one
R_VOWELS = {"अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ऋ": "ru", "ए": "e", "ऐ": "ai", "ओ": "o",
            "औ": "au", "ऍ": "e", "ऑ": "o"}
R_SIGNS = {"ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ru", "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
           "ॅ": "e", "ॉ": "o"}


def _key(deva: str) -> str:
    """Devanagari compared without nukta: Gujarati has none, so જૂનાગઢ must still find जूनागढ़."""
    return unicodedata.normalize("NFD", deva).replace(NUKTA, "")


REVERSE: dict[str, str] = {}  # Devanagari spelling (Hindi, or the Gujarati one shifted) -> English, first listed wins
for _en, _v in WORDS.items():
    _g, _h = _v if isinstance(_v, tuple) else (_gu(_v), _v)
    for _s in (_h, _shift(_g, 0x0A80, -0x180)):
        REVERSE.setdefault(_key(_s), _en)
R_SUFFIXES = [(_key(WORDS[s] if isinstance(WORDS[s], str) else WORDS[s][1]), s) for s in SUFFIXES]
R_SUFFIXES += [(_key(_shift(WORDS[s][0], 0x0A80, -0x180)), s) for s in SUFFIXES if isinstance(WORDS[s], tuple)]
R_INITIALS = {_key(_shift(g, 0x0A80, -0x180)): en for g, en in INITIALS.items()}


def _roman(w: str, gujarati: bool = False) -> str:
    """Letter rules for one Devanagari word: each consonant carries an 'a' unless a sign or virama replaces it; the
    'a' is then dropped at the end of a word (रमेश Ramesh) and between syllables that keep theirs (कमला Kamla).
    gujarati: the word was typed in Gujarati, where ઝ is z (Zala, zone) rather than Hindi's jh."""
    units = []  # [letters, vowel, inherent]: inherent = the consonant's own 'a', which may be dropped
    i = 0
    while i < len(w):
        c = w[i]
        if c in R_CONS:
            lat = "z" if gujarati and c == "झ" else R_CONS[c]
            if w[i + 1:i + 2] == NUKTA:
                lat, i = R_NUKTA.get(c, lat), i + 1
            nxt = w[i + 1:i + 2]
            if nxt == VIRAMA:
                units.append([lat, "", False])
                i += 1
            elif nxt in R_SIGNS:
                units.append([lat, R_SIGNS[nxt], False])
                i += 1
            else:
                units.append([lat, "a", True])
        elif c in R_VOWELS:
            units.append(["", R_VOWELS[c], False])
        elif c in (ANUSVARA, "ँ"):
            units.append(["~", "", False])  # n, or m before p/b/m: decided below
        elif c == "ः":
            units.append(["h", "", False])
        elif c in R_SIGNS:  # a sign with no consonant, typed after a vowel (અ + ા for આ): it is that vowel
            if units and units[-1][0] == "":
                units[-1][1] = R_SIGNS[c]
            else:
                units.append(["", R_SIGNS[c], False])
        elif unicodedata.category(c) == "Nd":
            units.append([str(unicodedata.digit(c)), "", False])
        elif not "ऀ" <= c <= "ॿ":  # any other Devanagari mark is left out, never shown as is
            units.append([c, "", False])
        i += 1

    def cons(u):
        return u[0] not in ("", "~") and u[0].isalpha()

    # the last consonant's 'a' goes, except in a one-letter word or a conjunct ending in r/y/l (मिश्र Mishra,
    # सूर्य Surya, शुक्ल Shukla)
    last = len(units) - 1
    if last > 0 and units[last][2] and cons(units[last]) and not (
            units[last][0] in ("r", "y", "l") and cons(units[last - 1]) and units[last - 1][1] == ""):
        units[last][1] = ""
    # inside the word, right to left: V C(a) C V -> drop the 'a' (कमला Kamla, धोरणपारडी Dhoranpardi, पंडया Pandya)
    for k in range(last - 1, 0, -1):
        u, prev, nxt = units[k], units[k - 1], units[k + 1]
        if u[2] and u[1] and (prev[1] or prev[0] == "~") and cons(nxt) and nxt[1]:
            u[1] = ""
    out = []
    for k, (letters, vowel, _) in enumerate(units):
        if letters == "~":
            nxt = units[k + 1][0] if k + 1 < len(units) else ""
            letters = "m" if nxt[:1] in ("p", "b", "m") else "n"
        out.append(letters + vowel)
    return "".join(out)


def _english(deva: str, gujarati: bool, words: bool = True) -> str:
    """One Devanagari word in English letters: the word list, else a known ending split off, else the letter rules."""
    k = _key(deva)
    if words and k in REVERSE:
        return REVERSE[k].capitalize()
    for sk, s in R_SUFFIXES if words else ():
        if k.endswith(sk) and len(k) > len(sk) + 1:  # રમેશભાઈ Rameshbhai
            return _english(k[: -len(sk)], gujarati) + s
    return _roman(k, gujarati).capitalize()


def localized(text: str | None, words: bool = True) -> dict[str, str]:
    """{"en": ..., "gu": ..., "hi": ...} for a name or place; {} for no text. Each language gets the same name in its
    own script: English text stays as typed, Gujarati or Hindi text is mirrored to the other and spelled out in
    English letters. words=False is the letter rules alone (what rows written before the word list hold)."""
    if not text:
        return {}
    en, gu, hi = [], [], []
    for part in re.split(r"([A-Za-z]+)", text):
        if part.isascii() and part.isalpha():
            g, h = _pair(part) if words else (None, _word(part))
            en.append(part)
            gu.append(g or _gu(h))
            hi.append(h)
        else:
            h = _shift(part, 0x0A80, -0x180)  # typed in Gujarati: Hindi gets the Devanagari letters
            gujarati = bool(re.search(r"[઀-૿]", part))

            def word(m):  # an initial is the English letter it names: બી. -> B.
                if m.group(2) and _key(m.group(1)) in R_INITIALS:
                    return R_INITIALS[_key(m.group(1))] + "."
                return _english(m.group(1), gujarati, words) + m.group(2)
            en.append(re.sub(r"([ऀ-ॿ]+)(\.?)", word, h))
            gu.append(_gu(h))
            hi.append(h)
    return {"en": "".join(en), "gu": "".join(gu), "hi": "".join(hi)}


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
        assert localized(en, words=False) == {"en": en, "gu": gu, "hi": hi}, (en, localized(en, words=False))
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
        assert localized(en) == {"en": en, "gu": gu, "hi": hi}, (en, localized(en))
    assert localized("દેસાઈ") == {"en": "Desai", "gu": "દેસાઈ", "hi": "देसाई"}
    assert localized("") == {} and localized(None) == {}
    assert localized("12 B-wing")["hi"] == "12 ब-विंग"
    # typed in Gujarati or Hindi -> English letters: listed spellings exactly, the rest by the letter rules
    for typed, en in [
        ("અમદાવાદ", "Ahmedabad"), ("જૂનાગઢ", "Junagadh"), ("पटेल", "Patel"), ("શાંતાબેન મહેતા", "Shantaben Mehta"),
        ("રમેશભાઈ", "Rameshbhai"), ("રમેશ", "Ramesh"), ("કમલા", "Kamla"), ("હસમુખ", "Hasmukh"), ("સુરતી", "Surti"),
        ("ભરત", "Bharat"), ("જયેશ", "Jayesh"), ("અરવિંદ", "Arvind"), ("મિશ્ર", "Mishra"), ("ચંપા", "Champa"),
        ("નવસારી", "Navsari"), ("ધર્મેશ", "Dharmesh"), ("કૃણાલ", "Krunal"), ("હેતલ", "Hetal"), ("ના", "Na"),
        ("ફાલ્ગુની", "Falguni"), ("૧૨, પટેલ નગર", "12, Patel Nagar"), ("Asha પટેલ", "Asha Patel"),
        ("ધોરણપારડી", "Dhoranpardi"), ("અમલસાડ", "Amalsad"), ("સુરત અઠવા ઝોન", "Surat Athva Zon"), ("झाँसी", "Jhansi"),
        ("ડૉ. શ્લેષા વૈદ્ય", "Dr. Shlesha Vaidya"), ("સૂરજ બી. પાઠક", "Suraj B. Pathak"), ("ધરા શુક્લ", "Dhara Shukla"),
        ("પંડયા", "Pandya"), ("દ્યુતિબહેન", "Dyutibahen"), ("સંદલપુર", "Sandalpur"), ("કંદર્પ", "Kandarp"),
        ("એમ.કે. શાહ", "M.K. Shah"), ("બી", "Bi"), ("હોન્ડ", "Hond"), ("સૂર્ય", "Surya"), ("અામરી", "Amri"), ("સુવેણખૂર્દ", "Suvenkhurd"),
    ]:
        assert localized(typed)["en"] == en, (typed, localized(typed)["en"])
    # nothing is lost going round: English typed -> Gujarati -> English gives the listed word back
    for name in ("Patel", "Desai", "Ahmedabad", "Surat", "Mehta", "Rameshbhai", "Navsari"):
        assert localized(localized(name)["gu"])["en"] == name, name
    print("ok")
