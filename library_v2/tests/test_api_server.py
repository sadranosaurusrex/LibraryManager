from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from library_app.config import REQUIRED_COLUMNS, AppConfig
from library_app.web.server import start_server_in_thread


class TestApiServer(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.excel_path = self.tmp_path / "Books_api.xlsx"
        rows = [
            {
                "ID": 1,
                "BookName": "شاهنامه",
                "Author": "فردوسی",
                "Genre": "شعر و حماسه",
                "Description": "حماسه ملی ایران",
                "Storage": "قفسه A",
                "Floor": 1,
                "Row": 1,
                "Status": "Reading",
                "Rating": 5,
                "DateAdded": "2026-06-06",
                "DateFinished": None,
                "CoverPath": None,
                "Notes": None,
            }
        ]
        pd.DataFrame(rows, columns=list(REQUIRED_COLUMNS)).to_excel(self.excel_path, index=False)
        config = AppConfig.from_workspace(workspace_root=self.tmp_path, excel_path=self.excel_path, port=0)
        self.server, self.port, self.thread = start_server_in_thread(config)
        self.base_url = f"http://127.0.0.1:{self.port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.tmp_dir.cleanup()

    def _req(self, method: str, path: str, body: dict | None = None) -> tuple[int, bytes]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as err:
            with err:
                return err.code, err.read()

    def test_full_rest_lifecycle(self) -> None:
        # Health & i18n
        code, raw = self._req("GET", "/api/health")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["total_books"], 1)

        code, raw = self._req("GET", "/api/i18n")
        self.assertEqual(code, 200)
        i18n_data = json.loads(raw)
        self.assertEqual(i18n_data["default_lang"], "fa")
        self.assertIn("fa", i18n_data["translations"])
        self.assertIn("en", i18n_data["translations"])

        # Validation error (400) when missing book_name
        code, raw = self._req("POST", "/api/books", {"storage": "قفسه A"})
        self.assertEqual(code, 400)
        self.assertEqual(json.loads(raw)["error"], "err_book_name_required")

        # Create book with Jalali date
        code, raw = self._req(
            "POST",
            "/api/books",
            {
                "book_name": "منطق‌الطیر",
                "author": "عطار نیشابوری",
                "genre": "عرفان",
                "storage": "کمد دیواری",
                "floor": 2,
                "row": 3,
                "status": "Unread",
                "date_added": "۱۴۰۵/۰۸/۲۱",
            },
        )
        self.assertEqual(code, 201)
        created = json.loads(raw)
        self.assertEqual(created["id"], 2)
        self.assertEqual(created["date_added"], "2026-11-12")

        # Partial PATCH update -> mark Finished
        code, raw = self._req("PATCH", "/api/books/2", {"status": "Finished", "rating": 5})
        self.assertEqual(code, 200)
        patched = json.loads(raw)
        self.assertEqual(patched["status"], "Finished")
        self.assertTrue(bool(patched["date_finished"]))

        # Upload minimal 1x1 PNG cover and fetch it back
        tiny_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        code, raw = self._req(
            "POST",
            "/api/books/2/cover",
            {"filename": "cover.png", "data_base64": base64.b64encode(tiny_png).decode("ascii")},
        )
        self.assertEqual(code, 200)
        cover_path = json.loads(raw)["cover_path"]
        code, img_bytes = self._req("GET", f"/api/covers/{cover_path}")
        self.assertEqual(code, 200)
        self.assertEqual(img_bytes, tiny_png)

        # Path traversal attempt must return 404
        code, _ = self._req("GET", "/api/covers/../../etc/passwd")
        self.assertEqual(code, 404)

        # CSV export must include UTF-8 BOM for Windows Excel Persian support
        code, csv_bytes = self._req("GET", "/api/export/csv")
        self.assertEqual(code, 200)
        self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf"))
        self.assertIn("منطق‌الطیر", csv_bytes.decode("utf-8-sig"))

        # Analytics & Hygiene
        code, raw = self._req("GET", "/api/analytics")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["kpis"]["total_books"], 2)

        # Delete book
        code, _ = self._req("DELETE", "/api/books/2")
        self.assertEqual(code, 200)
        code, _ = self._req("GET", "/api/books/2")
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main()
