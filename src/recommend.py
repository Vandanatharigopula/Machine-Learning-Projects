from __future__ import annotations

import pandas as pd
from collections.abc import Mapping
from sklearn.linear_model import LogisticRegression


def recommend_top_books(
    user_id: int | str,
    user_book_matrix: pd.DataFrame,
    similarity_matrix: pd.DataFrame,
    top_n: int = 5,
    book_title_map: Mapping[str, str] | None = None,
    engagement_model: Mapping[str, object] | None = None,
    min_like_probability: float = 0.55,
) -> list[str]:
    """
    Recommend books for a user using user-user collaborative filtering.

    Args:
        user_id: Target user ID to generate recommendations for.
        user_book_matrix: DataFrame where rows are users, columns are book titles,
            and values are ratings (0 means unread/not rated).
        similarity_matrix: Square DataFrame of user-user similarity scores.
            Index/columns should match user IDs from user_book_matrix.
        top_n: Number of books to return (default: 5).
        book_title_map: Optional mapping from book_id (or matrix column value)
            to human-readable title. If provided, returned values are titles.
        engagement_model: Optional engagement prediction model bundle produced
            by build_engagement_prediction_model().
        min_like_probability: Minimum predicted probability required for a book
            to be considered a "likely like" recommendation.

    Returns:
        List of recommended book titles, ordered by highest predicted interest.
    """
    # Validate that the requested user exists.
    if user_id not in user_book_matrix.index:
        raise ValueError(f"User '{user_id}' not found in user_book_matrix.")
    if user_id not in similarity_matrix.index:
        raise ValueError(f"User '{user_id}' not found in similarity_matrix.")

    # Get similarity scores for this user and exclude the user itself.
    user_similarities = similarity_matrix.loc[user_id].drop(user_id, errors="ignore")

    # Align similar-user scores with rows available in the rating matrix.
    common_users = user_book_matrix.index.intersection(user_similarities.index)
    similar_users = user_similarities.loc[common_users]

    # Books already read/rated by the target user (rating > 0).
    user_ratings = user_book_matrix.loc[user_id]
    unread_mask = user_ratings == 0

    # Collaborative-filtering score candidates.
    cf_scores = pd.Series(dtype=float)
    if not similar_users.empty:
        # Vectorized weighted scoring:
        # numerator = sum(similarity * rating), denominator = sum(abs(similarity))
        # only for users who have rated the book (> 0).
        neighbor_ratings = user_book_matrix.loc[common_users]
        rated_mask = neighbor_ratings > 0

        weighted_sum = (
            neighbor_ratings.mul(similar_users, axis=0).where(rated_mask, 0.0).sum(axis=0)
        )
        similarity_sum = (
            rated_mask.mul(similar_users.abs(), axis=0).sum(axis=0)
        )
        # Avoid division by zero by converting 0 denominators to NA.
        scores = weighted_sum.div(similarity_sum.where(similarity_sum > 0))

        # Candidate collaborative-filtering scores for unread books.
        cf_scores = scores[unread_mask].dropna().sort_values(ascending=False)

    # Fallback collaborative candidates from global popularity/quality.
    if cf_scores.empty:
        cf_scores = (
            user_book_matrix.where(user_book_matrix > 0)
            .mean(axis=0)[unread_mask]
            .dropna()
            .sort_values(ascending=False)
        )

    # Build predicted engagement for candidate books and combine both signals.
    if engagement_model:
        user_mean_series = engagement_model.get("user_mean_rating")
        book_mean_series = engagement_model.get("book_mean_rating")
        book_count_series = engagement_model.get("book_rating_count")
        global_mean = float(engagement_model.get("global_mean_rating", 0.0))
        global_count = float(engagement_model.get("global_book_rating_count", 0.0))
        classifier = engagement_model.get("model")
        constant_probability = engagement_model.get("constant_probability")

        user_mean = global_mean
        if user_mean_series is not None and user_id in user_mean_series.index:
            user_mean = float(user_mean_series.loc[user_id])

        features = pd.DataFrame(index=cf_scores.index)
        if book_mean_series is not None:
            features["book_mean_rating"] = features.index.to_series().map(book_mean_series)
        else:
            features["book_mean_rating"] = global_mean
        if book_count_series is not None:
            features["book_rating_count"] = features.index.to_series().map(book_count_series)
        else:
            features["book_rating_count"] = global_count

        features["book_mean_rating"] = features["book_mean_rating"].fillna(global_mean)
        features["book_rating_count"] = features["book_rating_count"].fillna(global_count)
        features["user_mean_rating"] = user_mean
        features = features[["user_mean_rating", "book_mean_rating", "book_rating_count"]]

        if classifier is None and constant_probability is not None:
            like_proba = pd.Series(constant_probability, index=features.index, dtype=float)
        else:
            if not isinstance(classifier, LogisticRegression):
                raise ValueError("Invalid engagement model: classifier type mismatch.")
            probabilities = classifier.predict_proba(features)[:, 1]
            like_proba = pd.Series(probabilities, index=features.index)

        liked_mask = like_proba >= min_like_probability
        filtered_candidates = cf_scores[liked_mask]
        if filtered_candidates.empty:
            filtered_candidates = cf_scores

        # Normalize CF scores then blend with predicted engagement probability.
        cf_min = float(filtered_candidates.min())
        cf_max = float(filtered_candidates.max())
        if cf_max > cf_min:
            normalized_cf = (filtered_candidates - cf_min) / (cf_max - cf_min)
        else:
            normalized_cf = pd.Series(1.0, index=filtered_candidates.index)

        blended_score = (0.7 * normalized_cf) + (0.3 * like_proba.loc[filtered_candidates.index])
        recommended_books = [str(book) for book in blended_score.sort_values(ascending=False).head(top_n).index]
    else:
        recommended_books = [str(book) for book in cf_scores.head(top_n).index]

    if book_title_map is None:
        return recommended_books

    return [book_title_map.get(book, book) for book in recommended_books]
