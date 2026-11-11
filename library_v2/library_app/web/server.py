from __future__ import annotations

import base64
import json
import math
import mimetypes
import threading
import urllib.parse
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from library_app.config import AppConfig
from library_app.domain.models import BookFilter
from library_app.domain.validation import (
    ValidationError,
    parse_optional_int,
    validate_book_payload,
)
from library_app.i18n import TRANSLATIONS
from library_app.repository.excel_repository import (
    ExcelFileLockedError,
    ExcelRepository,
)
from library_app.services.analytics_service import build_analytics, build_facets
from library_app.services.hygiene_service import (
    apply_safe_hygiene_fixes,
    scan_library_hygiene,
)
from library_app.services.search_service import search_and_filter_books
from library_app.utils.jalali import format_jalali_long, format_jalali_short, today_iso

STATIC_DIR = Path(__file__).resolve().parent / "static"


class LibraryAppState:
    def __init__(self, config: AppConfig, repo: ExcelRepository) -> None:
        self.config = config
        self.repo = repo


def _parse_filter_params(query_params: dict[str, list[str]]) -> tuple[BookFilter, int, int, bool]:
    def first(key: str, default: str = "") -> str:
        vals = query_params.get(key)
        return vals[0] if vals else default

    floor_val: int | None = None
    raw_floor = first("floor")
    if raw_floor:
        try:
            floor_val = parse_optional_int(raw_floor, field="floor", min_val=1, max_val=999)
        except ValidationError:
            floor_val = None

    row_val: int | None = None
    raw_row = first("row")
    if raw_row:
        try:
            row_val = parse_optional_int(raw_row, field="row", min_val=1, max_val=999)
        except ValidationError:
            row_val = None

    book_filter = BookFilter(
        query=first("q"),
        storage=first("storage"),
        floor=floor_val,
        row=row_val,
        genre=first("genre"),
        status=first("status"),
        rating_filter=first("rating"),
        sort_by=first("sort_by", "id"),
        sort_dir=first("sort_dir", "desc"),
    )

    try:
        page = max(1, int(first("page", "1")))
    except ValueError:
        page = 1

    try:
        per_page = max(1, min(500, int(first("per_page", "50"))))
    except ValueError:
        per_page = 50

    show_all = first("all") in {"1", "true", "yes"}
    return book_filter, page, per_page, show_all


class LibraryRequestHandler(BaseHTTPRequestHandler):
    server_version = "LibraryStudio/2.0"

    def __init__(self, *args: Any, state: LibraryAppState, **kwargs: Any) -> None:
        self.state = state
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy per-request console logs during normal interactive/test runs
        return

    def _send_json(self, status: int, payload: Any) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _send_bytes(
        self,
        status: int,
        content_type: str,
        data: bytes,
        *,
        download_filename: str | None = None,
        cache_control: str = "no-cache",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache_control)
        if download_filename:
            quoted = urllib.parse.quote(download_filename)
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quoted}")
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        if length > 16 * 1024 * 1024:
            raise ValidationError("err_cover_too_large", "Request payload too large")
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("err_invalid_json", str(exc)) from exc
        if not isinstance(parsed, dict):
            raise ValidationError("err_invalid_json", "JSON object expected")
        return parsed

    def _serve_static_file(self, rel_path: str) -> None:
        cleaned = rel_path.lstrip("/")
        if not cleaned:
            cleaned = "index.html"
        target = (STATIC_DIR / cleaned).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.exists() or not target.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        mime, _ = mimetypes.guess_type(str(target))
        content_type = mime or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "text/javascript"}:
            content_type = f"{content_type}; charset=utf-8"
        self._send_bytes(HTTPStatus.OK, content_type, target.read_bytes())

    def _serve_cover_file(self, cover_subpath: str) -> None:
        decoded = urllib.parse.unquote(cover_subpath).lstrip("/")
        resolved = self.state.repo.resolve_cover_file(decoded)
        if resolved is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "cover_not_found"})
            return
        mime, _ = mimetypes.guess_type(str(resolved))
        self._send_bytes(
            HTTPStatus.OK,
            mime or "application/octet-stream",
            resolved.read_bytes(),
            cache_control="max-age=3600",
        )

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_static_file("index.html")
            return

        if path.startswith("/static/"):
            self._serve_static_file(path.removeprefix("/static/"))
            return

        if path.startswith("/api/covers/"):
            self._serve_cover_file(path.removeprefix("/api/covers/"))
            return

        if path == "/api/health":
            books = self.state.repo.get_all_books()
            today = today_iso()
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "excel_path": str(self.state.config.excel_path),
                    "total_books": len(books),
                    "today_iso": today,
                    "today_jalali": format_jalali_short(today),
                    "today_jalali_long": format_jalali_long(today),
                },
            )
            return

        if path == "/api/i18n":
            self._send_json(
                HTTPStatus.OK,
                {
                    "default_lang": self.state.config.default_lang,
                    "translations": TRANSLATIONS,
                },
            )
            return

        if path == "/api/books":
            all_books = self.state.repo.get_all_books()
            facets = build_facets(all_books)
            book_filter, page, per_page, show_all = _parse_filter_params(query)
            results = search_and_filter_books(all_books, book_filter)
            total_filtered = len(results)

            if show_all:
                paged = results
                total_pages = 1
                page = 1
            else:
                total_pages = max(1, math.ceil(total_filtered / per_page))
                page = min(page, total_pages)
                start = (page - 1) * per_page
                paged = results[start : start + per_page]

            has_query = bool(book_filter.query.strip())
            items = [
                book.to_dict(score=score if has_query else None) for book, score in paged
            ]
            self._send_json(
                HTTPStatus.OK,
                {
                    "items": items,
                    "total_filtered": total_filtered,
                    "total_books": len(all_books),
                    "page": page,
                    "per_page": per_page if not show_all else max(1, total_filtered),
                    "total_pages": total_pages,
                    "facets": facets,
                },
            )
            return

        if path.startswith("/api/books/"):
            tail = path.removeprefix("/api/books/").strip("/")
            if tail.isdigit():
                book = self.state.repo.get_book(int(tail))
                if book is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "book_not_found"})
                    return
                self._send_json(HTTPStatus.OK, book.to_dict())
                return

        if path == "/api/analytics":
            books = self.state.repo.get_all_books()
            self._send_json(HTTPStatus.OK, build_analytics(books))
            return

        if path == "/api/hygiene":
            books = self.state.repo.get_all_books()
            raw_statuses = self.state.repo.get_raw_statuses()
            report = scan_library_hygiene(books, raw_statuses)
            self._send_json(HTTPStatus.OK, report.to_dict())
            return

        if path == "/api/backups":
            self._send_json(HTTPStatus.OK, {"backups": self.state.repo.list_backups()})
            return

        if path == "/api/export/csv":
            all_books = self.state.repo.get_all_books()
            book_filter, _, _, _ = _parse_filter_params(query)
            filtered = [book for book, _ in search_and_filter_books(all_books, book_filter)]
            csv_bytes = self.state.repo.export_csv_bytes(filtered)
            self._send_bytes(
                HTTPStatus.OK,
                "text/csv; charset=utf-8",
                csv_bytes,
                download_filename="Books_export.csv",
            )
            return

        if path == "/api/export/xlsx":
            all_books = self.state.repo.get_all_books()
            book_filter, _, _, _ = _parse_filter_params(query)
            filtered = [book for book, _ in search_and_filter_books(all_books, book_filter)]
            xlsx_bytes = self.state.repo.export_excel_bytes(filtered)
            self._send_bytes(
                HTTPStatus.OK,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                xlsx_bytes,
                download_filename="Books_export.xlsx",
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            if path == "/api/books":
                payload = self._read_json_body()
                clean = validate_book_payload(payload)
                created = self.state.repo.add_book(clean)
                self._send_json(HTTPStatus.CREATED, created.to_dict())
                return

            if path.startswith("/api/books/") and path.endswith("/cover"):
                raw_id = path.removeprefix("/api/books/").removesuffix("/cover").strip("/")
                if not raw_id.isdigit():
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_id"})
                    return
                book_id = int(raw_id)
                existing = self.state.repo.get_book(book_id)
                if existing is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "book_not_found"})
                    return
                payload = self._read_json_body()
                filename = str(payload.get("filename") or "cover.png")
                data_url = str(payload.get("data_base64") or "")
                if "," in data_url and data_url.startswith("data:"):
                    data_url = data_url.split(",", 1)[1]
                try:
                    img_bytes = base64.b64decode(data_url, validate=True)
                except Exception as exc:
                    raise ValidationError("err_invalid_cover_type", "Invalid base64 image") from exc
                cover_ref = self.state.repo.save_cover_image(book_id, filename, img_bytes)
                updated_payload = validate_book_payload({"cover_path": cover_ref}, existing=existing)
                updated = self.state.repo.update_book(book_id, updated_payload)
                self._send_json(HTTPStatus.OK, updated.to_dict() if updated else {"cover_path": cover_ref})
                return

            if path == "/api/hygiene/fix":
                summary = apply_safe_hygiene_fixes(self.state.repo)
                books = self.state.repo.get_all_books()
                raw_statuses = self.state.repo.get_raw_statuses()
                report = scan_library_hygiene(books, raw_statuses)
                self._send_json(
                    HTTPStatus.OK,
                    {"summary": summary, "report": report.to_dict()},
                )
                return

            if path == "/api/backups":
                backup = self.state.repo.create_backup(reason="manual")
                self._send_json(
                    HTTPStatus.CREATED,
                    {
                        "created": backup.name if backup else None,
                        "backups": self.state.repo.list_backups(),
                    },
                )
                return

            if path == "/api/backups/restore":
                payload = self._read_json_body()
                name = str(payload.get("name") or "")
                ok = self.state.repo.restore_backup(name)
                if not ok:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "backup_not_found"})
                    return
                self._send_json(
                    HTTPStatus.OK,
                    {"restored": name, "backups": self.state.repo.list_backups()},
                )
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except ValidationError as exc:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": exc.message_key, "detail": exc.detail, "field": exc.field},
            )
        except ExcelFileLockedError:
            self._send_json(HTTPStatus.CONFLICT, {"error": "err_excel_locked"})

    def do_PUT(self) -> None:
        self._handle_update(partial_update=False)

    def do_PATCH(self) -> None:
        self._handle_update(partial_update=True)

    def _handle_update(self, *, partial_update: bool) -> None:
        del partial_update
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/books/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        raw_id = path.removeprefix("/api/books/").strip("/")
        if not raw_id.isdigit():
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_id"})
            return
        book_id = int(raw_id)
        try:
            existing = self.state.repo.get_book(book_id)
            if existing is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "book_not_found"})
                return
            payload = self._read_json_body()
            clean = validate_book_payload(payload, existing=existing)
            updated = self.state.repo.update_book(book_id, clean)
            if updated is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "book_not_found"})
                return
            self._send_json(HTTPStatus.OK, updated.to_dict())
        except ValidationError as exc:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": exc.message_key, "detail": exc.detail, "field": exc.field},
            )
        except ExcelFileLockedError:
            self._send_json(HTTPStatus.CONFLICT, {"error": "err_excel_locked"})

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/books/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        raw_id = path.removeprefix("/api/books/").strip("/")
        if not raw_id.isdigit():
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_id"})
            return
        book_id = int(raw_id)
        try:
            deleted = self.state.repo.delete_book(book_id)
            if deleted is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "book_not_found"})
                return
            self._send_json(HTTPStatus.OK, {"deleted": deleted.to_dict()})
        except ExcelFileLockedError:
            self._send_json(HTTPStatus.CONFLICT, {"error": "err_excel_locked"})


def create_server(config: AppConfig) -> tuple[ThreadingHTTPServer, LibraryAppState]:
    repo = ExcelRepository(config)
    state = LibraryAppState(config=config, repo=repo)
    handler = partial(LibraryRequestHandler, state=state)
    server = ThreadingHTTPServer((config.host, config.port), handler)
    return server, state


def start_server_in_thread(config: AppConfig) -> tuple[ThreadingHTTPServer, int, threading.Thread]:
    server, _ = create_server(config)
    actual_port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, actual_port, thread
