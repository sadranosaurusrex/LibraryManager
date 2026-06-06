from pathlib import Path
from repository.library_repository import LibraryRepository

BASE_DIR = Path(__file__).resolve().parent.parent

excel_path = BASE_DIR / "data" / "Books_v2.xlsx"

print(excel_path)

repo = LibraryRepository(excel_path)

books = repo.get_all_books()

print(books.head())
print()
print("Total books:", len(books))