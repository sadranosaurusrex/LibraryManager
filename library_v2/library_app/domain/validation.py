from __future__ import annotations

import math
from typing import Any

from library_app.domain.models import Book, BookStatus
from library_app.utils.jalali import parse_flexible_date, today_iso
from library_app.utils.persian import clean_persian_text, coerce_text, to_ascii_digits


class ValidationError(ValueError):
    """Structured validation error with error key and optional field."""

    def __init__(self, message_key: str, detail: str = "", field: str = "") -> None:
        super().__init__(detail or message_key)
        self.message_key = message_key
        self.detail = detail
        self.field = field


def parse_optional_int(value: Any, *, field: str = "", min_val: int | None = 1, max_val: int | None = 999) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = to_ascii_digits(coerce_text(value))
    if not text:
        return None
    try:
        parsed_float = float(text)
    except ValueError as exc:
        raise ValidationError("err_invalid_number", f"{field}: {value!r}", field=field) from exc
    if not parsed_float.is_integer():
        raise ValidationError("err_invalid_integer", f"{field}: {value!r}", field=field)
    num = int(parsed_float)
    if min_val is not None and num < min_val:
        raise ValidationError("err_out_of_range", f"{field}: {num} < {min_val}", field=field)
    if max_val is not None and num > max_val:
        raise ValidationError("err_out_of_range", f"{field}: {num} > {max_val}", field=field)
    return num


def parse_optional_rating(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = to_ascii_digits(coerce_text(value)).replace("٫", ".").replace("/", ".")
    if not text:
        return None
    try:
        num = float(text)
    except ValueError as exc:
        raise ValidationError("err_invalid_rating", str(value), field="rating") from exc
    if num < 0 or num > 5:
        raise ValidationError("err_rating_range", str(num), field="rating")
    return round(num, 2)


def validate_book_payload(payload: dict[str, Any], existing: Book | None = None) -> dict[str, Any]:
    """Validate and normalize incoming API payload for creating or updating a Book."""
    book_name_raw = payload.get("book_name", existing.book_name if existing else "")
    book_name = clean_persian_text(book_name_raw)
    if not book_name:
        raise ValidationError("err_book_name_required", "BookName is required", field="book_name")

    author = clean_persian_text(payload.get("author", existing.author if existing else ""))
    genre = clean_persian_text(payload.get("genre", existing.genre if existing else ""))
    description = coerce_text(payload.get("description", existing.description if existing else ""))
    storage = clean_persian_text(payload.get("storage", existing.storage if existing else ""))
    if not storage:
        raise ValidationError("err_storage_required", "Storage is required", field="storage")

    floor = parse_optional_int(
        payload.get("floor", existing.floor if existing else None),
        field="floor",
        min_val=1,
        max_val=50,
    )
    row = parse_optional_int(
        payload.get("row", existing.row if existing else None),
        field="row",
        min_val=1,
        max_val=100,
    )
    status = BookStatus.normalize(payload.get("status", existing.status.value if existing else BookStatus.UNREAD.value))
    rating = parse_optional_rating(payload.get("rating", existing.rating if existing else None))

    raw_date_added = payload.get("date_added", existing.date_added if existing else "")
    try:
        date_added = parse_flexible_date(raw_date_added) if coerce_text(raw_date_added) else (
            existing.date_added if existing and existing.date_added else today_iso()
        )
    except ValueError as exc:
        raise ValidationError("err_invalid_date", str(exc), field="date_added") from exc

    raw_date_finished = payload.get("date_finished", existing.date_finished if existing else "")
    try:
        date_finished = parse_flexible_date(raw_date_finished) if coerce_text(raw_date_finished) else ""
    except ValueError as exc:
        raise ValidationError("err_invalid_date", str(exc), field="date_finished") from exc

    # Automatically stamp DateFinished when user marks a book Finished without supplying a date
    if status == BookStatus.FINISHED and not date_finished:
        date_finished = today_iso()

    cover_path = coerce_text(payload.get("cover_path", existing.cover_path if existing else ""))
    notes = coerce_text(payload.get("notes", existing.notes if existing else ""))

    return {
        "book_name": book_name,
        "author": author,
        "genre": genre,
        "description": description,
        "storage": storage,
        "floor": floor,
        "row": row,
        "status": status,
        "rating": rating,
        "date_added": date_added,
        "date_finished": date_finished,
        "cover_path": cover_path,
        "notes": notes,
    }
