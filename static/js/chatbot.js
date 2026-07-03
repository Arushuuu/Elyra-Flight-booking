const form = document.getElementById("chatForm");
const input = document.getElementById("chatInput");
const messages = document.getElementById("chatMessages");

function addMessage(text, className) {
  const bubble = document.createElement("p");
  bubble.className = className;
  bubble.textContent = text;
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
}

if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, "user");
    input.value = "";
    addMessage("Checking Elyra flights...", "bot");

    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({message: text})
      });
      const data = await response.json();
      messages.lastChild.textContent = data.reply;
    } catch (error) {
      messages.lastChild.textContent = "Sorry, the assistant is unavailable right now.";
    }
  });
}
