from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from library_app.utils.jalali import format_jalali_long, format_jalali_short
from library_app.utils.persian import split_genres


class BookStatus(str, Enum):
    UNREAD = "Unread"
    READING = "Reading"
    FINISHED = "Finished"
    DROPPED = "Dropped"

    @classmethod
    def normalize(cls, raw: object) -> BookStatus:
        if isinstance(raw, BookStatus):
            return raw
        text = str(raw or "").strip().lower()
        mapping = {
            "unread": cls.UNREAD,
            "خوانده‌نشده": cls.UNREAD,
            "خوانده نشده": cls.UNREAD,
            "reading": cls.READING,
            "در حال خواندن": cls.READING,
            "finished": cls.FINISHED,
            "خوانده‌شده": cls.FINISHED,
            "خوانده شده": cls.FINISHED,
            "dropped": cls.DROPPED,
            "رهاشده": cls.DROPPED,
            "رها شده": cls.DROPPED,
        }
        return mapping.get(text, cls.UNREAD)


@dataclass(slots=True)
class Book:
    id: int
    book_name: str
    author: str = ""
    genre: str = ""
    description: str = ""
    storage: str = ""
    floor: int | None = None
    row: int | None = None
    status: BookStatus = BookStatus.UNREAD
    rating: float | None = None
    date_added: str = ""
    date_finished: str = ""
    cover_path: str = ""
    notes: str = ""

    def to_excel_row(self) -> dict[str, Any]:
        return {
            "ID": self.id,
            "BookName": self.book_name,
            "Author": self.author or None,
            "Genre": self.genre or None,
            "Description": self.description or None,
            "Storage": self.storage or None,
            "Floor": self.floor,
            "Row": self.row,
            "Status": self.status.value,
            "Rating": self.rating,
            "DateAdded": self.date_added or None,
            "DateFinished": self.date_finished or None,
            "CoverPath": self.cover_path or None,
            "Notes": self.notes or None,
        }

    def to_dict(self, score: float | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "book_name": self.book_name,
            "author": self.author,
            "genre": self.genre,
            "genre_tags": split_genres(self.genre),
            "description": self.description,
            "storage": self.storage,
            "floor": self.floor,
            "row": self.row,
            "status": self.status.value,
            "rating": self.rating,
            "date_added": self.date_added,
            "date_added_jalali": format_jalali_short(self.date_added),
            "date_added_jalali_long": format_jalali_long(self.date_added),
            "date_finished": self.date_finished,
            "date_finished_jalali": format_jalali_short(self.date_finished),
            "date_finished_jalali_long": format_jalali_long(self.date_finished),
            "cover_path": self.cover_path,
            "notes": self.notes,
        }
        if score is not None:
            data["search_score"] = round(score, 2)
        return data


@dataclass(slots=True)
class BookFilter:
    query: str = ""
    storage: str = ""
    floor: int | None = None
    row: int | None = None
    genre: str = ""
    status: str = ""
    rating_filter: str = ""  # "", "rated", "unrated", "4plus", "5"
    sort_by: str = "id"
    sort_dir: str = "desc"


@dataclass(slots=True)
class HygieneIssue:
    book_id: int
    book_name: str
    issue_type: str
    field: str
    current_value: str
    suggested_value: str
    auto_fixable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "book_id": self.book_id,
            "book_name": self.book_name,
            "issue_type": self.issue_type,
            "field": self.field,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "auto_fixable": self.auto_fixable,
        }


@dataclass(slots=True)
class HygieneReport:
    total_books: int
    issue_counts: dict[str, int] = field(default_factory=dict)
    issues: list[HygieneIssue] = field(default_factory=list)
    duplicate_groups: list[list[dict[str, Any]]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_books": self.total_books,
            "total_issues": len(self.issues),
            "auto_fixable_count": sum(1 for item in self.issues if item.auto_fixable),
            "issue_counts": self.issue_counts,
            "issues": [item.to_dict() for item in self.issues],
            "duplicate_groups": self.duplicate_groups,
        }
