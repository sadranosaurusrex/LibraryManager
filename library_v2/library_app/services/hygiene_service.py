from __future__ import annotations

from collections import Counter, defaultdict
from copy import copy

from library_app.domain.models import Book, BookStatus, HygieneIssue, HygieneReport
from library_app.repository.excel_repository import ExcelRepository
from library_app.utils.persian import clean_persian_text, compact_for_search


def scan_library_hygiene(books: list[Book], raw_statuses: dict[int, str] | None = None) -> HygieneReport:
    """Inspect library data for Arabic variants, whitespace issues, status casing, missing fields, and duplicates."""
    issues: list[HygieneIssue] = []
    counts: Counter[str] = Counter()
    dup_buckets: dict[tuple[str, str], list[Book]] = defaultdict(list)

    for book in books:
        # 1. Persian/Arabic char & extra whitespace checks
        for field_name in ("book_name", "author", "genre", "storage"):
            val = getattr(book, field_name)
            if not val:
                continue
            cleaned = clean_persian_text(val)
            if cleaned != val:
                issues.append(
                    HygieneIssue(
                        book_id=book.id,
                        book_name=book.book_name,
                        issue_type="persian_normalization",
                        field=field_name,
                        current_value=val,
                        suggested_value=cleaned,
                        auto_fixable=True,
                    )
                )
                counts["persian_normalization"] += 1

        # 2. Status casing / standardization check
        if raw_statuses and book.id in raw_statuses:
            raw_st = raw_statuses[book.id]
            canonical = book.status.value
            if raw_st != canonical:
                issues.append(
                    HygieneIssue(
                        book_id=book.id,
                        book_name=book.book_name,
                        issue_type="status_casing",
                        field="status",
                        current_value=raw_st,
                        suggested_value=canonical,
                        auto_fixable=True,
                    )
                )
                counts["status_casing"] += 1

        # 3. Missing physical coordinates
        if book.floor is None or book.row is None:
            issues.append(
                HygieneIssue(
                    book_id=book.id,
                    book_name=book.book_name,
                    issue_type="missing_location",
                    field="floor_row",
                    current_value=f"Floor={book.floor}, Row={book.row}",
                    suggested_value="",
                    auto_fixable=False,
                )
            )
            counts["missing_location"] += 1

        # 4. Missing Author / Genre
        if not book.author:
            counts["missing_author"] += 1
        if not book.genre:
            counts["missing_genre"] += 1

        # 5. Potential duplicates (normalized Title + Author)
        title_key = compact_for_search(book.book_name)
        author_key = compact_for_search(book.author)
        if title_key:
            dup_buckets[(title_key, author_key)].append(book)

    duplicate_groups: list[list[dict[str, object]]] = []
    for group in dup_buckets.values():
        if len(group) > 1:
            counts["duplicates"] += len(group)
            duplicate_groups.append(
                [
                    {
                        "id": b.id,
                        "book_name": b.book_name,
                        "author": b.author,
                        "storage": b.storage,
                        "floor": b.floor,
                        "row": b.row,
                    }
                    for b in group
                ]
            )

    return HygieneReport(
        total_books=len(books),
        issue_counts=dict(counts),
        issues=issues,
        duplicate_groups=duplicate_groups,
    )


def apply_safe_hygiene_fixes(repo: ExcelRepository) -> dict[str, int]:
    """Normalize Arabic ي/ك, extra whitespace, and status casing safely with automatic backup."""
    books = repo.get_all_books()
    raw_statuses = repo.get_raw_statuses()

    fixed_text_fields = 0
    fixed_statuses = 0
    touched_books = 0

    cleaned_books: list[Book] = []
    for book in books:
        nb = copy(book)
        book_changed = False

        for field_name in ("book_name", "author", "genre", "storage"):
            old_val = getattr(nb, field_name)
            if old_val:
                new_val = clean_persian_text(old_val)
                if new_val != old_val:
                    setattr(nb, field_name, new_val)
                    fixed_text_fields += 1
                    book_changed = True

        raw_st = raw_statuses.get(nb.id, nb.status.value)
        canonical_status = BookStatus.normalize(raw_st)
        if raw_st != canonical_status.value:
            nb.status = canonical_status
            fixed_statuses += 1
            book_changed = True

        if book_changed:
            touched_books += 1
        cleaned_books.append(nb)

    if touched_books > 0:
        repo.replace_all_books(cleaned_books, reason="hygiene_normalize")

    return {
        "touched_books": touched_books,
        "fixed_text_fields": fixed_text_fields,
        "fixed_statuses": fixed_statuses,
    }
