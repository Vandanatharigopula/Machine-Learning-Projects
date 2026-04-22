const recommendForm = document.getElementById("recommend-form");
const userIdInput = document.getElementById("user-id");
const recommendStatus = document.getElementById("recommend-status");
const recommendList = document.getElementById("recommend-list");

const trendingStatus = document.getElementById("trending-status");
const trendingList = document.getElementById("trending-list");
const refreshTrendingBtn = document.getElementById("refresh-trending");

function setStatus(element, message, isError = false) {
  element.textContent = message;
  element.style.color = isError ? "#b91c1c" : "#4b5563";
}

async function fetchRecommendations(userId) {
  setStatus(recommendStatus, "Loading recommendations...");
  recommendList.innerHTML = "";

  try {
    const response = await fetch(`/recommend/${userId}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Failed to load recommendations.");
    }

    if (!Array.isArray(data.recommendations) || data.recommendations.length === 0) {
      setStatus(recommendStatus, "No recommendations found for this user.");
      return;
    }

    setStatus(recommendStatus, `Top recommendations for user ${data.user_id}:`);
    data.recommendations.forEach((title) => {
      const li = document.createElement("li");
      li.className = "book-item";
      li.textContent = title;
      recommendList.appendChild(li);
    });
  } catch (error) {
    setStatus(recommendStatus, error.message, true);
  }
}

async function fetchTrending() {
  setStatus(trendingStatus, "Loading trending books...");
  trendingList.innerHTML = "";

  try {
    const response = await fetch("/trending");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Failed to load trending books.");
    }

    if (!Array.isArray(data.books) || data.books.length === 0) {
      setStatus(trendingStatus, "No trending books available.");
      return;
    }

    setStatus(trendingStatus, "Top 10 books by rating count:");
    const list = document.createElement("ol");
    list.className = "list";

    data.books.forEach((book) => {
      const li = document.createElement("li");
      li.className = "book-item";
      li.innerHTML = `
        <strong>${book.title}</strong>
        <div class="book-meta">
          ${book.author || "Unknown author"} | Ratings: ${book.rating_count} | ID: ${book.book_id}
        </div>
      `;
      list.appendChild(li);
    });

    trendingList.appendChild(list);
  } catch (error) {
    setStatus(trendingStatus, error.message, true);
  }
}

recommendForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const userId = userIdInput.value.trim();
  if (!userId) {
    setStatus(recommendStatus, "Please enter a user ID.", true);
    return;
  }
  fetchRecommendations(userId);
});

refreshTrendingBtn.addEventListener("click", () => {
  fetchTrending();
});

fetchTrending();
