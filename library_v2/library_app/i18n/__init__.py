from __future__ import annotations

from library_app.i18n.en import EN_TRANSLATIONS
from library_app.i18n.fa import FA_TRANSLATIONS

TRANSLATIONS: dict[str, dict[str, str]] = {
    "fa": FA_TRANSLATIONS,
    "en": EN_TRANSLATIONS,
}


def get_translations(lang: str = "fa") -> dict[str, str]:
    return TRANSLATIONS.get(lang, FA_TRANSLATIONS)


def t(key: str, lang: str = "fa") -> str:
    bundle = get_translations(lang)
    return bundle.get(key, FA_TRANSLATIONS.get(key, key))
