import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity


def build_user_similarity(
    processed_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build a user-book interaction matrix and user-user cosine similarity matrix.

    Args:
        processed_df: Preprocessed DataFrame containing at least:
            - user_id
            - book_id
            - rating

    Returns:
        A tuple with:
            1) user_book_matrix: Pivot table with users as rows, books as columns,
               and ratings as values. Missing values are filled with 0.
            2) user_similarity_df: DataFrame of cosine similarity scores between users.
    """
    # Ensure required columns exist before building matrices.
    required_cols = {"user_id", "book_id", "rating"}
    missing_cols = required_cols.difference(processed_df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {sorted(missing_cols)}")

    # Create user-book matrix:
    # rows -> user_id, columns -> book_id, values -> rating.
    user_book_matrix = processed_df.pivot_table(
        index="user_id",
        columns="book_id",
        values="rating",
        aggfunc="mean",
    )

    # Replace missing ratings with 0 so cosine similarity can be computed.
    user_book_matrix = user_book_matrix.fillna(0)

    # Compute cosine similarity between all user vectors.
    similarity_matrix = cosine_similarity(user_book_matrix)

    # Wrap similarity array in a DataFrame with user IDs as index/columns.
    user_similarity_df = pd.DataFrame(
        similarity_matrix,
        index=user_book_matrix.index,
        columns=user_book_matrix.index,
    )

    return user_book_matrix, user_similarity_df


def build_engagement_prediction_model(
    processed_df: pd.DataFrame,
) -> dict[str, object]:
    """
    Train a lightweight engagement model from historical ratings.

    The model predicts whether a user is likely to "like" a book based on
    aggregate interaction features.
    """
    required_cols = {"user_id", "book_id", "rating"}
    missing_cols = required_cols.difference(processed_df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {sorted(missing_cols)}")

    if processed_df.empty:
        raise ValueError("processed_df is empty. Cannot train engagement model.")

    # Aggregate statistics used as features for both train and inference.
    user_mean_rating = processed_df.groupby("user_id")["rating"].mean()
    book_mean_rating = processed_df.groupby("book_id")["rating"].mean()
    book_rating_count = processed_df.groupby("book_id")["rating"].count()
    global_mean_rating = float(processed_df["rating"].mean())

    train_df = processed_df[["user_id", "book_id", "rating"]].copy()
    train_df["user_mean_rating"] = train_df["user_id"].map(user_mean_rating)
    train_df["book_mean_rating"] = train_df["book_id"].map(book_mean_rating)
    train_df["book_rating_count"] = train_df["book_id"].map(book_rating_count)

    # Define engagement target from rating distribution.
    like_threshold = float(train_df["rating"].median())
    y_train = (train_df["rating"] >= like_threshold).astype(int)

    # Ensure both classes exist to avoid fitting errors on small datasets.
    if y_train.nunique() < 2:
        like_threshold = global_mean_rating
        y_train = (train_df["rating"] >= like_threshold).astype(int)

    # If still one class, default to a constant score model represented as metadata.
    if y_train.nunique() < 2:
        constant_probability = float(y_train.iloc[0])
        return {
            "model": None,
            "constant_probability": constant_probability,
            "user_mean_rating": user_mean_rating,
            "book_mean_rating": book_mean_rating,
            "book_rating_count": book_rating_count,
            "global_mean_rating": global_mean_rating,
            "global_book_rating_count": float(book_rating_count.mean()),
        }

    x_train = train_df[["user_mean_rating", "book_mean_rating", "book_rating_count"]]
    classifier = LogisticRegression(max_iter=500, random_state=42)
    classifier.fit(x_train, y_train)

    return {
        "model": classifier,
        "constant_probability": None,
        "user_mean_rating": user_mean_rating,
        "book_mean_rating": book_mean_rating,
        "book_rating_count": book_rating_count,
        "global_mean_rating": global_mean_rating,
        "global_book_rating_count": float(book_rating_count.mean()),
    }


if __name__ == "__main__":
    # Local test run: load processed data and show quick verification outputs.
    try:
        from data_processing import load_and_process_data
    except ImportError:
        from src.data_processing import load_and_process_data

    df = load_and_process_data()
    if df is None or df.empty:
        print("No processed data available. Check your data files and preprocessing.")
    else:
        user_book_matrix, user_similarity_df = build_user_similarity(df)
        engagement_model = build_engagement_prediction_model(df)
        print(f"Processed rows: {len(df)}")
        print(f"User-book matrix shape: {user_book_matrix.shape}")
        print(f"User similarity matrix shape: {user_similarity_df.shape}")
        print(
            "Engagement model ready:",
            "yes" if engagement_model.get("model") is not None else "constant",
        )
        print("\nUser-book matrix (first 5 rows):")
        print(user_book_matrix.head())
        print("\nUser similarity matrix (first 5 rows):")
        print(user_similarity_df.head())
