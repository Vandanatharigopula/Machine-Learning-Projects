from src.data_processing import load_and_process_data
from src.model import build_user_similarity, build_engagement_prediction_model
from src.recommend import recommend_top_books

# Use a small sample for fast local smoke tests.
df = load_and_process_data(sample_size=1000, min_book_ratings=50)

if df is not None and not df.empty:
    user_book_matrix, similarity = build_user_similarity(df)
    engagement_model = build_engagement_prediction_model(df)
    book_title_map = (
        df[["book_id", "title"]]
        .dropna()
        .drop_duplicates(subset=["book_id"])
        .set_index("book_id")["title"]
        .astype(str)
        .to_dict()
    )

    if user_book_matrix.empty:
        print("User-book matrix is empty; no recommendations can be generated.")
    else:
        user_id = user_book_matrix.index[0]
        recs = recommend_top_books(
            user_id,
            user_book_matrix,
            similarity,
            engagement_model=engagement_model,
            top_n=5,
            book_title_map=book_title_map,
        )

        print(f"Recommendations for user {user_id}:")
        if recs:
            for r in recs:
                print("-", r)
        else:
            print("No recommendations available for this user.")
else:
    print("Data loading failed or returned no rows.")