from __future__ import annotations

import datetime as dt
import re
from typing import Any

from library_app.utils.persian import coerce_text, to_ascii_digits, to_persian_digits

PERSIAN_MONTHS: tuple[str, ...] = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)

ENGLISH_MONTHS: tuple[str, ...] = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

_DATE_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """Convert Gregorian date (Y, M, D) to Jalali (Shamsi) (Y, M, D)."""
    g_d_m = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666
        + (365 * gy)
        + ((gy2 + 3) // 4)
        - ((gy2 + 99) // 100)
        + ((gy2 + 399) // 400)
        + gd
        + g_d_m[gm - 1]
    )
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    """Convert Jalali (Shamsi) date (Y, M, D) to Gregorian (Y, M, D)."""
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186

    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365

    gd = days + 1
    sal_a = (
        0,
        31,
        29 if ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    )
    gm = 0
    for gm in range(1, 13):
        v = sal_a[gm]
        if gd <= v:
            break
        gd -= v
    return gy, gm, gd


def is_jalali_leap(jy: int) -> bool:
    # Check if Esfand 30 converts back cleanly to Esfand 30
    gy2, gm2, gd2 = jalali_to_gregorian(jy, 12, 30)
    jy2, jm2, jd2 = gregorian_to_jalali(gy2, gm2, gd2)
    return (jy2, jm2, jd2) == (jy, 12, 30)


def parse_flexible_date(raw: Any) -> str:
    """Parse Gregorian ISO or Jalali date strings into canonical 'YYYY-MM-DD'."""
    if raw is None:
        return ""
    if isinstance(raw, dt.datetime):
        return raw.date().isoformat()
    if isinstance(raw, dt.date):
        return raw.isoformat()

    text = to_ascii_digits(coerce_text(raw))
    if not text:
        return ""

    # Strip time portion if timestamp string like '2026-06-06 00:00:00'
    if " " in text and len(text.split(" ")[0]) >= 8:
        text = text.split(" ")[0]
    if "T" in text and len(text.split("T")[0]) >= 8:
        text = text.split("T")[0]

    match = _DATE_RE.match(text)
    if not match:
        raise ValueError(f"Invalid date format: {raw!r}")

    year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))

    # Jalali year heuristic (1200..1599)
    if 1200 <= year <= 1599:
        if not (1 <= month <= 12):
            raise ValueError(f"Invalid Jalali month: {month}")
        max_day = 31 if month <= 6 else (30 if month <= 11 or is_jalali_leap(year) else 29)
        if not (1 <= day <= max_day):
            raise ValueError(f"Invalid Jalali day: {day} for month {month}")
        gy, gm, gd = jalali_to_gregorian(year, month, day)
        return dt.date(gy, gm, gd).isoformat()

    return dt.date(year, month, day).isoformat()


def today_iso() -> str:
    return dt.datetime.now().astimezone().date().isoformat()


def format_jalali_short(iso_date: str, persian_digits: bool = True) -> str:
    if not iso_date:
        return ""
    try:
        parsed = dt.date.fromisoformat(parse_flexible_date(iso_date))
    except ValueError:
        return iso_date
    jy, jm, jd = gregorian_to_jalali(parsed.year, parsed.month, parsed.day)
    formatted = f"{jy:04d}/{jm:02d}/{jd:02d}"
    return to_persian_digits(formatted) if persian_digits else formatted


def format_jalali_long(iso_date: str, persian_digits: bool = True) -> str:
    if not iso_date:
        return ""
    try:
        parsed = dt.date.fromisoformat(parse_flexible_date(iso_date))
    except ValueError:
        return iso_date
    jy, jm, jd = gregorian_to_jalali(parsed.year, parsed.month, parsed.day)
    formatted = f"{jd} {PERSIAN_MONTHS[jm - 1]} {jy}"
    return to_persian_digits(formatted) if persian_digits else formatted


def format_date_for_locale(iso_date: str, lang: str = "fa", long_format: bool = False) -> str:
    if not iso_date:
        return ""
    if lang == "fa":
        return format_jalali_long(iso_date) if long_format else format_jalali_short(iso_date)
    try:
        parsed = dt.date.fromisoformat(parse_flexible_date(iso_date))
    except ValueError:
        return iso_date
    if long_format:
        return f"{ENGLISH_MONTHS[parsed.month - 1]} {parsed.day}, {parsed.year}"
    return parsed.isoformat()
