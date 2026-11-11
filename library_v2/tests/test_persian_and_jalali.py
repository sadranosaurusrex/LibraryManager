from __future__ import annotations

import sys
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from library_app.utils.jalali import (
    format_date_for_locale,
    format_jalali_long,
    format_jalali_short,
    gregorian_to_jalali,
    is_jalali_leap,
    jalali_to_gregorian,
    parse_flexible_date,
)
from library_app.utils.persian import (
    clean_persian_text,
    coerce_text,
    compact_for_search,
    normalize_for_search,
    split_genres,
    to_ascii_digits,
    to_persian_digits,
)


class TestPersianUtils(unittest.TestCase):
    def test_digits_and_coercion(self) -> None:
        self.assertEqual(to_ascii_digits("۱۲۳۴۵۶۷۸۹۰"), "1234567890")
        self.assertEqual(to_ascii_digits("١٢٣"), "123")
        self.assertEqual(to_persian_digits("2026-06-06"), "۲۰۲۶-۰۶-۰۶")
        self.assertEqual(coerce_text(1984), "1984")
        self.assertEqual(coerce_text(1984.0), "1984")
        self.assertEqual(coerce_text(float("nan")), "")
        self.assertEqual(coerce_text(None), "")

    def test_arabic_normalization_and_zwnj(self) -> None:
        self.assertEqual(clean_persian_text("  تاريخ   كهن  ياد  "), "تاریخ کهن یاد")
        self.assertEqual(normalize_for_search("جامعه‌شناسی"), "جامعه شناسی")
        self.assertEqual(compact_for_search("جامعه‌شناسی"), "جامعهشناسی")
        self.assertEqual(compact_for_search("جامعه شناسی"), "جامعهشناسی")
        self.assertEqual(normalize_for_search("١٤٠٥ کتاب"), "1405 کتاب")

    def test_split_genres(self) -> None:
        self.assertEqual(
            split_genres("دستور العمل ، ديني  ، سياسي / دینی "),
            ["دستور العمل", "دینی", "سیاسی"],
        )
        self.assertEqual(split_genres(None), [])


class TestJalaliCalendar(unittest.TestCase):
    def test_known_conversions(self) -> None:
        # Nowruz 1405
        self.assertEqual(gregorian_to_jalali(2026, 3, 21), (1405, 1, 1))
        self.assertEqual(jalali_to_gregorian(1405, 1, 1), (2026, 3, 21))

        # 2026-06-06 -> 1405-03-16 (Khordad 16)
        self.assertEqual(gregorian_to_jalali(2026, 6, 6), (1405, 3, 16))
        self.assertEqual(jalali_to_gregorian(1405, 3, 16), (2026, 6, 6))

        # 2026-11-12 -> 1405-08-21 (Aban 21)
        self.assertEqual(gregorian_to_jalali(2026, 11, 12), (1405, 8, 21))
        self.assertEqual(jalali_to_gregorian(1405, 8, 21), (2026, 11, 12))

    def test_leap_year_roundtrip(self) -> None:
        # 1403 was a leap year in Jalali (Esfand 30 = 2025-03-20)
        self.assertTrue(is_jalali_leap(1403))
        self.assertEqual(jalali_to_gregorian(1403, 12, 30), (2025, 3, 20))
        self.assertEqual(gregorian_to_jalali(2025, 3, 20), (1403, 12, 30))

    def test_flexible_date_parsing_and_formatting(self) -> None:
        self.assertEqual(parse_flexible_date("۱۴۰۵/۰۳/۱۶"), "2026-06-06")
        self.assertEqual(parse_flexible_date("1405-08-21"), "2026-11-12")
        self.assertEqual(parse_flexible_date("2026-06-06"), "2026-06-06")
        self.assertEqual(format_jalali_short("2026-06-06"), "۱۴۰۵/۰۳/۱۶")
        self.assertEqual(format_jalali_long("2026-11-12"), "۲۱ آبان ۱۴۰۵")
        self.assertEqual(format_date_for_locale("2026-11-12", lang="en", long_format=True), "Nov 12, 2026")
        with self.assertRaises(ValueError):
            parse_flexible_date("not-a-date")


if __name__ == "__main__":
    unittest.main()
