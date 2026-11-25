"""Language-aware text normalization for similarity analysis.

The module never downloads NLTK corpora at runtime. It uses NLTK stopword
corpora when installed locally and safe bundled fallback lists otherwise.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_TOKEN_RE = re.compile(r"[^a-zа-яё]+", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")

_RU_FALLBACK = frozenset("""
а без более бы был была были было быть в вам вас весь во вот все всего
всех вы где да даже для до его ее если есть ещё же за здесь и из или им
их к как ко когда кто ли либо мне может мы на над надо наш не него нее
нет ни них но ну о об один она они оно от по под при с со так такой
также там те тем то того той только том ты у уже хотя чего чем что чтобы
эта эти это я
""".split())
_EN_FALLBACK = frozenset("""
a an and are as at be been being by for from had has have he her hers him
his i if in into is it its me my of on or our ours she that the their them
they this those to was we were what when where which who will with you your
yours not no do does did can could would should may might must
""".split())


@lru_cache(maxsize=1)
def _stopwords() -> dict[str, frozenset[str]]:
    result = {"ru": _RU_FALLBACK, "en": _EN_FALLBACK}
    try:
        from nltk.corpus import stopwords
        for language, nltk_name in (("ru", "russian"), ("en", "english")):
            try:
                result[language] = frozenset(stopwords.words(nltk_name))
            except LookupError:
                pass
    except ImportError:
        pass
    return result


@lru_cache(maxsize=1)
def _russian_morph():
    try:
        import pymorphy2
        return pymorphy2.MorphAnalyzer()
    except (ImportError, Exception):
        # Morphology is an enhancement, not a reason to make all ingestion fail.
        return None


def normalize_text(raw_text: str, language_code: str | None = None) -> tuple[str, int]:
    """Return normalized text and token count.

    Russian tokens are lemmatized when pymorphy2 is usable. English tokens are
    lowercased; punctuation, digits, and stopwords are removed for both.
    """
    if not raw_text or not raw_text.strip():
        return "", 0

    text = unicodedata.normalize("NFKC", raw_text).lower()
    text = _TOKEN_RE.sub(" ", text)
    tokens = _SPACE_RE.split(text.strip()) if text.strip() else []
    lang = (language_code or "").lower()
    if lang not in {"ru", "en"}:
        cyrillic = sum("\u0400" <= ch <= "\u04ff" for ch in text)
        latin = sum("a" <= ch <= "z" for ch in text)
        lang = "ru" if cyrillic > latin else "en"

    stopwords = _stopwords()[lang]
    morph = _russian_morph() if lang == "ru" else None
    normalized: list[str] = []
    for token in tokens:
        if not token or token in stopwords:
            continue
        if morph is not None:
            token = morph.parse(token)[0].normal_form
        if token and token not in stopwords:
            normalized.append(token)

    return " ".join(normalized), len(normalized)


# Explicit descriptive alias for external callers.
normalize = normalize_text
