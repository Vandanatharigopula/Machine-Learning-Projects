const loginForm = document.getElementById("login-form");
const loginStatus = document.getElementById("login-status");

function setStatus(message, isError = false) {
  loginStatus.textContent = message;
  loginStatus.style.color = isError ? "#b91c1c" : "#4b5563";
}

function hasLoggedInUser() {
  const rawUser = localStorage.getItem("book_app_user");
  if (!rawUser) {
    return false;
  }
  try {
    const parsed = JSON.parse(rawUser);
    return Boolean(parsed.username && parsed.userId);
  } catch (_error) {
    localStorage.removeItem("book_app_user");
    return false;
  }
}

if (hasLoggedInUser()) {
  window.location.href = "/app";
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;

  try {
    const response = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 404) {
        window.location.href = "/signup";
        return;
      }
      throw new Error(data.detail || "Login failed.");
    }

    localStorage.setItem(
      "book_app_user",
      JSON.stringify({ username: data.username, userId: data.user_id, interests: data.interests || [] }),
    );
    window.location.href = "/app";
  } catch (error) {
    setStatus(error.message, true);
  }
});
