from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from library_app.config import DEFAULT_STORAGES
from library_app.domain.models import Book, BookStatus
from library_app.utils.persian import (
    clean_persian_text,
    normalize_for_search,
    split_genres,
)


def build_facets(books: list[Book]) -> dict[str, Any]:
    """Compute dynamic filter options (storages, floors, rows, genres, statuses) from live data."""
    storage_counts: Counter[str] = Counter()
    floors: set[int] = set()
    rows: set[int] = set()
    genre_counts: Counter[str] = Counter()
    genre_display: dict[str, str] = {}

    for book in books:
        if book.storage:
            storage_counts[clean_persian_text(book.storage)] += 1
        if book.floor is not None:
            floors.add(book.floor)
        if book.row is not None:
            rows.add(book.row)
        for tag in split_genres(book.genre):
            key = normalize_for_search(tag)
            if key not in genre_display:
                genre_display[key] = tag
            genre_counts[key] += 1

    # Merge default storages so user always sees standard presets + any custom ones from Excel
    all_storages = sorted(
        set(storage_counts.keys()) | set(DEFAULT_STORAGES),
        key=lambda s: (-storage_counts.get(s, 0), s),
    )

    genres_sorted = [
        {"name": genre_display[key], "count": count}
        for key, count in genre_counts.most_common()
    ]

    return {
        "storages": [{"name": s, "count": storage_counts.get(s, 0)} for s in all_storages],
        "floors": sorted(floors),
        "rows": sorted(rows),
        "genres": genres_sorted,
        "statuses": [status.value for status in BookStatus],
    }


def build_analytics(books: list[Book]) -> dict[str, Any]:
    """Generate library analytics and physical shelf map grouped by Storage -> Floor -> Row."""
    total = len(books)
    status_counts: Counter[str] = Counter()
    storage_counts: Counter[str] = Counter()
    genre_counts: Counter[str] = Counter()
    genre_display: dict[str, str] = {}
    author_counts: Counter[str] = Counter()
    author_display: dict[str, str] = {}
    ratings: list[float] = []
    rating_buckets: Counter[int] = Counter()

    # Physical map: storage -> floor -> row -> list of lightweight book dicts
    shelf_slots: dict[str, dict[int, dict[int, list[dict[str, Any]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    unplaced_in_storage: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for book in books:
        status_counts[book.status.value] += 1
        storage_name = clean_persian_text(book.storage) or "نامشخص"
        storage_counts[storage_name] += 1

        if book.author:
            akey = normalize_for_search(book.author)
            if akey not in author_display:
                author_display[akey] = clean_persian_text(book.author)
            author_counts[akey] += 1

        for tag in split_genres(book.genre):
            gkey = normalize_for_search(tag)
            if gkey not in genre_display:
                genre_display[gkey] = tag
            genre_counts[gkey] += 1

        if book.rating is not None and book.rating > 0:
            ratings.append(book.rating)
            rating_buckets[round(book.rating)] += 1

        slot_item = {
            "id": book.id,
            "book_name": book.book_name,
            "author": book.author,
            "status": book.status.value,
            "rating": book.rating,
        }
        if book.floor is not None and book.row is not None:
            shelf_slots[storage_name][book.floor][book.row].append(slot_item)
        else:
            unplaced_in_storage[storage_name].append(slot_item)

    finished_count = status_counts.get(BookStatus.FINISHED.value, 0)
    reading_count = status_counts.get(BookStatus.READING.value, 0)
    unread_count = status_counts.get(BookStatus.UNREAD.value, 0)
    dropped_count = status_counts.get(BookStatus.DROPPED.value, 0)

    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
    completion_rate = round((finished_count / total) * 100, 1) if total else 0.0

    # Format shelf map cleanly
    shelf_map: list[dict[str, Any]] = []
    for storage_name, count in storage_counts.most_common():
        floors_dict = shelf_slots.get(storage_name, {})
        floors_list: list[dict[str, Any]] = []
        for floor_num in sorted(floors_dict.keys()):
            rows_dict = floors_dict[floor_num]
            rows_list: list[dict[str, Any]] = []
            for row_num in sorted(rows_dict.keys()):
                slot_books = rows_dict[row_num]
                rows_list.append(
                    {
                        "row": row_num,
                        "count": len(slot_books),
                        "books": slot_books,
                    }
                )
            floors_list.append(
                {
                    "floor": floor_num,
                    "count": sum(r["count"] for r in rows_list),
                    "rows": rows_list,
                }
            )
        shelf_map.append(
            {
                "storage": storage_name,
                "total_books": count,
                "floors": floors_list,
                "unplaced_books": unplaced_in_storage.get(storage_name, []),
            }
        )

    return {
        "kpis": {
            "total_books": total,
            "finished_books": finished_count,
            "reading_books": reading_count,
            "unread_books": unread_count,
            "dropped_books": dropped_count,
            "completion_rate": completion_rate,
            "rated_books": len(ratings),
            "average_rating": avg_rating,
            "unique_authors": len(author_counts),
            "unique_genres": len(genre_counts),
            "unique_storages": len(storage_counts),
        },
        "by_status": [
            {"status": status.value, "count": status_counts.get(status.value, 0)}
            for status in BookStatus
        ],
        "by_storage": [
            {"storage": name, "count": count} for name, count in storage_counts.most_common()
        ],
        "top_genres": [
            {"genre": genre_display[k], "count": count} for k, count in genre_counts.most_common(14)
        ],
        "top_authors": [
            {"author": author_display[k], "count": count} for k, count in author_counts.most_common(10)
        ],
        "rating_distribution": [
            {"stars": star, "count": rating_buckets.get(star, 0)} for star in range(5, 0, -1)
        ],
        "shelf_map": shelf_map,
    }
