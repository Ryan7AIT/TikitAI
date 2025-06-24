// JavaScript controlling the chat UI – extracted from index.html

const chatWindow = document.getElementById("chat-window");
const questionInput = document.getElementById("question-input");
const sendBtn = document.getElementById("send-btn");
const convList = document.getElementById("conv-list");
const newConvBtn = document.getElementById("new-conv-btn");
const modelSelect = document.getElementById("model-select");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");
const toggleModel = document.getElementById("toggle-model");
const modelSelectorWrapper = document.getElementById("model-selector-wrapper");

let currentConvId = null;
let sidebarVisible = true;

async function fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error("Request failed");
    return res.json();
}

// Conversations
async function loadConversations() {
    const data = await fetchJSON("/conversations/");
    convList.innerHTML = "";
    data.forEach((c) => {
        const li = document.createElement("li");
        li.dataset.id = c.id;
        li.className = "flex items-center justify-between px-4 py-3 hover:bg-gray-800";
        if (c.id == currentConvId) li.classList.add("bg-gray-700");

        const titleSpan = document.createElement("span");
        titleSpan.className = "truncate flex-1 cursor-pointer";
        titleSpan.textContent = c.title;
        titleSpan.addEventListener("click", () => selectConversation(c.id));

        const kebab = document.createElement("button");
        kebab.className = "kebab text-gray-500 hover:text-gray-700 px-2";
        kebab.innerHTML = "⋮";
        kebab.dataset.id = c.id;

        li.appendChild(titleSpan);
        li.appendChild(kebab);
        convList.appendChild(li);
    });
}

async function selectConversation(id) {
    currentConvId = id;
    // highlight
    [...convList.children].forEach((li) => {
        li.classList.toggle("bg-gray-700", li.dataset.id == id);
    });
    chatWindow.innerHTML = "";
    const msgs = await fetchJSON(`/conversations/${id}/messages`);
    msgs.forEach((m) => {
        appendMessage(m.question, true);
        const botBubble = appendMessage(m.answer, false);
        addFeedbackButtons(botBubble, m.id);
    });
}

async function createConversation() {
    const conv = await fetchJSON("/conversations/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
    });
    await loadConversations();
    selectConversation(conv.id);
}

newConvBtn.addEventListener("click", createConversation);

function appendMessage(text, isUser = false) {
    const wrapper = document.createElement("div");
    wrapper.className = `w-full max-w-3xl mx-auto flex ${isUser ? "justify-end" : "justify-start"}`;

    const bubble = document.createElement("div");
    bubble.className = `max-w-[75%] px-4 py-2 rounded-lg shadow text-sm whitespace-pre-line ${isUser
        ? "bg-emerald-600 text-white rounded-br-none"
        : "bg-gray-700 text-gray-200 rounded-bl-none"
        }`;
    bubble.textContent = text;

    wrapper.appendChild(bubble);
    chatWindow.appendChild(wrapper);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    return bubble; // Return bubble for further manipulation (streaming, etc.)
}

// Show a thinking placeholder (animated dots)
function appendThinking() {
    const bubble = appendMessage("", false);
    bubble.classList.add("flex", "items-center");

    const dotContainer = document.createElement("div");
    dotContainer.className = "flex gap-1";

    for (let i = 0; i < 3; i++) {
        const dot = document.createElement("span");
        dot.className = "animate-bounce bg-gray-500 rounded-full w-2 h-2";
        dot.style.animationDelay = `${i * 0.2}s`;
        dotContainer.appendChild(dot);
    }

    bubble.appendChild(dotContainer);
    return bubble;
}

// Typewriter effect for bot answer
function typeWriter(element, fullText, speed = 20, onComplete = null) {
    element.textContent = ""; // clear (remove dots)
    let index = 0;
    const prefix = "🤖 ";
    element.textContent = prefix;
    const interval = setInterval(() => {
        if (index < fullText.length) {
            element.textContent = prefix + fullText.slice(0, index + 1);
            index++;
            chatWindow.scrollTop = chatWindow.scrollHeight;
        } else {
            clearInterval(interval);
            if (onComplete) onComplete();
        }
    }, speed);
}

// Add thumbs-up / thumbs-down after bot response
function addFeedbackButtons(bubble, messageId) {
    // set relative so absolute children position correctly
    bubble.classList.add("relative", "pb-6"); // padding-bottom for space

    const container = document.createElement("div");
    container.className =
        "absolute right-2 bottom-1 flex items-center gap-1 text-gray-400 text-sm select-none";

    const label = document.createElement("span");
    label.textContent = "Helpful?";

    const upBtn = document.createElement("button");
    upBtn.textContent = "👍";
    const downBtn = document.createElement("button");
    downBtn.textContent = "👎";

    [upBtn, downBtn].forEach((btn) => {
        btn.className =
            "cursor-pointer transition-transform duration-150 hover:scale-110";
    });

    upBtn.addEventListener("mouseover", () => (upBtn.style.color = "#16a34a")); // green
    upBtn.addEventListener("mouseout", () => (upBtn.style.color = ""));

    downBtn.addEventListener("mouseover", () => (downBtn.style.color = "#dc2626")); // red
    downBtn.addEventListener("mouseout", () => (downBtn.style.color = ""));

    upBtn.addEventListener("click", () => sendFeedback(messageId, "up", upBtn, downBtn));
    downBtn.addEventListener("click", () => sendFeedback(messageId, "down", upBtn, downBtn));

    container.appendChild(label);
    container.appendChild(upBtn);
    container.appendChild(downBtn);
    bubble.appendChild(container);
}

async function sendFeedback(messageId, feedback, upBtn, downBtn) {
    try {
        await fetch(`/messages/${messageId}/feedback`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ feedback }),
        });
        // Visually mark selected
        if (feedback === "up") {
            upBtn.classList.add("opacity-50");
            downBtn.remove();
        } else {
            downBtn.classList.add("opacity-50");
            upBtn.remove();
        }
    } catch (err) {
        console.error("Failed to send feedback", err);
    }
}

async function sendQuestion() {
    const question = questionInput.value.trim();
    if (!question) return;

    appendMessage(question, true);
    questionInput.value = "";
    questionInput.focus();

    const thinkingBubble = appendThinking();

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question, conversation_id: currentConvId, model_name: modelSelect.value }),
        });

        if (!res.ok) {
            throw new Error("Server error");
        }

        const data = await res.json();
        if (!currentConvId) {
            currentConvId = data.conversation_id;
            loadConversations();
        }
        const messageId = data.message_id;
        typeWriter(thinkingBubble, data.answer || "No answer returned", 20, () => {
            addFeedbackButtons(thinkingBubble, messageId);
        });
    } catch (err) {
        console.error(err);
        thinkingBubble.remove();
        appendMessage("Oops! Something went wrong. Please try again later.");
    }
}

// initial load
loadConversations();

// Send on button click
sendBtn.addEventListener("click", sendQuestion);
// Send on Enter key
questionInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        sendQuestion();
    }
});

// Add event listener for sidebar toggle (collapse sidebar)
sidebarToggle.addEventListener("click", () => {
    sidebarVisible = !sidebarVisible;
    if (sidebarVisible) {
        sidebar.classList.remove("w-16");
        sidebar.classList.add("w-64");
        sidebarToggle.textContent = "⇤"; // arrow to collapse
        sidebar.querySelectorAll(".collapsible").forEach(el => el.classList.remove("hidden"));
    } else {
        sidebar.classList.remove("w-64");
        sidebar.classList.add("w-16");
        sidebarToggle.textContent = "☰"; // icon to expand
        sidebar.querySelectorAll(".collapsible").forEach(el => el.classList.add("hidden"));
    }
});

// Handle kebab menu actions using event delegation
document.addEventListener("click", (e) => {
    // open menu
    if (e.target.classList.contains("kebab")) {
        e.stopPropagation();
        showConvMenu(e.target);
    } else if (e.target.classList.contains("rename-btn")) {
        const id = e.target.dataset.id;
        const newName = prompt("Enter new name:");
        if (newName) {
            fetchJSON(`/conversations/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: newName }),
            }).then(loadConversations);
        }
    } else if (e.target.classList.contains("del-conv-btn")) {
        const id = e.target.dataset.id;
        if (confirm("Delete this conversation?")) {
            fetchJSON(`/conversations/${id}`, { method: "DELETE" }).then(() => {
                if (currentConvId == id) {
                    currentConvId = null;
                    chatWindow.innerHTML = "";
                }
                loadConversations();
            });
        }
    } else {
        // Click outside menu closes it
        const existing = document.getElementById("conv-menu");
        if (existing) existing.remove();
    }
});

function showConvMenu(btn) {
    const existing = document.getElementById("conv-menu");
    if (existing) existing.remove();

    const menu = document.createElement("div");
    menu.id = "conv-menu";
    menu.className = "absolute right-2 mt-2 bg-gray-800 border border-gray-600 rounded shadow text-sm z-10 text-gray-100";
    menu.innerHTML = `<button class="rename-btn block w-full text-left px-4 py-2 hover:bg-gray-700" data-id="${btn.dataset.id}">Rename</button><button class="del-conv-btn block w-full text-left px-4 py-2 hover:bg-gray-700 text-red-500" data-id="${btn.dataset.id}">Delete</button>`;
    btn.parentElement.style.position = "relative";
    btn.parentElement.appendChild(menu);
}

toggleModel.addEventListener('click', () => {
    modelSelectorWrapper.classList.toggle('hidden');
});