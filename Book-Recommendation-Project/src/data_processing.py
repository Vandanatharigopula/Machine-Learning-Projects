from __future__ import annotations

import pandas as pd
from pathlib import Path


def _resolve_data_csv(base: str, candidates: tuple[str, ...]) -> Path:
    """Pick first existing CSV path (Linux is case-sensitive)."""
    data_dir = Path("data")
    for name in candidates:
        path = data_dir / name
        if path.is_file():
            return path
    raise FileNotFoundError(f"No file found for {base}; tried: {candidates}")


def load_and_process_data(
    sample_size: int = 20000,
    min_book_ratings: int = 50,
):
    try:
        books_path = _resolve_data_csv("books", ("books.csv", "Books.csv"))
        ratings_path = _resolve_data_csv("ratings", ("ratings.csv", "Ratings.csv"))
        books = pd.read_csv(books_path, sep=";", encoding="latin-1")
        ratings = pd.read_csv(ratings_path, sep=";", encoding="latin-1")

        # Rename columns based on YOUR dataset
        books = books.rename(columns={
            "ISBN": "book_id",
            "Title": "title",
            "Author": "author"
        })

        ratings = ratings.rename(columns={
            "User-ID": "user_id",
            "ISBN": "book_id",
            "Rating": "rating"
        })

        # Merge datasets
        df = pd.merge(ratings, books, on="book_id")

        # Remove zero ratings
        df = df[df["rating"] > 0]

        # Drop missing values
        df = df.dropna()

        # Keep only books with enough rating history to improve signal quality.
        if min_book_ratings and min_book_ratings > 1:
            book_rating_counts = df.groupby("book_id")["rating"].transform("count")
            df = df[book_rating_counts >= min_book_ratings]

        # Reduce size for faster processing.
        # Use min() so this works even when the dataset has fewer rows.
        if sample_size and sample_size > 0:
            sample_n = min(sample_size, len(df))
            df = df.sample(n=sample_n, random_state=42)

        return df

    except Exception as e:
        print(f"Error: {e}")
        return None