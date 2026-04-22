# Book Recommendation API

A production-style FastAPI service for personalized book recommendations using a hybrid approach:

- **Collaborative filtering** (user-user cosine similarity)
- **Engagement prediction** (logistic regression probability of user liking a book)
- **Popularity filtering** (minimum rating-count threshold to reduce noisy books)

The API provides user recommendations and a trending list from processed ratings data.

## Project Overview

This project loads book and rating data from CSV files, cleans and filters records, builds recommendation models at API startup, and serves results through REST endpoints.

Core goals:

- improve recommendation quality by removing low-signal books
- combine neighborhood-based recommendations with prediction confidence
- provide fast endpoints with preloaded model state
- expose operational logs for startup, requests, and errors

## Architecture (Text Diagram)

```text
                    +----------------------+
                    | data/books.csv       |
                    | data/ratings.csv     |
                    +----------+-----------+
                               |
                               v
                 +-----------------------------+
                 | src.data_processing         |
                 | - clean & merge             |
                 | - remove zero ratings       |
                 | - filter by MIN_BOOK_RATINGS
                 +--------------+--------------+
                                |
              +-----------------+-----------------+
              |                                   |
              v                                   v
 +-------------------------------+    +-------------------------------+
 | src.model.build_user_similarity|    | src.model.build_engagement_  |
 | - user-book matrix             |    | prediction_model              |
 | - cosine similarity matrix     |    | - logistic regression         |
 +----------------+--------------+    +---------------+---------------+
                  |                                   |
                  +-----------------+-----------------+
                                    v
                         +-------------------------+
                         | FastAPI app (api/main) |
                         | - /recommend/{user_id} |
                         | - /trending            |
                         | - request/error logs   |
                         +-----------+------------+
                                     |
                                     v
                              JSON API Responses
```

## How to Run

### 1) Prerequisites

- Python 3.9+
- `pip`

### 2) Install dependencies

```bash
cd Book-Recommendation-Project
pip install -r requirements.txt
```

### 3) Configure (optional)

- `MIN_BOOK_RATINGS` controls minimum number of ratings per book during startup preprocessing.
- Default: `50`

Windows PowerShell:

```powershell
$env:MIN_BOOK_RATINGS = "75"
```

Windows CMD:

```cmd
set MIN_BOOK_RATINGS=75
```

Linux/macOS:

```bash
export MIN_BOOK_RATINGS=75
```

### 4) Start API server

```bash
python -m uvicorn api.main:app --reload
```

### 5) Open API docs

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## API Endpoints

### `GET /`
Health check endpoint.

### `GET /recommend/{user_id}`
Returns top recommended books for a specific user.

- **Path param**: `user_id` (int)
- **Response**: `user_id`, `recommendations` (list of titles)
- **Errors**:
  - `404` user not found
  - `503` model not ready
  - `500` runtime failure

### `GET /trending`
Returns top 10 most popular books based on rating count from the processed dataframe.

- **Response**: `books` array with `book_id`, `title`, `author`, `rating_count`
- **Errors**:
  - `503` data/model not ready

## Sample Outputs

### `GET /`

```json
{
  "message": "API is running"
}
```

### `GET /recommend/244`

```json
{
  "user_id": 244,
  "recommendations": [
    "The Four Agreements: A Practical Guide to Personal Freedom",
    "Anne Frank: The Diary of a Young Girl",
    "Pop Goes the Weasel",
    "The Honk and Holler Opening Soon",
    "Beloved (Plume Contemporary Fiction)"
  ]
}
```

### `GET /trending`

```json
{
  "books": [
    {
      "book_id": "0971880107",
      "title": "Wild Animus",
      "author": "Rich Shapero",
      "rating_count": 120
    },
    {
      "book_id": "0316666343",
      "title": "The Lovely Bones: A Novel",
      "author": "Alice Sebold",
      "rating_count": 111
    }
  ]
}
```

## Project Structure

```text
Book-Recommendation-Project/
├── api/
│   └── main.py                  # FastAPI app and endpoints
├── data/
│   ├── books.csv
│   └── ratings.csv
├── src/
│   ├── data_processing.py       # Data loading and preprocessing
│   ├── model.py                 # Similarity + engagement model builders
│   └── recommend.py             # Hybrid recommendation logic
├── requirements.txt
├── test.py                      # Local smoke test script
└── README.md
```

## Logging

The API uses Python's `logging` module to record:

- startup initialization and readiness status
- incoming requests and response status/latency
- handled and unhandled errors

## Future Enhancements

- add offline evaluation metrics (`precision@k`, `recall@k`, `MAP`)
- persist trained artifacts instead of rebuilding every startup
- add caching and pagination for larger catalog responses
- add CI tests for endpoint contract and model quality checks
