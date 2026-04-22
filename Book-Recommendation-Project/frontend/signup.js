const signupForm = document.getElementById("signup-form");
const signupStatus = document.getElementById("signup-status");

function setStatus(message, isError = false) {
  signupStatus.textContent = message;
  signupStatus.style.color = isError ? "#b91c1c" : "#4b5563";
}

signupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = document.getElementById("signup-username").value.trim();
  const password = document.getElementById("signup-password").value;
  const interests = Array.from(
    document.getElementById("signup-interests").selectedOptions,
    (option) => option.value,
  );

  try {
    const response = await fetch("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, interests }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Signup failed.");
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
