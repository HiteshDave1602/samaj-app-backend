import html
import logging
import re

import httpx

from core.config import settings
from core.translit import LANGS, localized

# MyMemory: free, no key. ponytail: 5,000 characters a day per server IP (50,000 with TRANSLATE_EMAIL), counted per
# target language; swap this file for a paid service when posts outgrow that.
URL = "https://api.mymemory.translated.net/get"
MAX_BYTES = 450  # the service refuses more than 500 in one request
log = logging.getLogger(__name__)


def _source(text: str) -> str:
    """The service needs the source language; Gujarati and Hindi are told apart by their script."""
    if re.search(r"[઀-૿]", text):
        return "gu"
    return "hi" if re.search(r"[ऀ-ॿ]", text) else "en"


def _chunks(text: str) -> list[str]:
    """Pieces of at most MAX_BYTES that join back into text, cut after a sentence or line where possible."""
    pieces = []
    for sentence in re.findall(r"[^.!?।\n]*[.!?।\n]*\s*", text):
        if len(sentence.encode()) <= MAX_BYTES:
            pieces.append(sentence)
            continue
        for word in re.findall(r"\S*\s*", sentence):
            # 100 characters are 400 bytes at most in these scripts
            pieces += [word] if len(word.encode()) <= MAX_BYTES else [word[i:i + 100] for i in range(0, len(word), 100)]
    chunks, current = [], ""
    for piece in pieces:
        if len((current + piece).encode()) > MAX_BYTES:
            chunks.append(current)
            current = ""
        current += piece
        if "\n" in piece:  # sent on its own, so the service can't lose a paragraph break
            chunks.append(current)
            current = ""
    return [*chunks, current] if current else chunks


def _one(text: str, source: str, lang: str) -> str:
    params = {"q": text, "langpair": f"{source}|{lang}"}
    if settings.translate_email:
        params["de"] = settings.translate_email
    r = httpx.get(URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    out = data["responseData"]["translatedText"]
    # over quota can still be a 200, with the warning where the translation should be: it must never be saved
    if str(data.get("responseStatus")) != "200" or not out or out.startswith("MYMEMORY WARNING"):
        raise ValueError(f"status {data.get('responseStatus')}: {str(out)[:80]}")
    return html.unescape(out)


def _translated(text: str, lang: str) -> str:
    source = _source(text)
    if source == lang:
        return text
    out = []
    for chunk in _chunks(text):
        words = chunk.rstrip()
        if words:
            out.append(_one(words, source, lang))
        out.append(chunk[len(words):])  # keeps the line breaks between paragraphs
    joined = "".join(out)
    # it hands short phrases back unchanged at times ('mumbai darshan'): the name rules at least give the right script
    return localized(text)[lang] if joined.casefold() == text.casefold() else joined


def translate(texts: list[str]) -> dict[str, list[str]] | None:
    """{lang: translations, in the order of texts} for each of LANGS; None when the service failed or the day's
    allowance is used up, so callers keep the original text and try again later."""
    try:
        return {lang: [_translated(t, lang) for t in texts] for lang in LANGS}
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        log.warning("Translation failed: %s", exc)
        return None


if __name__ == "__main__":  # self-check, no network, from backend/: python -m core.translate
    def reply(text, status=200, http=200):
        return httpx.Response(http, json={"responseData": {"translatedText": text}, "responseStatus": status},
                              request=httpx.Request("GET", URL))

    # chunks: under the limit, nothing lost, whatever the text looks like
    for s in ["Short.", "One. Two!\n\nThree?", "વાક્ય. " * 200, "x" * 2000, "શબ્દ" * 400, "word " * 500, ""]:
        parts = _chunks(s)
        assert "".join(parts) == s and all(len(p.encode()) <= 500 for p in parts), s[:20]

    calls = []
    def ok(url, params, timeout):
        calls.append(params)
        return reply(f"{params['langpair']}:{params['q']}")
    httpx.get = ok
    assert translate(["a b"]) == {"gu": ["en|gu:a b"], "hi": ["en|hi:a b"]}
    assert "de" not in calls[0]  # no email goes out unless it is configured
    # already in the target language: not sent; Gujarati text goes to Hindi only
    calls.clear()
    assert translate(["નમસ્તે"]) == {"gu": ["નમસ્તે"], "hi": ["gu|hi:નમસ્તે"]} and len(calls) == 1
    calls.clear()
    assert _translated("One.\n\nTwo.", "hi") == "en|hi:One.\n\nen|hi:Two."  # paragraphs survive
    assert [c["q"] for c in calls] == ["One.", "Two."]

    httpx.get = lambda url, params, timeout: reply("तुम &#39;ठीक&#39;")
    assert translate(["you"])["hi"] == ["तुम 'ठीक'"]  # entities decoded
    httpx.get = lambda url, params, timeout: reply("mumbai darshan")
    assert translate(["Mumbai darshan"])["hi"] == [localized("Mumbai darshan")["hi"]]  # unchanged: name rules

    # failures give None, and a quota warning is never taken for a translation
    for bad in (reply("MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS"),
                reply("MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS", status=429),
                reply("QUERY LENGTH LIMIT EXCEEDED", status=403), reply("x", http=429), reply("")):
        httpx.get = lambda url, params, timeout, b=bad: b
        assert translate(["a"]) is None, bad.text
    def down(url, params, timeout):
        raise httpx.ConnectTimeout("slow")
    httpx.get = down
    assert translate(["a"]) is None
    print("ok")
