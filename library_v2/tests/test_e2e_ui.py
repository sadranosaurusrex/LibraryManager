from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PACKAGE_ROOT.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from library_app.config import REQUIRED_COLUMNS, AppConfig
from library_app.web.server import start_server_in_thread
from run import find_available_port


class TestEndToEndUI(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.excel_path = self.tmp_path / "Books_e2e.xlsx"

        real_excel = WORKSPACE_ROOT / "data" / "Books_v2.xlsx"
        if real_excel.exists():
            shutil.copy2(real_excel, self.excel_path)
            self.expected_initial_count = 665
        else:
            rows = [
                {
                    "ID": 1,
                    "BookName": "مثنوی معنوی",
                    "Author": "مولانا",
                    "Genre": "شعر و عرفان",
                    "Description": "شاهکار ادب فارسی",
                    "Storage": "کمد دیواری",
                    "Floor": 1,
                    "Row": 1,
                    "Status": "Finished",
                    "Rating": 5,
                    "DateAdded": "2026-06-06",
                    "DateFinished": "2026-08-01",
                    "CoverPath": None,
                    "Notes": None,
                },
                {
                    "ID": 2,
                    "BookName": "تاريخ بيهقي",
                    "Author": "ابوالفضل بيهقي",
                    "Genre": "تاريخ",
                    "Description": "متن کلاسیک نثر فارسی",
                    "Storage": "قفسه A",
                    "Floor": 2,
                    "Row": 1,
                    "Status": "Unread",
                    "Rating": None,
                    "DateAdded": "2026-06-06",
                    "DateFinished": None,
                    "CoverPath": None,
                    "Notes": None,
                },
            ]
            pd.DataFrame(rows, columns=list(REQUIRED_COLUMNS)).to_excel(self.excel_path, index=False)
            self.expected_initial_count = 2

        safe_port = find_available_port("127.0.0.1", 18765)
        config = AppConfig.from_workspace(workspace_root=self.tmp_path, excel_path=self.excel_path, port=safe_port)
        self.server, self.port, self.thread = start_server_in_thread(config)
        self.base_url = f"http://127.0.0.1:{self.port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.tmp_dir.cleanup()

    def test_persian_rtl_flows_and_language_switch(self) -> None:
        screenshot_dir = os.environ.get("LIBRARY_V2_SCREENSHOT_DIR", "")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1380, "height": 880})
            page = context.new_page()

            console_errors: list[str] = []
            page_errors: list[str] = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            page.goto(self.base_url, wait_until="networkidle")

            # 1. Verify default Persian RTL state
            self.assertEqual(page.locator("html").get_attribute("lang"), "fa")
            self.assertEqual(page.locator("html").get_attribute("dir"), "rtl")
            page.wait_for_selector("#books-tbody tr")

            if screenshot_dir:
                Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(Path(screenshot_dir) / "01_library_rtl.png"), full_page=False)

            # 2. Verify dynamic storage filter contains کمد دیواری
            storage_options = page.locator("#filter-storage option").all_text_contents()
            self.assertTrue(any("کمد دیواری" in opt for opt in storage_options))

            # 3. Add a new unique Persian book via UI modal using Jalali date
            unique_title = "سفرنامه آزمایشی ۱۴۰۵"
            page.click("#btn-add-book")
            page.fill("#form-book-name", unique_title)
            page.fill("#form-author", "نویسنده آزمایشی")
            page.fill("#form-genre", "ادبیات")
            page.fill("#form-storage", "کمد دیواری")
            page.fill("#form-floor", "2")
            page.fill("#form-row", "2")
            page.select_option("#form-status", "Finished")
            page.fill("#form-rating", "5")
            page.fill("#form-date-added", "۱۴۰۵/۰۸/۲۱")
            page.click("#btn-submit-book-modal")
            page.wait_for_timeout(300)

            # Search for newly added book
            page.fill("#search-input", unique_title)
            page.wait_for_timeout(350)
            self.assertIn(unique_title, page.locator("#books-tbody").inner_text())

            # Open slide-over drawer & switch to Cards view
            page.locator("#books-tbody tr").first.click()
            page.wait_for_selector("#book-drawer:not(.hidden)")
            self.assertIn(unique_title, page.locator("#book-drawer").inner_text())
            page.click("#btn-close-drawer")

            page.click("#btn-view-cards")
            page.wait_for_selector("#cards-view-container:not(.hidden) .book-card")
            if screenshot_dir:
                page.screenshot(path=str(Path(screenshot_dir) / "02_cards_rtl.png"), full_page=False)
            page.click("#btn-view-table")
            page.click("#btn-clear-search")
            page.wait_for_timeout(300)

            # 4. Shelf Map Tab
            page.click('.nav-tab[data-tab="shelf-map"]')
            page.wait_for_selector("#shelf-map-grid .cabinet-card")
            page.locator(".row-slot-btn").first.click()
            page.wait_for_selector("#shelf-slot-inspector:not(.hidden)")
            if screenshot_dir:
                page.screenshot(path=str(Path(screenshot_dir) / "03_shelf_map_rtl.png"), full_page=False)

            # 5. Analytics Tab
            page.click('.nav-tab[data-tab="analytics"]')
            page.wait_for_selector("#chart-status-container svg")
            if screenshot_dir:
                page.screenshot(path=str(Path(screenshot_dir) / "04_analytics_rtl.png"), full_page=False)

            # 6. Hygiene Tab + Auto-clean
            page.click('.nav-tab[data-tab="hygiene"]')
            page.wait_for_selector("#hygiene-summary-grid .kpi-card")
            if screenshot_dir:
                page.screenshot(path=str(Path(screenshot_dir) / "05_hygiene_rtl.png"), full_page=False)

            # 7. Language Switch -> English (LTR) and back to Persian (RTL)
            page.click("#btn-lang-toggle")
            self.assertEqual(page.locator("html").get_attribute("lang"), "en")
            self.assertEqual(page.locator("html").get_attribute("dir"), "ltr")
            if screenshot_dir:
                page.screenshot(path=str(Path(screenshot_dir) / "06_analytics_en_ltr.png"), full_page=False)

            page.click("#btn-lang-toggle")
            self.assertEqual(page.locator("html").get_attribute("lang"), "fa")
            self.assertEqual(page.locator("html").get_attribute("dir"), "rtl")

            # 8. Delete the test book via drawer + confirm modal
            page.click('.nav-tab[data-tab="library"]')
            page.fill("#search-input", unique_title)
            page.wait_for_timeout(350)
            page.locator("#books-tbody tr").first.click()
            page.wait_for_selector("#btn-drawer-delete")
            page.click("#btn-drawer-delete")
            page.wait_for_selector("#confirm-modal-backdrop:not(.hidden)")
            page.click("#btn-confirm-delete")
            page.wait_for_selector("#library-empty-state:not(.hidden)")
            self.assertIn("کتابی با این مشخصات پیدا نشد", page.locator("#library-empty-state").inner_text())

            # 9. Verify responsive layout has no horizontal overflow on mobile viewport
            page.set_viewport_size({"width": 390, "height": 844})
            page.click("#btn-empty-reset")
            page.wait_for_timeout(300)
            overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            self.assertFalse(overflow, "Page should not have horizontal overflow at 390px width")

            self.assertEqual(console_errors, [], f"Console errors: {console_errors}")
            self.assertEqual(page_errors, [], f"Page errors: {page_errors}")
            browser.close()


if __name__ == "__main__":
    unittest.main()
