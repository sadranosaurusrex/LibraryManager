from pathlib import Path
import tkinter as tk

from repository.library_repository import LibraryRepository
from ui.main_window import MainWindow

BASE_DIR = Path(__file__).resolve().parent.parent

excel_path = BASE_DIR / "data" / "Books_v2.xlsx"

repo = LibraryRepository(excel_path)

root = tk.Tk()

app = MainWindow(root, repo)

root.mainloop()