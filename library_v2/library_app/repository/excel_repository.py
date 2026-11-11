from __future__ import annotations

import datetime as dt
import io
import os
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from library_app.config import REQUIRED_COLUMNS, AppConfig
from library_app.domain.models import Book, BookStatus
from library_app.domain.validation import (
    ValidationError,
    parse_optional_int,
    parse_optional_rating,
)
from library_app.utils.jalali import parse_flexible_date
from library_app.utils.persian import coerce_text

ALLOWED_COVER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class ExcelFileLockedError(RuntimeError):
    """Raised when the Excel file is locked by another program (e.g. Microsoft Excel)."""


class ExcelRepository:
    """Thread-safe, backup-protected Excel repository compatible with Books_v2.xlsx."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.excel_path = config.excel_path
        self.backup_dir = config.backup_dir
        self.covers_dir = config.covers_dir
        self._lock = threading.RLock()
        self._cached_sig: tuple[int, int] | None = None
        self._cached_books: list[Book] = []
        self._cached_raw_statuses: dict[int, str] = {}

    def _file_signature(self) -> tuple[int, int] | None:
        if not self.excel_path.exists():
            return None
        stat = self.excel_path.stat()
        return (stat.st_mtime_ns, stat.st_size)

    def _ensure_excel_exists(self) -> None:
        if self.excel_path.exists():
            return
        self.excel_path.parent.mkdir(parents=True, exist_ok=True)
        empty_df = pd.DataFrame(columns=list(REQUIRED_COLUMNS))
        self._atomic_write_df(empty_df)

    def _row_to_book(self, row: dict[str, Any], fallback_id: int) -> tuple[Book, str]:
        raw_id = parse_optional_int(row.get("ID"), min_val=1, max_val=10_000_000)
        book_id = raw_id if raw_id is not None else fallback_id

        try:
            floor = parse_optional_int(row.get("Floor"), min_val=1, max_val=999)
        except ValidationError:
            floor = None

        try:
            book_row = parse_optional_int(row.get("Row"), min_val=1, max_val=999)
        except ValidationError:
            book_row = None

        try:
            rating = parse_optional_rating(row.get("Rating"))
        except ValidationError:
            rating = None

        raw_status = coerce_text(row.get("Status"))
        status = BookStatus.normalize(raw_status)

        raw_date_added = row.get("DateAdded")
        try:
            date_added = parse_flexible_date(raw_date_added)
        except ValueError:
            date_added = coerce_text(raw_date_added)

        raw_date_finished = row.get("DateFinished")
        try:
            date_finished = parse_flexible_date(raw_date_finished)
        except ValueError:
            date_finished = coerce_text(raw_date_finished)

        book = Book(
            id=book_id,
            book_name=coerce_text(row.get("BookName")),
            author=coerce_text(row.get("Author")),
            genre=coerce_text(row.get("Genre")),
            description=coerce_text(row.get("Description")),
            storage=coerce_text(row.get("Storage")),
            floor=floor,
            row=book_row,
            status=status,
            rating=rating,
            date_added=date_added,
            date_finished=date_finished,
            cover_path=coerce_text(row.get("CoverPath")),
            notes=coerce_text(row.get("Notes")),
        )
        return book, raw_status

    def _reload_cache_unlocked(self) -> None:
        if not self.excel_path.exists():
            self._cached_sig = None
            self._cached_books = []
            self._cached_raw_statuses = {}
            return

        df = pd.read_excel(self.excel_path, engine="openpyxl")
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                df[col] = None

        books: list[Book] = []
        raw_statuses: dict[int, str] = {}
        seen_ids: set[int] = set()
        next_fallback = 1

        records = df.to_dict(orient="records")
        for record in records:
            str_record = {str(k): v for k, v in record.items()}
            while next_fallback in seen_ids:
                next_fallback += 1
            book, raw_status = self._row_to_book(str_record, next_fallback)
            if not book.book_name and not book.author and not book.storage:
                continue
            if book.id in seen_ids:
                while next_fallback in seen_ids:
                    next_fallback += 1
                book.id = next_fallback
            seen_ids.add(book.id)
            books.append(book)
            raw_statuses[book.id] = raw_status

        self._cached_books = books
        self._cached_raw_statuses = raw_statuses
        self._cached_sig = self._file_signature()

    def _get_books_unlocked(self) -> list[Book]:
        sig = self._file_signature()
        if sig != self._cached_sig:
            self._reload_cache_unlocked()
        return list(self._cached_books)

    def create_backup(self, reason: str = "manual") -> Path | None:
        with self._lock:
            if not self.excel_path.exists():
                return None
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
            safe_reason = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in reason)
            backup_name = f"{self.excel_path.stem}_backup_{stamp}_{safe_reason}.xlsx"
            backup_path = self.backup_dir / backup_name
            shutil.copy2(self.excel_path, backup_path)
            self._prune_backups_unlocked()
            return backup_path

    def _prune_backups_unlocked(self) -> None:
        if not self.backup_dir.exists():
            return
        backups = sorted(
            self.backup_dir.glob(f"{self.excel_path.stem}_backup_*.xlsx"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in backups[self.config.max_backups :]:
            old.unlink(missing_ok=True)

    def list_backups(self) -> list[dict[str, Any]]:
        with self._lock:
            if not self.backup_dir.exists():
                return []
            backups = sorted(
                self.backup_dir.glob(f"{self.excel_path.stem}_backup_*.xlsx"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            result: list[dict[str, Any]] = []
            for item in backups:
                st = item.stat()
                result.append(
                    {
                        "name": item.name,
                        "size_bytes": st.st_size,
                        "modified_at": dt.datetime.fromtimestamp(
                            st.st_mtime, tz=dt.timezone.utc
                        ).astimezone().isoformat(timespec="seconds"),
                    }
                )
            return result

    def _atomic_write_df(self, df: pd.DataFrame) -> None:
        self.excel_path.parent.mkdir(parents=True, exist_ok=True)
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[list(REQUIRED_COLUMNS)]

        tmp_name = f".{self.excel_path.stem}.{uuid.uuid4().hex}.tmp.xlsx"
        tmp_path = self.excel_path.parent / tmp_name
        try:
            df.to_excel(tmp_path, index=False, engine="openpyxl")
            os.replace(tmp_path, self.excel_path)
        except PermissionError as exc:
            tmp_path.unlink(missing_ok=True)
            raise ExcelFileLockedError("Excel file is locked by another process.") from exc
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    def _save_books_unlocked(self, books: list[Book], *, reason: str) -> None:
        if self.excel_path.exists():
            self.create_backup(reason=reason)
        rows = [book.to_excel_row() for book in books]
        df = pd.DataFrame(rows, columns=list(REQUIRED_COLUMNS))
        self._atomic_write_df(df)
        self._cached_books = list(books)
        self._cached_raw_statuses = {b.id: b.status.value for b in books}
        self._cached_sig = self._file_signature()

    def get_all_books(self) -> list[Book]:
        with self._lock:
            return self._get_books_unlocked()

    def get_raw_statuses(self) -> dict[int, str]:
        with self._lock:
            self._get_books_unlocked()
            return dict(self._cached_raw_statuses)

    def get_book(self, book_id: int) -> Book | None:
        with self._lock:
            for book in self._get_books_unlocked():
                if book.id == book_id:
                    return book
            return None

    def add_book(self, clean_data: dict[str, Any]) -> Book:
        with self._lock:
            books = self._get_books_unlocked()
            next_id = max((b.id for b in books), default=0) + 1
            new_book = Book(
                id=next_id,
                book_name=clean_data["book_name"],
                author=clean_data["author"],
                genre=clean_data["genre"],
                description=clean_data["description"],
                storage=clean_data["storage"],
                floor=clean_data["floor"],
                row=clean_data["row"],
                status=clean_data["status"],
                rating=clean_data["rating"],
                date_added=clean_data["date_added"],
                date_finished=clean_data["date_finished"],
                cover_path=clean_data["cover_path"],
                notes=clean_data["notes"],
            )
            books.append(new_book)
            self._save_books_unlocked(books, reason="add")
            return new_book

    def update_book(self, book_id: int, clean_data: dict[str, Any]) -> Book | None:
        with self._lock:
            books = self._get_books_unlocked()
            updated_book: Book | None = None
            new_list: list[Book] = []
            for book in books:
                if book.id == book_id:
                    updated_book = Book(
                        id=book_id,
                        book_name=clean_data["book_name"],
                        author=clean_data["author"],
                        genre=clean_data["genre"],
                        description=clean_data["description"],
                        storage=clean_data["storage"],
                        floor=clean_data["floor"],
                        row=clean_data["row"],
                        status=clean_data["status"],
                        rating=clean_data["rating"],
                        date_added=clean_data["date_added"],
                        date_finished=clean_data["date_finished"],
                        cover_path=clean_data["cover_path"],
                        notes=clean_data["notes"],
                    )
                    new_list.append(updated_book)
                else:
                    new_list.append(book)
            if updated_book is None:
                return None
            self._save_books_unlocked(new_list, reason="update")
            return updated_book

    def delete_book(self, book_id: int) -> Book | None:
        with self._lock:
            books = self._get_books_unlocked()
            deleted: Book | None = None
            remaining: list[Book] = []
            for book in books:
                if book.id == book_id:
                    deleted = book
                else:
                    remaining.append(book)
            if deleted is None:
                return None
            self._save_books_unlocked(remaining, reason="delete")
            return deleted

    def replace_all_books(self, books: list[Book], reason: str = "hygiene") -> None:
        with self._lock:
            self._save_books_unlocked(books, reason=reason)

    def restore_backup(self, backup_name: str) -> bool:
        with self._lock:
            safe_name = Path(backup_name).name
            source = (self.backup_dir / safe_name).resolve()
            if not source.exists() or source.parent != self.backup_dir.resolve():
                return False
            if self.excel_path.exists():
                self.create_backup(reason="pre_restore")
            shutil.copy2(source, self.excel_path)
            self._cached_sig = None
            self._reload_cache_unlocked()
            return True

    def save_cover_image(self, book_id: int, original_filename: str, content: bytes) -> str:
        ext = Path(original_filename).suffix.lower()
        if ext not in ALLOWED_COVER_EXTENSIONS:
            raise ValidationError("err_invalid_cover_type", f"Unsupported image extension: {ext}", field="cover")
        if len(content) > 8 * 1024 * 1024:
            raise ValidationError("err_cover_too_large", "Cover exceeds 8MB", field="cover")
        self.covers_dir.mkdir(parents=True, exist_ok=True)
        unique_name = f"book_{book_id}_{uuid.uuid4().hex[:8]}{ext}"
        target = self.covers_dir / unique_name
        target.write_bytes(content)
        return f"covers/{unique_name}"

    def resolve_cover_file(self, cover_ref: str) -> Path | None:
        ref = coerce_text(cover_ref)
        if not ref:
            return None
        candidate = Path(ref)
        if not candidate.is_absolute():
            if ref.startswith("covers/"):
                candidate = self.covers_dir / ref.removeprefix("covers/")
            else:
                candidate = self.excel_path.parent / ref
        try:
            resolved = candidate.resolve()
        except OSError:
            return None
        if not resolved.exists() or not resolved.is_file():
            return None
        if resolved.suffix.lower() not in ALLOWED_COVER_EXTENSIONS:
            return None
        return resolved

    def export_csv_bytes(self, books: list[Book]) -> bytes:
        rows = [book.to_excel_row() for book in books]
        df = pd.DataFrame(rows, columns=list(REQUIRED_COLUMNS))
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        # UTF-8 with BOM so Microsoft Excel on Windows displays Persian characters properly
        return buf.getvalue().encode("utf-8-sig")

    def export_excel_bytes(self, books: list[Book]) -> bytes:
        rows = [book.to_excel_row() for book in books]
        df = pd.DataFrame(rows, columns=list(REQUIRED_COLUMNS))
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        return buf.getvalue()
