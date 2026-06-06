from dataclasses import dataclass

@dataclass
class Book:
    id: int

    book_name: str
    author: str
    genre: str
    description: str

    storage: str
    floor: int
    row: int

    status: str
    rating: float

    date_added: str
    date_finished: str

    cover_path: str
    notes: str