function togglePassword(id) {
    const passwordInput = document.getElementById(id);

    if (passwordInput.type === "password") {
        passwordInput.type = "text";
    } else {
        passwordInput.type = "password";
    }
}

function completeAnimation(event, element) {
    event.preventDefault();

    const card = element.closest(".task-card");

    card.classList.add("complete-success");
    element.innerHTML = "🎉 Completed Successfully!";

    setTimeout(() => {
        window.location.href = element.href;
    }, 800);
}

async function getSuggestion() {
    const resultBox = document.getElementById("aiResult");

    resultBox.style.display = "block";
    resultBox.innerHTML = "🤖 AI is thinking...";

    try {
        const response = await fetch("/ai_suggest", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            }
        });

        const data = await response.json();

        resultBox.innerHTML = "✨ <strong>AI Suggestion:</strong><br><br>" + data.response;
    } catch (error) {
        resultBox.innerHTML = "Something went wrong. Try again.";
    }
}