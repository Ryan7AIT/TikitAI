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

---

## 📄 Document Embedding Rules

The RAG system uses a sophisticated document processing pipeline that handles different file types with appropriate splitting strategies. All embedding operations are centralized and consistent across the application.

### 🎯 Core Embedding Principles

1. **Database-Driven**: Only documents with `is_synced = 1` in the DataSource table are embedded
2. **Type-Aware Splitting**: Different document types use different chunking strategies
3. **Centralized Logic**: All embedding operations use the same processing pipeline
4. **Consistent Processing**: Whether documents are synced individually or in bulk, the same rules apply

### 📝 Document Type Processing Rules

#### Documentation Files (`*_docs.txt`, `*_docs.md`)
- **Strategy**: Guide-based splitting
- **Delimiter**: Triple dashes (`---`)
- **Use Case**: Technical documentation, user guides, knowledge bases
- **Example**:
  ```
  Section 1 Content
  ---
  Section 2 Content
  ---
  Section 3 Content
  ```

#### ClickUp Tasks (`clickup_*.txt`)
- **Strategy**: Single chunk per task
- **Processing**: Keep entire task content as one document
- **Use Case**: Task descriptions, issue tracking, project management
- **Format**: Task ID, Issue description, Problem, Solution

#### Support Tickets & Regular Files (all other `.txt`, `.md`)
- **Strategy**: Issue-based splitting
- **Delimiter**: The word "Issue"
- **Processing**: Split on "Issue" keyword and prepend "Issue" to each chunk
- **Use Case**: Support ticket systems, incident reports, troubleshooting guides

#### PDF Files (`.pdf`)
- **Strategy**: Page-based processing
- **Processing**: Each page becomes a separate chunk
- **Use Case**: Documentation, reports, manuals

#### URLs (`http://`, `https://`)
- **Strategy**: Web content extraction
- **Processing**: Extracts main content and applies appropriate splitting based on content type
- **Use Case**: Articles, blog posts, online documentation

### 🔄 Embedding Workflow

1. **Sync Check**: System verifies `DataSource.is_synced = 1`
2. **Type Detection**: File extension and naming patterns determine processing strategy
3. **Content Loading**: Documents are loaded using appropriate loaders (TextLoader, PyPDFLoader, WebBaseLoader)
4. **Standardized Processing**: Content is processed through `VectorStoreService.process_documents_for_embedding()`
5. **Vector Store Addition**: Processed chunks are added to the FAISS vector store

### 🛠️ API Embedding Operations

| Operation | Description | Database Check |
|-----------|-------------|----------------|
| **App Initialization** | Loads all synced documents on startup | ✅ Only `is_synced = 1` |
| **Individual Sync** | `/datasources/{id}/sync` | ✅ Updates `is_synced = 1` after embedding |
| **Bulk Sync** | `/datasources/regular/sync` | ✅ Only processes `is_synced != 1` |
| **ClickUp Sync** | `/external/{id}/clickup/tickets/{ticket_id}/sync` | ✅ Creates DataSource with `is_synced = 1` |
| **Rebuild Vector Store** | After deletions or major changes | ✅ Only `is_synced = 1` sources |

### 🔍 Embedding Functions

#### Core Functions
- `VectorStoreService.process_documents_for_embedding()` - Main processing logic
- `VectorStoreService.embed_datasource()` - Embed single datasource
- `VectorStoreService.embed_content_string()` - Embed content string
- `rebuild_vector_store()` - Rebuild entire vector store

#### File Pattern Detection
```python
# Documentation files (only files with "_docs" in name)
if "_docs.txt" in filename or "_docs.md" in filename:
    # Split by "---"

# ClickUp tasks  
elif "clickup_" in filename:
    # Keep as single chunks

# Regular support tickets and other files
else:
    # Split by "Issue"
```

### ⚠️ Important Notes

- **Consistency**: All embedding operations use the same `VectorStoreService.process_documents_for_embedding()` method
- **Database Authority**: The DataSource table is the single source of truth for what should be embedded
- **Sync Status**: Files are only embedded when `is_synced = 1`
- **Error Handling**: Failed embeddings are logged but don't stop the overall process
- **Performance**: Large files are automatically chunked appropriately for optimal retrieval

### 🚀 Best Practices

1. **File Naming**: Use consistent naming patterns (`*_docs.txt` for documentation, `clickup_*` for tasks)
2. **Content Structure**: Structure documentation with `---` separators for better chunking
3. **Sync Management**: Always use the admin interface to manage sync status
4. **Monitoring**: Check logs for embedding errors and performance metrics

---

## 📊 Performance Metrics (v1.5)

The chat UI now shows a "Performance" tab with detailed timing metrics for each `/chat` call.  The backend logs:

```
message_id  client_ip  retrieve_ms  generate_ms  db_ms  total_ms  question
```



## 🔌 API (admin-only routes require `Authorization: Bearer <token>`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | /chat | Ask a question (public). |
| POST   | /auth/login | Authenticate and receive JWT token. |
| GET    | /conversations/ | List conversations. |
| POST   | /conversations/ | Create a new conversation. |
| PUT    | /conversations/{id} | Rename/update a conversation. |
| DELETE | /conversations/{id} | Delete a conversation and its messages. |
| GET    | /conversations/{id}/messages | Retrieve messages in a conversation. |
| GET    | /messages/ | List all chat messages (admin). |
| POST   | /messages/{id}/feedback | Leave 👍 / 👎 feedback on an answer (public). |
| GET    | /datasources/ | List registered data sources. |
| POST   | /datasources/upload | Upload a TXT/PDF file. |
| POST   | /datasources/add-url | Register an external article URL. |
| DELETE | /datasources/{id} | Delete a data source. |
| POST   | /datasources/{id}/sync | Parse & embed a data source into the vector store. |
| GET    | /datasources/{id}/preview | Download/preview the raw source. |
| GET    | /metrics/ | Basic KPIs: message count, avg latency, sources count. |
| POST   | /clickup/test | Verify ClickUp credentials. |
| POST   | /clickup/tasks | List ClickUp tasks (with sync status). |
| POST   | /clickup/sync | Sync one or more tasks into the vector store. |
| POST   | /clickup/unsync | Remove previously-synced tasks. |
| POST   | /clickup/comments | Fetch comments for a ClickUp task. |
| POST   | /clickup/teams | List available ClickUp teams. |
| POST   | /clickup/spaces | List spaces within a team. |
| POST   | /clickup/lists | List lists within a space. |
| GET    | /connections/ | List saved ClickUp connections. |
| POST   | /connections/ | Create a new connection. |
| GET    | /connections/{id} | Retrieve connection details. |
| PUT    | /connections/{id} | Update an existing connection. |
| DELETE | /connections/{id} | Delete a connection. |
| POST   | /connections/{id}/test | Test stored connection credentials. |

---