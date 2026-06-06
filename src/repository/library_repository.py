import pandas as pd
from pathlib import Path
from rapidfuzz import fuzz


class LibraryRepository:

    def __init__(self, excel_path):
        self.excel_path = Path(excel_path)

    # ---------------- NORMALIZE ----------------
    def normalize_text(self, text: str) -> str:
        if not isinstance(text, str):
            return ""

        text = text.strip()

        # Persian normalization
        text = text.replace("ي", "ی")
        text = text.replace("ك", "ک")

        return text.lower()

    # ---------------- LOAD / SAVE ----------------
    def load_books(self):
        return pd.read_excel(self.excel_path)

    def save_books(self, df):
        df.to_excel(self.excel_path, index=False)

    def get_all_books(self):
        return self.load_books()

    # ---------------- ADD ----------------
    def add_book(self, book_data):

        try:
            df = self.load_books()
        except:
            df = pd.DataFrame()

        if df.empty:
            df = pd.DataFrame(columns=book_data.keys())
            next_id = 1
        else:
            next_id = int(df["ID"].max()) + 1

        book_data["ID"] = next_id

        df = pd.concat([df, pd.DataFrame([book_data])], ignore_index=True)

        self.save_books(df)

        return next_id
    # ---------------- DELETE ----------------
    def delete_book(self, book_id):

        df = self.load_books()

        df["ID"] = df["ID"].astype(int)
        mask = df["ID"] == int(book_id)
        
        df = df[~mask]

        self.save_books(df)

    # ---------------- UPDATE ----------------
    def update_book(self, book_id, updated_data):

        df = self.load_books()

        df["ID"] = df["ID"].astype(int)

        mask = df["ID"] == int(book_id)

        if not mask.any():
            print("Book not found!")
            return

        for key, value in updated_data.items():

            if key not in df.columns:
                df[key] = None  # auto-fix missing column

            if value == "" or value is None:
                df.loc[mask, key] = None
            else:
                df.loc[mask, key] = value

        self.save_books(df)

    # ---------------- SEARCH (HYBRID + FUZZY) ----------------
    def search(self, query):

        df = self.load_books()

        query = self.normalize_text(query)

        if not query:
            return df

        results = []

        for _, row in df.iterrows():

            book_name = self.normalize_text(row["BookName"])
            author = self.normalize_text(row["Author"])

            # 1) Exact substring match (fast path)
            exact_match = (
                query in book_name or
                query in author
            )

            # 2) Fuzzy match (smart path)
            fuzzy_score = max(
                fuzz.partial_ratio(query, book_name),
                fuzz.partial_ratio(query, author)
            )

            if exact_match or fuzzy_score > 70:
                row_dict = row.to_dict()
                row_dict["score"] = fuzzy_score
                results.append(row_dict)

        # sort by relevance
        results = sorted(results, key=lambda x: x["score"], reverse=True)

        return pd.DataFrame(results)