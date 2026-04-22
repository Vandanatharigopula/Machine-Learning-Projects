from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Import project functions using the requested names.
from src.data_processing import load_and_process_data
from src.model import build_user_similarity as build_model
from src.model import build_engagement_prediction_model
from src.recommend import recommend_top_books as recommend_books

app = FastAPI(title="Book Recommendation API")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("book_recommender_api")
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

DEFAULT_MIN_BOOK_RATINGS = 50


def _get_min_book_ratings() -> int:
    """Read MIN_BOOK_RATINGS env var with a safe integer fallback."""
    raw_value = os.getenv("MIN_BOOK_RATINGS", str(DEFAULT_MIN_BOOK_RATINGS))
    try:
        parsed_value = int(raw_value)
    except ValueError:
        return DEFAULT_MIN_BOOK_RATINGS
    return max(1, parsed_value)


class HealthResponse(BaseModel):
    """Response model for health endpoint."""

    message: str


class RecommendationResponse(BaseModel):
    """Response model for recommendation endpoint."""

    user_id: int
    recommendations: list[str]


class TrendingBook(BaseModel):
    """Single trending-book item."""

    book_id: str
    title: str
    author: Optional[str] = None
    rating_count: int


class TrendingResponse(BaseModel):
    """Response model for trending endpoint."""

    books: list[TrendingBook]


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming requests and response status."""
    start_time = time.perf_counter()
    logger.info("Incoming request: %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.exception(
            "Unhandled error during request: %s %s (%.2f ms)",
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "Completed request: %s %s -> %s (%.2f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Log HTTP errors and keep FastAPI-style response."""
    logger.error(
        "HTTP error on %s %s: status=%s detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log uncaught runtime errors and return a clean 500 response."""
    logger.exception(
        "Unhandled server error on %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.on_event("startup")
def startup_event() -> None:
    """
    Load data and build the recommendation model once at startup.

    If loading/model building fails, we keep state as unavailable and let
    endpoints return a clear 503 instead of crashing the application.
    """
    app.state.model_ready = False
    app.state.startup_error = None
    app.state.user_book_matrix = None
    app.state.similarity_matrix = None
    app.state.engagement_model = None
    app.state.processed_df = None

    try:
        logger.info("API startup: initializing processed data and models")
        # Train only on books with stronger rating support.
        min_book_ratings = _get_min_book_ratings()
        df = load_and_process_data(min_book_ratings=min_book_ratings)
        if df is None or df.empty:
            app.state.startup_error = "Failed to load data or dataset is empty."
            logger.error(app.state.startup_error)
            return

        user_book_matrix, similarity_matrix = build_model(df)
        if user_book_matrix.empty or similarity_matrix.empty:
            app.state.startup_error = "Model build failed: generated empty matrices."
            logger.error(app.state.startup_error)
            return

        app.state.user_book_matrix = user_book_matrix
        app.state.similarity_matrix = similarity_matrix
        app.state.engagement_model = build_engagement_prediction_model(df)
        app.state.processed_df = df
        app.state.model_ready = True
        logger.info("API startup completed successfully")
    except Exception as exc:  # pragma: no cover - startup guard
        app.state.startup_error = f"Startup failed: {exc}"
        logger.exception(app.state.startup_error)


@app.get("/", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Simple health endpoint to verify the API is up."""
    return HealthResponse(message="API is running")


@app.get("/app")
def frontend_app() -> FileResponse:
    """Serve a simple frontend for recommendations and trending books."""
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend is not available.")
    return FileResponse(index_file)


@app.get("/recommend/{user_id}", response_model=RecommendationResponse)
def get_recommendations(user_id: int) -> RecommendationResponse:
    """
    Return top book recommendations for a given user.

    Responses:
    - 200 with recommendation list
    - 404 if user is not found
    - 503 if model is unavailable
    - 500 for unexpected runtime errors
    """
    if not getattr(app.state, "model_ready", False):
        detail = app.state.startup_error or "Model is not available."
        raise HTTPException(status_code=503, detail=detail)

    try:
        recommendations = recommend_books(
            user_id=user_id,
            user_book_matrix=app.state.user_book_matrix,
            similarity_matrix=app.state.similarity_matrix,
            engagement_model=app.state.engagement_model,
            top_n=5,
        )
        return RecommendationResponse(
            user_id=user_id,
            recommendations=recommendations,
        )
    except ValueError as exc:
        # recommend_books raises ValueError when user_id is unknown.
        logger.error("Recommendation error for user %s: %s", user_id, exc)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to generate recommendations for user %s", user_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendations: {exc}",
        ) from exc


@app.get("/trending", response_model=TrendingResponse)
def get_trending_books() -> TrendingResponse:
    """
    Return top 10 trending books by number of ratings in processed data.

    Responses:
    - 200 with trending books
    - 503 if model/data is unavailable
    """
    if not getattr(app.state, "model_ready", False):
        detail = app.state.startup_error or "Model is not available."
        raise HTTPException(status_code=503, detail=detail)

    processed_df = getattr(app.state, "processed_df", None)
    if processed_df is None or processed_df.empty:
        raise HTTPException(status_code=503, detail="Processed data is not available.")

    trending_df = (
        processed_df.groupby(["book_id", "title", "author"], as_index=False)
        .agg(rating_count=("rating", "count"))
        .sort_values(by="rating_count", ascending=False)
        .head(10)
    )

    books = [
        TrendingBook(
            book_id=str(row.book_id),
            title=str(row.title),
            author=None if row.author is None else str(row.author),
            rating_count=int(row.rating_count),
        )
        for row in trending_df.itertuples(index=False)
    ]

    return TrendingResponse(books=books)
