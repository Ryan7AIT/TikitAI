# RAG Chat Application

A full-stack Retrieval-Augmented Generation (RAG) chatbot built with **FastAPI**, **LangChain**, **Ollama (Llama-3)** and a lightweight **TailwindCSS** front-end.

The project lets end-users chat with your documents while giving administrators a password-protected console to manage data sources and monitor usage.

---

## ✨ Key Features

* Retrieval-augmented answering using a local FAISS index fed by text / PDF files, article URLs **and now ClickUp tasks + comments**.
* Modern one-page chat UI with typing animation, thinking indicator and mobile-friendly layout.
* SQLite persistence (via SQLModel) for:
  * Users (default `admin / admin`).
  * Every question / answer + latency metrics.
  * Registered data sources.
* Admin console (after login):
  * Dashboard with basic KPIs (message count, avg latency, number of data sources).
  * Data-source manager – upload / delete / sync files & URLs into the vector store.
  * Message viewer – inspect the full chat log.
* Modular code-base (routers, models, auth, db helpers) ready for scaling.
* Persistent ClickUp credentials – save once and reuse via /connections UI.

---

## 🏗️ Architecture

```
Browser (chat UI / admin UI)
        │  REST (JSON)
FastAPI ─┼─────────── /chat          ← public
        │           /auth/*         ← login
        │           /datasources/*  ← admin
        │           /messages/*     ← admin
        │           /metrics        ← admin
        │
        │  LangGraph pipeline
        └► retrieve() → generate() → ChatOllama (Llama-3)

Vector store: FAISS (in-memory) + HuggingFace Embeddings
Database    : SQLite via SQLModel (app.db)
Static files: served directly by FastAPI
```

---

## ⚡ Quick-Start

1. Clone & create a virtual env, then install deps:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the server (hot-reload):
   ```bash
   uvicorn app:app --reload
   ```
3. Open
   * Chat UI:        <http://127.0.0.1:8000/>
   * Admin login:    <http://127.0.0.1:8000/login>

Default admin credentials: **admin / admin** (created automatically on first run).

---

## 📂 Project Layout

```
RAG/
├── app.py                # FastAPI entry-point & chat endpoint
├── db.py                 # SQLite engine / session helpers
├── models.py             # SQLModel tables
├── auth.py               # Auth logic (bcrypt + Bearer token)
├── routers/              # Modular API routes
│   ├── auth_router.py
│   ├── data_router.py
│   ├── messages_router.py
│   └── metrics_router.py
├── data/                 # Source documents (text / pdf)
├── static/               # Front-end files (Tailwind)
│   ├── index.html        # Chat page
│   ├── login.html        # Admin login
│   └── admin/            # Console pages (dashboard, …)
└── requirements.txt
```

---

## 🔌 API (admin-only routes require `Authorization: Bearer <token>`)

| Method | Endpoint              | Description |
|--------|-----------------------|-------------|
| POST   | /chat                 | Ask a question (public) |
| POST   | /auth/login           | Get access-token |
| GET    | /datasources/         | List data sources |
| POST   | /datasources/upload   | Upload file (.txt/.pdf) |
| POST   | /datasources/add-url  | Register article URL |
| DELETE | /datasources/{id}     | Delete source |
| POST   | /datasources/{id}/sync| Parse & add source to vector store |
| GET    | /messages/            | List chat messages |
| GET    | /metrics/             | KPIs (msg count, avg latency, sources) |
| POST   | /clickup/test         | Verify ClickUp credentials |
| POST   | /clickup/tasks        | List tasks (with sync flag) |
| POST   | /clickup/sync         | Sync one or many tasks |
| POST   | /clickup/unsync       | Remove synced tasks |
| POST   | /clickup/comments     | Fetch comments for a task |
| GET    | /connections/          | List saved ClickUp connections |
| POST   | /connections/          | Create a new connection |
| GET    | /connections/{id}      | Get connection details |
| PUT    | /connections/{id}      | Update connection |
| DELETE | /connections/{id}      | Delete connection |
| POST   | /connections/{id}/test | Test connection credentials |

---

## 🛠️ Customisation Tips

* **Model** – edit `llm = ChatOllama(model="llama3.2:latest")` in `app.py` to point to any Ollama-served model.
* **Prompt** – modify `custom_template` in `app.py` to adjust tone & persona.
* **Chunking / parsing** – adjust logic in `data_router.sync_source()` or initial index build.
* **Styling** – all front-end pages use Tailwind CDN; tweak classes as desired.

---

## 🚀 Roadmap / Possible Improvements

1. **Real Streaming** – replace typewriter hack with Server-Sent Events or WebSocket streaming from FastAPI for token-level updates.
2. **JWT Auth** – store tokens client-side with expiry instead of in-memory `token_store`.
3. **Role management** – allow multiple non-admin users, register, reset password, etc.
4. **Persistent Vector Store** – move FAISS index to disk or use a cloud vector DB (e.g. Qdrant, Pinecone).
5. **Background Sync Jobs** – schedule automatic syncing of web URLs or S3 buckets (Celery / RQ).
6. **Advanced Analytics** – integrate Prometheus + Grafana or stream logs to ELK for richer dashboards.
7. **CI / CD & Docker** – containerise app, add GitHub Actions pipeline for tests + deployment.
8. **Semantic Search Tweaks** – experiment with different embedding models or hybrid BM25 + vector search.
9. **Feedback Loop** – thumbs-up / thumbs-down on answers to collect supervised data for future fine-tuning.
10. **Access Logs & Rate Limiting** – fortify public endpoint with IP throttling & CORS config.

Contributions & ideas are welcome – feel free to fork and iterate! 🎉 

## ✋ User Feedback (New)

Starting from v1.2 the chat UI shows a subtle "Helpful?" prompt in the bottom-right corner of each bot bubble followed by compact 👍 / 👎 icons.  Hovering them now highlights green/red for a clearer affordance.

When the user clicks:

1. A `POST /messages/{id}/feedback` with `{ "feedback": "up" | "down" }` is sent.
2. `logs/feedback.log` gets a line:
   ```
   2024-05-19T09:16:42	42	127.0.0.1	up
   ```
   (timestamp, message-id, client-ip, feedback)

All `/chat` requests produce a rich entry in `logs/interactions.log`:
```text
2024-05-19T09:16:40	42	127.0.0.1	123ms	Q: How do I reset my password?	A: You can click "Forgot password"…
```
So every interaction stores: timestamp, message-id, client-ip, latency, full question, and answer text—ready for downstream analytics.

> NOTE: The feedback endpoint remains unauthenticated; lock it down if required.

---

## 🗂️ Multi-Conversation Chat (v1.3)

The chat interface now features a sidebar listing past conversations – start a fresh one with the + button.  Selecting a conversation instantly reloads its history.

A model dropdown in the header lets users choose between three model names (placeholder – backend support to come).

Each `/chat` call now accepts `conversation_id` and returns it, while new chats auto-create a conversation record. Messages are linked via `conversation_id`.

## 🔄 Data Source Sync Status

Each data source now stores `last_synced_at` in the DB.  The Admin UI shows a green "Synced" label once a source has been embedded – and the status persists across page reloads.

Lightweight migration logic automatically adds the new column on first run after upgrade (SQLite `ALTER TABLE`).

### Sidebar actions (v1.4)

• Each conversation row now shows a ⋮ menu: rename or delete on the fly.  Titles persist server-side and are reflected across sessions.

• Sidebar can be toggled on mobile via the ☰ icon for a roomier chat view. 


## 📊 Performance Metrics (v1.5)

The chat UI now shows a "Performance" tab with detailed timing metrics for each `/chat` call.  The backend logs:

```
message_id  client_ip  retrieve_ms  generate_ms  db_ms  total_ms  question
```

