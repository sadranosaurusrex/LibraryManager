from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PACKAGE_ROOT.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from library_app.config import REQUIRED_COLUMNS, AppConfig
from library_app.domain.models import BookFilter, BookStatus
from library_app.domain.validation import validate_book_payload
from library_app.repository.excel_repository import ExcelRepository
from library_app.services.analytics_service import (
    build_analytics,
    build_facets,
)
from library_app.services.hygiene_service import (
    apply_safe_hygiene_fixes,
    scan_library_hygiene,
)
from library_app.services.search_service import search_and_filter_books


class TestRepositoryAndServices(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.excel_path = self.tmp_path / "Books_test.xlsx"

        # Seed realistic messy Excel rows mirroring Books_v2.xlsx quirks
        rows = [
            {
                "ID": 1,
                "BookName": 1984,  # numeric title!
                "Author": "جورج اورول",
                "Genre": "سیاسی ",
                "Description": 1984,
                "Storage": "کمد دیواری",
                "Floor": 2.0,
                "Row": 1.0,
                "Status": "finished",  # lowercase legacy status!
                "Rating": 5.0,
                "DateAdded": "2026-06-06",
                "DateFinished": None,
                "CoverPath": None,
                "Notes": None,
            },
            {
                "ID": 2,
                "BookName": "تاريخ فلسفه اسلامي",  # Arabic ي
                "Author": "مهدي حائري",
                "Genre": "فلسفه ، ديني",
                "Description": "معرفی جامعه‌شناسی و فلسفه",
                "Storage": "قفسه A",
                "Floor": None,  # missing Floor!
                "Row": None,    # missing Row!
                "Status": "Unread",
                "Rating": None,
                "DateAdded": "2026-06-06",
                "DateFinished": None,
                "CoverPath": None,
                "Notes": None,
            },
            {
                "ID": 3,
                "BookName": "بوف كور",  # Arabic ك
                "Author": None,  # missing Author!
                "Genre": "ادبیات داستانی",
                "Description": "رمان کلاسیک ایرانی",
                "Storage": "کمد اصلی",
                "Floor": 1.0,
                "Row": 2.0,
                "Status": "Reading",
                "Rating": 4.0,
                "DateAdded": "2026-06-06",
                "DateFinished": None,
                "CoverPath": None,
                "Notes": "یادداشت شخصی ویژه",
            },
        ]
        pd.DataFrame(rows, columns=list(REQUIRED_COLUMNS)).to_excel(self.excel_path, index=False)
        self.config = AppConfig.from_workspace(workspace_root=self.tmp_path, excel_path=self.excel_path)
        self.repo = ExcelRepository(self.config)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_messy_excel_loading_and_no_nan_strings(self) -> None:
        books = self.repo.get_all_books()
        self.assertEqual(len(books), 3)
        self.assertEqual(books[0].book_name, "1984")
        self.assertEqual(books[0].status, BookStatus.FINISHED)
        self.assertEqual(books[0].floor, 2)
        self.assertEqual(books[1].floor, None)
        self.assertEqual(books[2].author, "")

    def test_persian_hybrid_search_and_empty_filter_safety(self) -> None:
        books = self.repo.get_all_books()

        # Search Persian ی matching Arabic ي in Excel
        res1 = search_and_filter_books(books, BookFilter(query="تاريخ"))
        self.assertEqual([b.id for b, _ in res1], [2])
        res2 = search_and_filter_books(books, BookFilter(query="تاریخ"))
        self.assertEqual([b.id for b, _ in res2], [2])

        # ZWNJ-collapsed match in Description ("جامعه‌شناسی" vs "جامعهشناسی")
        res3 = search_and_filter_books(books, BookFilter(query="جامعهشناسی"))
        self.assertEqual([b.id for b, _ in res3], [2])

        # Search Persian digits matching numeric book ID or numeric title
        res_num = search_and_filter_books(books, BookFilter(query="۱۹۸۴"))
        self.assertEqual([b.id for b, _ in res_num], [1])

        # Fuzzy typo match ("بف کور" -> "بوف كور")
        res_fuzz = search_and_filter_books(books, BookFilter(query="بف کور"))
        self.assertEqual([b.id for b, _ in res_fuzz], [3])

        # Zero results combined with storage filter must return [] cleanly (no KeyError!)
        res_empty = search_and_filter_books(books, BookFilter(query="ناموجود_قطعی", storage="قفسه A"))
        self.assertEqual(res_empty, [])

    def test_crud_and_automatic_backup_restore(self) -> None:
        clean_add = validate_book_payload(
            {
                "book_name": "گلستان سعدي",
                "author": "سعدی",
                "genre": "شعر و نثر پارسی",
                "storage": "کمد (2)",
                "floor": "۳",
                "row": "۲",
                "status": "Finished",
                "rating": "4.5",
                "date_added": "۱۴۰۵/۰۸/۲۱",
            }
        )
        created = self.repo.add_book(clean_add)
        self.assertEqual(created.id, 4)
        self.assertEqual(created.book_name, "گلستان سعدی")
        self.assertEqual(created.floor, 3)
        self.assertEqual(created.date_added, "2026-11-12")
        self.assertTrue(bool(created.date_finished))  # auto-stamped when Finished

        backups = self.repo.list_backups()
        self.assertGreaterEqual(len(backups), 1)

        # Delete and verify backup created, then restore
        deleted = self.repo.delete_book(4)
        self.assertIsNotNone(deleted)
        self.assertIsNone(self.repo.get_book(4))

        delete_backup = next(
            b["name"] for b in self.repo.list_backups() if "delete" in b["name"]
        )
        self.assertTrue(self.repo.restore_backup(delete_backup))
        self.assertIsNotNone(self.repo.get_book(4))

    def test_analytics_facets_and_hygiene_fix(self) -> None:
        books = self.repo.get_all_books()
        facets = build_facets(books)
        storage_names = {s["name"] for s in facets["storages"]}
        self.assertIn("کمد دیواری", storage_names)
        self.assertIn("کمد اصلی", storage_names)

        analytics = build_analytics(books)
        self.assertEqual(analytics["kpis"]["total_books"], 3)
        self.assertEqual(analytics["kpis"]["finished_books"], 1)

        report = scan_library_hygiene(books, self.repo.get_raw_statuses())
        self.assertGreater(report.issue_counts.get("persian_normalization", 0), 0)
        self.assertEqual(report.issue_counts.get("status_casing", 0), 1)

        summary = apply_safe_hygiene_fixes(self.repo)
        self.assertGreater(summary["touched_books"], 0)
        self.assertEqual(summary["fixed_statuses"], 1)

        after = scan_library_hygiene(self.repo.get_all_books(), self.repo.get_raw_statuses())
        self.assertEqual(after.issue_counts.get("persian_normalization", 0), 0)
        self.assertEqual(after.issue_counts.get("status_casing", 0), 0)

    def test_real_books_v2_compatibility_on_isolated_copy(self) -> None:
        real_excel = WORKSPACE_ROOT / "data" / "Books_v2.xlsx"
        if not real_excel.exists():
            self.skipTest("data/Books_v2.xlsx not present")

        copy_path = self.tmp_path / "Books_v2_copy.xlsx"
        shutil.copy2(real_excel, copy_path)
        cfg = AppConfig.from_workspace(workspace_root=self.tmp_path, excel_path=copy_path)
        repo = ExcelRepository(cfg)

        books = repo.get_all_books()
        self.assertEqual(len(books), 665)

        analytics = build_analytics(books)
        self.assertGreaterEqual(len(analytics["shelf_map"]), 7)

        # Hygiene scan + fix on isolated copy should clean Arabic variants cleanly
        fix_summary = apply_safe_hygiene_fixes(repo)
        self.assertGreater(fix_summary["touched_books"], 0)
        self.assertEqual(len(repo.get_all_books()), 665)


if __name__ == "__main__":
    unittest.main()
