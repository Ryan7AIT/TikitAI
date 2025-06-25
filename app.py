from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import logging

# ---------------- RAG SETUP ---------------- #
# This code is largely adapted from main.py but wrapped so it can be reused by the web app.

from langchain_community.chat_models import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain import hub
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langgraph.graph import START, StateGraph
from typing_extensions import List, TypedDict
import glob
from langchain_community.document_loaders import TextLoader
import os

# DB and models for logging
from db import get_session, create_db_and_tables, engine
from models import Message, User, Conversation
from sqlmodel import Session, select
import time

# Instantiate models and vector store once at startup
llm = ChatOllama(model="gemma3:4b")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
embedding_dim = len(embeddings.embed_query("hello world"))
index = faiss.IndexFlatL2(embedding_dim)

vector_store = FAISS(
    embedding_function=embeddings,
    index=index,
    docstore=InMemoryDocstore(),
    index_to_docstore_id={},
)

# ---------------- Load documents & build index ---------------- #
file_paths = glob.glob(os.path.join("data", "*.txt"))
all_docs = []
for path in file_paths:
    loader = TextLoader(path, encoding="utf-8")
    all_docs.extend(loader.load())

# If you want to split by custom logic (Issue-based) as in main.py:
raw_text = "\n".join([doc.page_content for doc in all_docs])
chunks = [
    "Issue" + chunk.strip() for chunk in raw_text.split("Issue") if chunk.strip()
]
all_splits = [Document(page_content=chunk) for chunk in chunks]

# Add to vector store
_ = vector_store.add_documents(all_splits)

# ---------------- Prompt & helper functions ---------------- #
base_prompt = hub.pull("rlm/rag-prompt")

custom_template = """You are Aymen, a friendly AI assistant created by DATAFIRST to help users with their questions.

When the user greets you or asks personal questions such as "Who are you?" or "How are you?", reply politely by saying that you are Aymen, an AI assistant created by DATAFIRST, and you're feeling great. Always say you're here to help.

Use the following context to answer the question at the end. If you don't know the answer, simply say you don't know — do not attempt to make one up.

Keep answers short and clear — a maximum of three sentences. End every answer with: "Let me know if you need anything else!"

If the user asks about the company, say: "DATAFIRST is a leading tech company based in Algeria that builds innovative software solutions."

If the user says: "I fixed the problem", reply with: "Congratulations! I'm glad I could help 😊"

---

{context}

Question: {question}

Helpful Answer:"""

custom_prompt = PromptTemplate(
    template=custom_template, input_variables=["context", "question"]
)

class State(TypedDict):
    question: str
    context: List[Document]
    answer: str

def retrieve(state: State):
    retrieved_docs = vector_store.similarity_search(state["question"], k=3)
    return {"context": retrieved_docs}

def generate(state: State):
    docs_content = "\n\n".join(doc.page_content for doc in state["context"])
    messages = custom_prompt.invoke(
            {"question": state["question"], "context": docs_content}
    )
    response = llm.invoke(messages)
    return {"answer": response.content}

# Compile the graph once.
graph_builder = StateGraph(State).add_sequence([retrieve, generate])
graph_builder.add_edge(START, "retrieve")
rag_graph = graph_builder.compile()

def ask_question(question: str) -> str:
    """Helper that runs the RAG pipeline and returns the answer text."""
    try:
        result = rag_graph.invoke({"question": question})
        return result["answer"]
    except Exception as e:
        # Log or handle errors as needed.
        raise e

# ---------------- FastAPI setup ---------------- #
create_db_and_tables()

# Ensure default admin exists
from auth import hash_password
from sqlmodel import select

with Session(engine) as s:
    if not s.exec(select(User).where(User.username == "admin")).first():
        s.add(User(username="admin", hashed_password=hash_password("admin"), is_admin=True))
        s.commit()

app = FastAPI(title="RAG Chat API")

# Import and include API routers
from routers.auth_router import router as auth_router
from routers.data_router import router as data_router
from routers.messages_router import router as messages_router
from routers.conversations_router import router as conversations_router
from routers.metrics_router import router as metrics_router

app.include_router(auth_router)
app.include_router(data_router)
app.include_router(messages_router)
app.include_router(conversations_router)
app.include_router(metrics_router)

class Question(BaseModel):
    question: str
    conversation_id: int | None = None
    model_name: str | None = None

# Create logs directory and loggers
logs_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(logs_dir, exist_ok=True)

interaction_logger = logging.getLogger("interactions")
if not interaction_logger.handlers:
    interaction_logger.setLevel(logging.INFO)
    ih = logging.FileHandler(os.path.join(logs_dir, "interactions.log"))
    ih.setFormatter(logging.Formatter("%(asctime)s\t%(message)s"))
    interaction_logger.addHandler(ih)

feedback_logger = logging.getLogger("feedback")
if not feedback_logger.handlers:
    feedback_logger.setLevel(logging.INFO)
    fh = logging.FileHandler(os.path.join(logs_dir, "feedback.log"))
    fh.setFormatter(logging.Formatter("%(asctime)s\t%(message)s"))
    feedback_logger.addHandler(fh)

@app.post("/chat")
def chat_endpoint(
    payload: Question,
    request: Request,
    session: Session = Depends(get_session),
):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    start = time.time()
    answer = ask_question(payload.question)
    latency_ms = int((time.time() - start) * 1000)

    conv_id = payload.conversation_id
    if conv_id is None:
        first_prompt = payload.question.strip()
        title = (first_prompt[:10] + "…") if len(first_prompt) > 10 else first_prompt
        conv = Conversation(title=title or time.strftime("%Y-%m-%d %H:%M"))
        session.add(conv)
        session.commit()
        session.refresh(conv)
        conv_id = conv.id

    msg = Message(question=payload.question, answer=answer, latency_ms=latency_ms, conversation_id=conv_id)
    session.add(msg)
    session.commit()

    client_ip = request.client.host if request.client else "unknown"
    # Escape tabs/newlines in texts
    safe_q = payload.question.replace("\t", " ").replace("\n", " ")
    safe_a = answer.replace("\t", " ").replace("\n", " ")
    interaction_logger.info(
        f"{msg.id}\tconv:{conv_id}\t{client_ip}\t{latency_ms}ms\tQ: {safe_q}\tA: {safe_a}"
    )

    return {"answer": answer, "latency_ms": latency_ms, "message_id": msg.id, "conversation_id": conv_id}

# Serve the front-end
frontend_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    admin_dir = os.path.join(frontend_dir, "admin")
    if os.path.isdir(admin_dir):
        app.mount("/admin", StaticFiles(directory=admin_dir), name="admin")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/login.html")
    def serve_login():
        return FileResponse(os.path.join(frontend_dir, "login.html"))

    # friendly route without .html
    @app.get("/login")
    def serve_login_no_ext():
        return FileResponse(os.path.join(frontend_dir, "login.html"))
