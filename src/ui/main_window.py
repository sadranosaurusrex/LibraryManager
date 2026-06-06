import tkinter as tk
from tkinter import ttk
from enum import Enum
import pandas as pd


# ---------------- ENUMS ----------------
class StatusEnum(str, Enum):
    UNREAD = "Unread"
    READING = "Reading"
    FINISHED = "Finished"
    DROPPED = "Dropped"


class StorageEnum(str, Enum):
    CLOSET_MAIN = "کمد اصلی"
    CLOSET_WALL = "کمد دیواری"
    SHELF_A = "قفسه A"
    SHELF_B = "قفسه B"

import re

def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    text = text.strip()

    # Arabic -> Persian fixes
    text = text.replace("ي", "ی")
    text = text.replace("ك", "ک")

    # remove extra spaces
    text = re.sub(r"\s+", " ", text)

    return text.lower()


# ---------------- MAIN WINDOW ----------------
class MainWindow:

    def __init__(self, root, repository):
        self.root = root
        self.repository = repository

        self.root.title("Library Manager")
        self.root.geometry("1200x700")

        self.create_widgets()
        self.load_books()

    # ---------------- UI ----------------
    def create_widgets(self):

        # ---------- SEARCH BAR ----------
        search_frame = ttk.Frame(self.root)
        search_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(search_frame, text="Search:").pack(side="left")

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.on_search())

        ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            width=40
        ).pack(side="left", padx=5)

        ttk.Button(
            search_frame,
            text="Refresh",
            command=self.load_books
        ).pack(side="left")

        ttk.Button(
            search_frame,
            text="Add Book",
            command=self.open_add_book_window
        ).pack(side="left", padx=5)

        ttk.Button(
            search_frame,
            text="Edit Book",
            command=self.open_edit_book_window
        ).pack(side="left", padx=5)

        # ---------- TABLE ----------
        table_frame = ttk.Frame(self.root)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        columns = ("ID", "BookName", "Author", "Genre", "Storage", "Floor", "Row", "Status")

        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")

        for col in columns:
            self.tree.heading(col, text=col)

        self.tree.column("ID", width=60)
        self.tree.column("BookName", width=300)
        self.tree.column("Author", width=180)
        self.tree.column("Genre", width=180)
        self.tree.column("Storage", width=120)
        self.tree.column("Floor", width=70)
        self.tree.column("Row", width=70)
        self.tree.column("Status", width=120)

        v_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)

        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # 👉 Double click edit
        self.tree.bind("<Double-1>", self.open_edit_book_window)

    # ---------------- DATA ----------------
    def load_books(self):

        self.tree.delete(*self.tree.get_children())

        books = self.repository.get_all_books()

        for _, row in books.iterrows():
            self.tree.insert("", "end", values=(
                row["ID"],
                row["BookName"],
                row["Author"],
                row["Genre"],
                row["Storage"],
                row["Floor"],
                row["Row"],
                row["Status"]
            ))

    # ---------------- SEARCH ----------------
    def on_search(self):

        text = normalize_text(self.search_var.get())
        books = self.repository.search(text)

        self.tree.delete(*self.tree.get_children())

        for _, row in books.iterrows():
            self.tree.insert("", "end", values=(
                row["ID"],
                row["BookName"],
                row["Author"],
                row["Genre"],
                row["Storage"],
                row["Floor"],
                row["Row"],
                row["Status"]
            ))

    # ---------------- GET SELECTED ----------------
    def get_selected_book(self):

        selected = self.tree.focus()

        if not selected:
            return None

        values = self.tree.item(selected, "values")

        if not values:
            return None

        return values

    # ---------------- ADD ----------------
    def open_add_book_window(self):

        win = tk.Toplevel(self.root)
        win.title("Add Book")
        win.geometry("420x520")

        fields = {}

        STATUS_OPTIONS = [e.value for e in StatusEnum]
        STORAGE_OPTIONS = [e.value for e in StorageEnum]

        # BookName
        ttk.Label(win, text="Book Name").pack()
        fields["BookName"] = ttk.Entry(win)
        fields["BookName"].pack(fill="x", padx=10)

        # Author
        ttk.Label(win, text="Author").pack()
        fields["Author"] = ttk.Entry(win)
        fields["Author"].pack(fill="x", padx=10)

        # Genre
        ttk.Label(win, text="Genre").pack()
        fields["Genre"] = ttk.Entry(win)
        fields["Genre"].pack(fill="x", padx=10)

        # Description
        ttk.Label(win, text="Description").pack()
        fields["Description"] = ttk.Entry(win)
        fields["Description"].pack(fill="x", padx=10)

        # Storage
        storage_var = tk.StringVar()
        storage_box = ttk.Combobox(win, textvariable=storage_var,
                                   values=STORAGE_OPTIONS, state="readonly")
        storage_box.pack(fill="x", padx=10)
        storage_box.current(0)

        # Status
        status_var = tk.StringVar()
        status_box = ttk.Combobox(win, textvariable=status_var,
                                  values=STATUS_OPTIONS, state="readonly")
        status_box.pack(fill="x", padx=10)
        status_box.current(0)

        # Floor
        fields["Floor"] = ttk.Spinbox(win, from_=1, to=10)
        fields["Floor"].pack(fill="x", padx=10)

        # Row
        fields["Row"] = ttk.Spinbox(win, from_=1, to=20)
        fields["Row"].pack(fill="x", padx=10)

        # Rating
        fields["Rating"] = ttk.Spinbox(win, from_=0, to=5)
        fields["Rating"].pack(fill="x", padx=10)

        # Notes
        fields["Notes"] = ttk.Entry(win)
        fields["Notes"].pack(fill="x", padx=10)

        def save():

            data = {
                "BookName": fields["BookName"].get(),
                "Author": fields["Author"].get(),
                "Genre": fields["Genre"].get(),
                "Description": fields["Description"].get(),
                "Storage": storage_var.get(),
                "Status": status_var.get(),
                "Floor": int(float(fields["Floor"].get())),
                "Row": int(float(fields["Row"].get())),
                "Rating": float(fields["Rating"].get()),
                "DateAdded": "2026-06-06",
                "DateFinished": "",
                "CoverPath": "",
                "Notes": fields["Notes"].get()
            }

            self.repository.add_book(data)
            self.load_books()
            win.destroy()
            print(data)

        ttk.Button(win, text="Save", command=save).pack(pady=10)

    # ---------------- EDIT ----------------
    def open_edit_book_window(self, event=None):

        selected = self.get_selected_book()

        if not selected:
            return

        book_id = int(selected[0])

        df = self.repository.get_all_books()
        book = df[df["ID"] == book_id].iloc[0]

        win = tk.Toplevel(self.root)
        win.title("Edit Book")
        win.geometry("420x520")

        fields = {}

        STATUS_OPTIONS = [e.value for e in StatusEnum]
        STORAGE_OPTIONS = [e.value for e in StorageEnum]

        ttk.Label(win, text="Book Name").pack()
        fields["BookName"] = ttk.Entry(win)
        fields["BookName"].pack(fill="x", padx=10)
        fields["BookName"].insert(0, book["BookName"])

        ttk.Label(win, text="Author").pack()
        fields["Author"] = ttk.Entry(win)
        fields["Author"].pack(fill="x", padx=10)
        fields["Author"].insert(0, book["Author"])

        ttk.Label(win, text="Genre").pack()
        fields["Genre"] = ttk.Entry(win)
        fields["Genre"].pack(fill="x", padx=10)
        fields["Genre"].insert(0, book["Genre"])

        storage_var = tk.StringVar(value=book["Storage"])
        ttk.Combobox(win, textvariable=storage_var,
                     values=STORAGE_OPTIONS, state="readonly").pack(fill="x", padx=10)

        status_var = tk.StringVar(value=book["Status"])
        ttk.Combobox(win, textvariable=status_var,
                     values=STATUS_OPTIONS, state="readonly").pack(fill="x", padx=10)

        fields["Floor"] = ttk.Spinbox(win, from_=1, to=10)
        fields["Floor"].pack(fill="x", padx=10)
        fields["Floor"].insert(0, book["Floor"])

        fields["Row"] = ttk.Spinbox(win, from_=1, to=20)
        fields["Row"].pack(fill="x", padx=10)
        fields["Row"].insert(0, book["Row"])

        fields["Rating"] = ttk.Spinbox(win, from_=0, to=5)
        fields["Rating"].pack(fill="x", padx=10)
        fields["Rating"].insert(0, book["Rating"] if pd.notna(book["Rating"]) else 0)

        fields["Notes"] = ttk.Entry(win)
        fields["Notes"].pack(fill="x", padx=10)
        fields["Notes"].insert(0, book["Notes"] if pd.notna(book["Notes"]) else "")

        def save():

            updated = {
                "BookName": fields["BookName"].get(),
                "Author": fields["Author"].get(),
                "Genre": fields["Genre"].get(),
                "Storage": storage_var.get(),
                "Status": status_var.get(),
                "Floor": int(float(fields["Floor"].get())),
                "Row": int(float(fields["Row"].get())),
                "Rating": float(fields["Rating"].get()),
                "Notes": fields["Notes"].get()
            }

            self.repository.update_book(book_id, updated)
            self.load_books()
            win.destroy()
            print(updated)

        ttk.Button(win, text="Save Changes", command=save).pack(pady=10)