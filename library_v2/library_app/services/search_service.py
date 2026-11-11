from __future__ import annotations

from rapidfuzz import fuzz

from library_app.domain.models import Book, BookFilter, BookStatus
from library_app.utils.persian import (
    compact_for_search,
    normalize_for_search,
    persian_sort_key,
    split_genres,
)


def score_book_match(book: Book, query: str) -> float:
    """Compute weighted Persian+English hybrid exact/token/fuzzy relevance score (0-150)."""
    norm_q = normalize_for_search(query)
    if not norm_q:
        return 1.0

    compact_q = compact_for_search(query)
    tokens = [tok for tok in norm_q.split(" ") if tok]

    norm_title = normalize_for_search(book.book_name)
    compact_title = compact_for_search(book.book_name)
    norm_author = normalize_for_search(book.author)
    compact_author = compact_for_search(book.author)
    norm_genre = normalize_for_search(book.genre)
    compact_genre = compact_for_search(book.genre)
    norm_storage = normalize_for_search(book.storage)
    compact_storage = compact_for_search(book.storage)
    norm_desc = normalize_for_search(book.description)
    compact_desc = compact_for_search(book.description)
    norm_notes = normalize_for_search(book.notes)
    compact_notes = compact_for_search(book.notes)

    score = 0.0

    # Numeric ID quick lookup (e.g. searching "145" or "۱۴۵")
    if norm_q.isdigit() and int(norm_q) == book.id:
        score = max(score, 145.0)

    # Exact / prefix / substring matches on Title
    if norm_title:
        if norm_q == norm_title or (compact_q and compact_q == compact_title):
            score = max(score, 140.0)
        elif norm_title.startswith(norm_q) or (compact_q and compact_title.startswith(compact_q)):
            score = max(score, 125.0)
        elif norm_q in norm_title:
            score = max(score, 110.0)
        elif compact_q and compact_q in compact_title:
            score = max(score, 102.0)

    # Substring matches on Author
    if norm_author:
        if norm_q == norm_author:
            score = max(score, 105.0)
        elif norm_q in norm_author:
            score = max(score, 90.0)
        elif compact_q and compact_q in compact_author:
            score = max(score, 85.0)

    # Substring matches on Genre / Storage
    if norm_genre and (norm_q in norm_genre or (compact_q and compact_q in compact_genre)):
        score = max(score, 76.0)
    if norm_storage and (norm_q in norm_storage or (compact_q and compact_q in compact_storage)):
        score = max(score, 68.0)

    # Substring matches on Description / Notes
    if norm_desc and (norm_q in norm_desc or (compact_q and compact_q in compact_desc)):
        score = max(score, 60.0)
    if norm_notes and (norm_q in norm_notes or (compact_q and compact_q in compact_notes)):
        score = max(score, 58.0)

    # Multi-token AND match across combined metadata
    if len(tokens) > 1:
        combined = " ".join(
            part
            for part in (norm_title, norm_author, norm_genre, norm_storage, norm_desc, norm_notes)
            if part
        )
        if all(tok in combined for tok in tokens):
            score = max(score, 88.0)

    # Fuzzy fallback (handles typos & partial Persian stems without noisy cross-word false positives)
    if score == 0.0 and len(compact_q) >= 3:
        def safe_fuzzy(q_norm: str, q_compact: str, field_norm: str, field_compact: str) -> float:
            if not field_norm:
                return 0.0
            if len(tokens) > 1:
                return float(fuzz.token_set_ratio(q_norm, field_norm))
            token_best = max((float(fuzz.ratio(q_norm, tok)) for tok in field_norm.split()), default=0.0)
            whole_ratio = float(fuzz.ratio(q_compact, field_compact))
            return max(token_best, whole_ratio)

        title_fuzz = safe_fuzzy(norm_q, compact_q, norm_title, compact_title)
        author_fuzz = safe_fuzzy(norm_q, compact_q, norm_author, compact_author)
        genre_fuzz = float(fuzz.ratio(compact_q, compact_genre)) if compact_genre else 0.0

        min_thresh = 80.0 if len(compact_q) <= 5 else 76.0
        best_raw = max(title_fuzz, author_fuzz, genre_fuzz)
        if best_raw >= min_thresh:
            score = max(title_fuzz * 0.72, author_fuzz * 0.65, genre_fuzz * 0.55)

    return score


def _matches_filters(book: Book, book_filter: BookFilter) -> bool:
    if (
        book_filter.storage
        and book_filter.storage != "All"
        and normalize_for_search(book.storage) != normalize_for_search(book_filter.storage)
    ):
        return False

    if book_filter.floor is not None and book.floor != book_filter.floor:
        return False

    if book_filter.row is not None and book.row != book_filter.row:
        return False

    if book_filter.status and book_filter.status != "All":
        target_status = BookStatus.normalize(book_filter.status)
        if book.status != target_status:
            return False

    if book_filter.genre and book_filter.genre != "All":
        target_genre = normalize_for_search(book_filter.genre)
        book_genres = {normalize_for_search(tag) for tag in split_genres(book.genre)}
        if target_genre not in book_genres:
            return False

    if book_filter.rating_filter:
        rf = book_filter.rating_filter
        rating = book.rating
        if rf == "rated" and (rating is None or rating <= 0):
            return False
        if rf == "unrated" and (rating is not None and rating > 0):
            return False
        if rf == "4plus" and (rating is None or rating < 4.0):
            return False
        if rf == "5" and (rating is None or rating < 5.0):
            return False

    return True


def _sort_results(items: list[tuple[Book, float]], sort_by: str, sort_dir: str) -> list[tuple[Book, float]]:
    reverse = sort_dir.lower() == "desc"

    if sort_by == "relevance":
        return sorted(items, key=lambda pair: (pair[1], pair[0].id), reverse=True)

    if sort_by == "id":
        return sorted(items, key=lambda pair: pair[0].id, reverse=reverse)

    if sort_by in {"floor", "row", "rating"}:
        def num_key(pair: tuple[Book, float]) -> tuple[int, float]:
            val = getattr(pair[0], sort_by)
            if val is None:
                return (1, 0.0)
            return (0, float(val) * (-1 if reverse else 1))

        # Keep nulls always at the bottom regardless of asc/desc
        return sorted(items, key=lambda pair: (num_key(pair)[0], num_key(pair)[1], pair[0].id))

    if sort_by in {"book_name", "author", "genre", "storage", "status", "date_added", "date_finished"}:
        def text_key(pair: tuple[Book, float]) -> tuple[int, str, int]:
            val = getattr(pair[0], sort_by)
            if isinstance(val, BookStatus):
                val = val.value
            empty_flag, norm = persian_sort_key(val)
            return (empty_flag, norm, pair[0].id)

        non_empty = [pair for pair in items if text_key(pair)[0] == 0]
        empty = [pair for pair in items if text_key(pair)[0] == 1]
        non_empty.sort(key=text_key, reverse=reverse)
        return non_empty + empty

    return sorted(items, key=lambda pair: pair[0].id, reverse=reverse)


def search_and_filter_books(books: list[Book], book_filter: BookFilter) -> list[tuple[Book, float]]:
    """Run Persian-aware search, dynamic filtering, and safe sorting."""
    has_query = bool(normalize_for_search(book_filter.query))
    matched: list[tuple[Book, float]] = []

    for book in books:
        if not _matches_filters(book, book_filter):
            continue
        if has_query:
            score = score_book_match(book, book_filter.query)
            if score <= 0.0:
                continue
            matched.append((book, score))
        else:
            matched.append((book, 1.0))

    effective_sort = book_filter.sort_by or ("relevance" if has_query else "id")
    if has_query and book_filter.sort_by == "id" and book_filter.sort_dir == "desc":
        # Default to relevance when user types a search query without overriding sort
        effective_sort = "relevance"

    return _sort_results(matched, effective_sort, book_filter.sort_dir)
