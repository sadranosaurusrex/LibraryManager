from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REQUIRED_COLUMNS: tuple[str, ...] = (
    "ID",
    "BookName",
    "Author",
    "Genre",
    "Description",
    "Storage",
    "Floor",
    "Row",
    "Status",
    "Rating",
    "DateAdded",
    "DateFinished",
    "CoverPath",
    "Notes",
)

DEFAULT_STORAGES: tuple[str, ...] = (
    "قفسه A",
    "قفسه B",
    "قفسه C",
    "کمد اصلی",
    "کمد دیواری",
)


@dataclass(frozen=True, slots=True)
class AppConfig:
    excel_path: Path
    backup_dir: Path
    covers_dir: Path
    default_lang: str = "fa"
    max_backups: int = 25
    host: str = "127.0.0.1"
    port: int = 8765

    @classmethod
    def from_workspace(
        cls,
        workspace_root: Path | None = None,
        excel_path: Path | None = None,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> AppConfig:
        root = workspace_root or Path(__file__).resolve().parents[2]
        resolved_excel = (excel_path or (root / "data" / "Books_v2.xlsx")).resolve()
        data_dir = resolved_excel.parent
        return cls(
            excel_path=resolved_excel,
            backup_dir=data_dir / "backups",
            covers_dir=data_dir / "covers",
            default_lang="fa",
            max_backups=25,
            host=host,
            port=port,
        )
