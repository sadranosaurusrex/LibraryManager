from __future__ import annotations

import math
import re
from typing import Any

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
ASCII_DIGITS = "0123456789"

_TO_ASCII_TRANS = str.maketrans(
    PERSIAN_DIGITS + ARABIC_INDIC_DIGITS,
    ASCII_DIGITS * 2,
)
_TO_PERSIAN_TRANS = str.maketrans(
    ASCII_DIGITS + ARABIC_INDIC_DIGITS,
    PERSIAN_DIGITS * 2,
)

# Arabic presentation/variant characters -> standard Persian forms
_CHAR_MAP = str.maketrans(
    {
        "ي": "ی",
        "ى": "ی",
        "ئ": "ی",  # used in search folding; clean_persian_text preserves ئ
        "ك": "ک",
        "ة": "ه",
        "ۀ": "ه",
        "ؤ": "و",
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "\u0640": "",  # Arabic tatweel / kashida
    }
)

# Conservative clean mapping safe for stored text (keeps آ، ئ، ۀ intact)
_CLEAN_CHAR_MAP = str.maketrans(
    {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
        "ة": "ه",
        "أ": "ا",
        "إ": "ا",
        "\u0640": "",
    }
)

_DIACRITICS_RE = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_MULTISPACE_RE = re.compile(r"\s+")
_COMMA_SPACE_RE = re.compile(r"\s*([،,])\s*")
_GENRE_SPLIT_RE = re.compile(r"[,،/;|]+")


def is_na(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    text = str(value).strip().lower()
    return text in {"", "nan", "none", "<na>", "nat"}


def coerce_text(value: Any) -> str:
    """Safely convert Excel cell values (str, int, float, NaN) to clean string."""
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        if value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    text = str(value).strip()
    if text.lower() in {"nan", "none", "<na>", "nat"}:
        return ""
    return text


def to_ascii_digits(text: str) -> str:
    return text.translate(_TO_ASCII_TRANS)


def to_persian_digits(value: str | float) -> str:
    return str(value).translate(_TO_PERSIAN_TRANS)


def clean_persian_text(value: Any) -> str:
    """Normalize Arabic variants (ي/ك) and whitespace for clean display/storage."""
    text = coerce_text(value)
    if not text:
        return ""
    text = text.translate(_CLEAN_CHAR_MAP)
    text = _DIACRITICS_RE.sub("", text)
    text = _MULTISPACE_RE.sub(" ", text).strip()
    text = _COMMA_SPACE_RE.sub(r"\1 ", text).strip()
    return text


def normalize_for_search(value: Any) -> str:
    """Aggressive normalization for Persian+English fuzzy/substring search."""
    text = coerce_text(value)
    if not text:
        return ""
    text = _DIACRITICS_RE.sub("", text)
    text = text.translate(_CHAR_MAP)
    text = to_ascii_digits(text)
    # Treat ZWNJ (نیم‌فاصله) as space in token-level search
    text = text.replace("\u200c", " ").replace("\u200d", "")
    text = _MULTISPACE_RE.sub(" ", text).strip()
    return text.lower()


def compact_for_search(value: Any) -> str:
    """Space/ZWNJ-insensitive form (e.g. 'جامعه شناسی' == 'جامعه‌شناسی' == 'جامعهشناسی')."""
    normalized = normalize_for_search(value)
    return normalized.replace(" ", "")


def split_genres(value: Any) -> list[str]:
    """Split multi-value genre string (e.g. 'مدنی ، سیاسی') into clean unique tags."""
    text = clean_persian_text(value)
    if not text:
        return []
    seen: set[str] = set()
    tags: list[str] = []
    for raw_part in _GENRE_SPLIT_RE.split(text):
        part = _MULTISPACE_RE.sub(" ", raw_part).strip()
        if not part:
            continue
        key = normalize_for_search(part)
        if key not in seen:
            seen.add(key)
            tags.append(part)
    return tags


def persian_sort_key(value: Any) -> tuple[int, str]:
    """Sort key safe against mixed types and Arabic/Persian codepoint quirks."""
    normalized = normalize_for_search(value)
    if not normalized:
        return (1, "")
    return (0, normalized)
