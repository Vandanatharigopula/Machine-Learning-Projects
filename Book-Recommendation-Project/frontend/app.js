const recommendForm = document.getElementById("recommend-form");
const userIdInput = document.getElementById("user-id");
const recommendStatus = document.getElementById("recommend-status");
const recommendList = document.getElementById("recommend-list");
const useMyIdBtn = document.getElementById("use-my-id-btn");
const authUser = document.getElementById("auth-user");
const logoutBtn = document.getElementById("logout-btn");

const trendingStatus = document.getElementById("trending-status");
const trendingList = document.getElementById("trending-list");
const refreshTrendingBtn = document.getElementById("refresh-trending");
let currentUser = null;

function setStatus(element, message, isError = false) {
  element.textContent = message;
  element.style.color = isError ? "#b91c1c" : "#4b5563";
}

function setLoggedInUser(username, userId) {
  userIdInput.value = String(userId);
  const rawUser = localStorage.getItem("book_app_user");
  let interestsText = "Interests: Not set";
  if (rawUser) {
    try {
      const parsed = JSON.parse(rawUser);
      if (Array.isArray(parsed.interests) && parsed.interests.length > 0) {
        interestsText = `Interests: ${parsed.interests.join(", ")}`;
      }
    } catch (_error) {
      // Ignore malformed local storage and keep default text.
    }
  }
  authUser.textContent = `Logged in as ${username} (User ID: ${userId}) | ${interestsText}`;
  authUser.style.color = "#065f46";
}

function loadStoredUser() {
  const rawUser = localStorage.getItem("book_app_user");
  if (!rawUser) {
    window.location.href = "/login";
    return null;
  }
  try {
    const parsed = JSON.parse(rawUser);
    if (parsed.username && parsed.userId) {
      setLoggedInUser(parsed.username, parsed.userId);
      return parsed;
    }
  } catch (_error) {
    localStorage.removeItem("book_app_user");
  }
  window.location.href = "/login";
  return null;
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

useMyIdBtn.addEventListener("click", () => {
  if (!currentUser || !currentUser.userId) {
    setStatus(recommendStatus, "No logged-in user found. Please login again.", true);
    return;
  }
  userIdInput.value = String(currentUser.userId);
  setStatus(recommendStatus, `Using logged-in user ID: ${currentUser.userId}`);
});

refreshTrendingBtn.addEventListener("click", () => {
  fetchTrending();
});

logoutBtn.addEventListener("click", () => {
  localStorage.removeItem("book_app_user");
  window.location.href = "/login";
});

currentUser = loadStoredUser();
fetchTrending();
