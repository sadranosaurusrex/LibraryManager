import pandas as pd
from pathlib import Path

class LibraryRepository:

    def __init__(self, excel_path):
        self.excel_path = Path(excel_path)

    def load_books(self):
        return pd.read_excel(self.excel_path)

    def save_books(self, df):
        df.to_excel(self.excel_path, index=False)

    def get_all_books(self):
        return self.load_books()

    def add_book(self, book_data):

        df = self.load_books()

        next_id = 1

        if len(df) > 0:
            next_id = int(df["ID"].max()) + 1

        book_data["ID"] = next_id

        df = pd.concat(
            [df, pd.DataFrame([book_data])],
            ignore_index=True
        )

        self.save_books(df)

        return next_id

    def delete_book(self, book_id):

        df = self.load_books()

        df = df[df["ID"] != book_id]

        self.save_books(df)

    def update_book(self, book_id, updated_data):

        df = self.load_books()

        mask = df["ID"] == book_id

        for key, value in updated_data.items():
            df.loc[mask, key] = value

        self.save_books(df)

    def search(self, text):

        df = self.load_books()

        if not text:
            return df

        text = str(text).lower()

        mask = (
            df["BookName"].astype(str).str.lower().str.contains(text)
            |
            df["Author"].astype(str).str.lower().str.contains(text)
            |
            df["Genre"].astype(str).str.lower().str.contains(text)
        )

        return df[mask]