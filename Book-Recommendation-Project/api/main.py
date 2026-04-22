from __future__ import annotations

import logging
import os
import time
import json
import hashlib
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
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
FRONTEND_CANDIDATES = [
    BASE_DIR / "frontend",
    Path.cwd() / "frontend",
    Path.cwd() / "Book-Recommendation-Project" / "frontend",
]
FRONTEND_DIR = next(
    (path for path in FRONTEND_CANDIDATES if path.exists()),
    FRONTEND_CANDIDATES[0],
)

DEFAULT_MIN_BOOK_RATINGS = 50
APP_USERS_FILE = BASE_DIR / "data" / "app_users.json"
ALLOWED_GENRES = {
    "Fiction",
    "Fantasy",
    "Science Fiction",
    "Mystery / Thriller",
    "Romance",
    "Historical Fiction",
    "Biography / Autobiography",
    "Self-help",
    "Business / Finance",
    "Psychology",
    "Education",
    "Children's books",
    "Young Adult (YA)",
    "Comics / Graphic novels",
    "Philosophy",
    "Technology",
    "Health & Fitness",
    "Spiritual",
}
GENRE_KEYWORDS = {
    "Fantasy": ["dragon", "wizard", "magic", "kingdom", "sorcerer"],
    "Science Fiction": ["space", "alien", "robot", "future", "galaxy"],
    "Mystery / Thriller": ["murder", "mystery", "detective", "thriller", "crime"],
    "Romance": ["love", "romance", "heart", "bride", "kiss"],
    "Historical Fiction": ["history", "war", "empire", "queen", "king"],
    "Biography / Autobiography": ["biography", "memoir", "autobiography", "life of"],
    "Self-help": ["habit", "mindset", "success", "self", "guide"],
    "Business / Finance": ["business", "money", "finance", "invest", "market"],
    "Psychology": ["psychology", "mind", "behavior", "brain"],
    "Education": ["learning", "education", "study", "teaching"],
    "Children's books": ["kids", "children", "storybook"],
    "Young Adult (YA)": ["young", "teen", "academy"],
    "Comics / Graphic novels": ["comic", "graphic novel", "manga"],
    "Philosophy": ["philosophy", "ethics", "meaning", "stoic"],
    "Technology": ["technology", "programming", "software", "computer", "ai"],
    "Health & Fitness": ["health", "fitness", "diet", "workout"],
    "Spiritual": ["spiritual", "meditation", "soul", "faith"],
}


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


class SignupRequest(BaseModel):
    """Request payload for user signup."""

    username: str
    password: str
    interests: list[str] = []


class LoginRequest(BaseModel):
    """Request payload for user login."""

    username: str
    password: str


class AuthResponse(BaseModel):
    """Response payload for authentication endpoints."""

    user_id: int
    username: str
    interests: list[str]
    message: str


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


def _hash_password(password: str) -> str:
    """Hash plain password for simple local auth storage."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _load_registered_users() -> dict[str, dict[str, object]]:
    """Load app users from disk if available."""
    if not APP_USERS_FILE.exists():
        return {}
    with APP_USERS_FILE.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _save_registered_users(users: dict[str, dict[str, object]]) -> None:
    """Persist app users to disk."""
    APP_USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with APP_USERS_FILE.open("w", encoding="utf-8") as handle:
        json.dump(users, handle, indent=2)


def _next_user_id(existing_ids: set[int], users: dict[str, dict[str, object]]) -> int:
    """Generate next available user id across dataset and app users."""
    persisted_ids = {
        int(user_data.get("user_id"))
        for user_data in users.values()
        if isinstance(user_data, dict) and user_data.get("user_id") is not None
    }
    all_ids = existing_ids.union(persisted_ids)
    return (max(all_ids) + 1) if all_ids else 1


def _popular_title_fallback(top_n: int = 5) -> list[str]:
    """Return top popular titles when collaborative recommendations are unavailable."""
    processed_df = getattr(app.state, "processed_df", None)
    if processed_df is None or processed_df.empty:
        return []
    popular_df = (
        processed_df.groupby("title", as_index=False)
        .agg(rating_count=("rating", "count"))
        .sort_values(by="rating_count", ascending=False)
        .head(top_n)
    )
    return popular_df["title"].astype(str).tolist()


def _interest_based_fallback(user_id: int, top_n: int = 5) -> list[str]:
    """Use user interests to filter fallback recommendations when possible."""
    users = getattr(app.state, "registered_users", {})
    user_record = next(
        (
            record
            for record in users.values()
            if isinstance(record, dict) and int(record.get("user_id", -1)) == user_id
        ),
        None,
    )
    interests = user_record.get("interests", []) if user_record else []
    if not interests:
        return _popular_title_fallback(top_n=top_n)

    processed_df = getattr(app.state, "processed_df", None)
    if processed_df is None or processed_df.empty:
        return []

    keywords: set[str] = set()
    for genre in interests:
        keywords.update(GENRE_KEYWORDS.get(genre, []))

    if not keywords:
        return _popular_title_fallback(top_n=top_n)

    title_series = processed_df["title"].astype(str)
    keyword_pattern = "|".join(keyword for keyword in keywords if keyword)
    matched_df = processed_df[title_series.str.lower().str.contains(keyword_pattern, regex=True)]
    if matched_df.empty:
        return _popular_title_fallback(top_n=top_n)

    fallback_df = (
        matched_df.groupby("title", as_index=False)
        .agg(rating_count=("rating", "count"))
        .sort_values(by="rating_count", ascending=False)
        .head(top_n)
    )
    return fallback_df["title"].astype(str).tolist()


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
    app.state.book_title_map = None
    app.state.registered_users = {}
    app.state.existing_user_ids = set()

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
        app.state.book_title_map = (
            df[["book_id", "title"]]
            .dropna()
            .drop_duplicates(subset=["book_id"])
            .assign(book_id=lambda data: data["book_id"].astype(str))
            .set_index("book_id")["title"]
            .astype(str)
            .to_dict()
        )
        app.state.existing_user_ids = {int(user_id) for user_id in user_book_matrix.index}
        app.state.registered_users = _load_registered_users()
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
    """Serve authenticated app page."""
    for directory in FRONTEND_CANDIDATES:
        app_file = directory / "app.html"
        if app_file.exists():
            return FileResponse(app_file)
    raise HTTPException(status_code=404, detail="Frontend is not available.")


@app.get("/login")
def frontend_login() -> FileResponse:
    """Serve login page."""
    for directory in FRONTEND_CANDIDATES:
        login_file = directory / "login.html"
        if login_file.exists():
            return FileResponse(login_file)
    raise HTTPException(status_code=404, detail="Frontend is not available.")


@app.get("/signup")
def frontend_signup() -> FileResponse:
    """Serve signup page."""
    for directory in FRONTEND_CANDIDATES:
        signup_file = directory / "signup.html"
        if signup_file.exists():
            return FileResponse(signup_file)
    raise HTTPException(status_code=404, detail="Frontend is not available.")


@app.get("/ui")
def frontend_root_redirect() -> RedirectResponse:
    """Convenience route to open login page."""
    return RedirectResponse(url="/login")


@app.post("/auth/signup", response_model=AuthResponse)
def signup_user(payload: SignupRequest) -> AuthResponse:
    """Register a new application user and return assigned user id."""
    username = payload.username.strip().lower()
    password = payload.password.strip()

    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if payload.interests:
        invalid_interests = [genre for genre in payload.interests if genre not in ALLOWED_GENRES]
        if invalid_interests:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid interests: {invalid_interests}",
            )

    users = getattr(app.state, "registered_users", {})
    if username in users:
        raise HTTPException(status_code=409, detail="Username already exists.")

    existing_ids = getattr(app.state, "existing_user_ids", set())
    new_user_id = _next_user_id(existing_ids, users)
    users[username] = {
        "user_id": new_user_id,
        "password_hash": _hash_password(password),
        "interests": payload.interests,
    }
    _save_registered_users(users)
    app.state.registered_users = users

    return AuthResponse(
        user_id=new_user_id,
        username=username,
        interests=payload.interests,
        message="Signup successful.",
    )


@app.post("/auth/login", response_model=AuthResponse)
def login_user(payload: LoginRequest) -> AuthResponse:
    """Login an existing application user."""
    username = payload.username.strip().lower()
    password = payload.password.strip()
    users = getattr(app.state, "registered_users", {})

    if username not in users:
        raise HTTPException(status_code=404, detail="User not found. Please sign up first.")

    user_record = users[username]
    if user_record.get("password_hash") != _hash_password(password):
        raise HTTPException(status_code=401, detail="Invalid password.")

    return AuthResponse(
        user_id=int(user_record["user_id"]),
        username=username,
        interests=list(user_record.get("interests", [])),
        message="Login successful.",
    )


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
            book_title_map=app.state.book_title_map,
            engagement_model=app.state.engagement_model,
            top_n=5,
        )
        return RecommendationResponse(
            user_id=user_id,
            recommendations=recommendations,
        )
    except ValueError as exc:
        # recommend_books raises ValueError when user_id is unknown.
        # For new/unknown users, return popular-title fallback recommendations.
        logger.warning("Unknown user_id %s. Returning fallback recommendations.", user_id)
        fallback_recommendations = _interest_based_fallback(user_id=user_id, top_n=5)
        if fallback_recommendations:
            return RecommendationResponse(
                user_id=user_id,
                recommendations=fallback_recommendations,
            )
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
