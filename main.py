from langchain_community.chat_models import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
import bs4
from langchain import hub
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import START, StateGraph
from typing_extensions import List, TypedDict
import glob
from langchain_community.document_loaders import TextLoader
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain.chat_models import init_chat_model
from qdrant_client.models import Distance, VectorParams
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models

lolcallm = "llama3.2:latest"
apillm = "gemma-3-1b-it"
GOOGLE_API_KEY="AIzaSyDSW8g-DrBwRYEpuBAgjJHCKOYW0rYK0BQ"
is_local = False

if is_local:
    llm = ChatOllama(model=lolcallm)
else:
    llm = init_chat_model(
        model=apillm,
        model_provider="google_genai",
        api_key=GOOGLE_API_KEY,
    )

# embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
# use mutlilang model
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

embedding_dim = len(embeddings.embed_query("hello world"))
index = faiss.IndexFlatL2(embedding_dim)
client = QdrantClient('http://localhost:6333')
vector_size = len(embeddings.embed_query("sample text"))

# Always create the vector_store connection
vector_store = QdrantVectorStore(
    client=client,
    collection_name="test",
    embedding=embeddings,
)

# Only create collection and embed documents if collection doesn't exist
if not client.collection_exists("test"):
    client.create_collection(
        collection_name="test",
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
    )

    # step1: load the data from data/.txt files
    file_paths = glob.glob("data/*.txt")
    docs = []
    for path in file_paths:
        loader = TextLoader(path, encoding='utf-8')
        docs.extend(loader.load())

    # docs = loader.load()

    # print(docs[0])

    # Methode1: split by character count
    # text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
    # all_splits = text_splitter.split_documents(docs)
    # print(len(all_splits))

    # Methode2: split by issue
    # Step 1: Combine all your text into one big string
    raw_text = "\n".join([doc.page_content for doc in docs])

    # Step 2: Split the text by the keyword "Issue"
    issues = raw_text.split("Issue")

    # Step 3: Re-add the "Issue" word and clean
    chunks = ["Issue" + chunk.strip() for chunk in issues if chunk.strip()]

    # Step 4: Wrap each chunk in a Document
    all_splits = [Document(page_content=chunk) for chunk in chunks]

    for i, document in enumerate(all_splits):
        if i < 2:
            document.metadata["source"] = f"first"
        elif i < 3:
            document.metadata["source"] = f"beginning"
        else:
            document.metadata["source"] = "end"

    # Index the chunks
    _=vector_store.add_documents(all_splits)
    print("Collection created and documents embedded successfully!")
else:
    print("Collection already exists. Using existing collection without re-embedding documents.")

template = """Use the following pieces of context to answer the question at the end.
If you don't know the answer, just say that you don't know, don't try to make up an answer.
Use three sentences maximum and keep the answer as concise as possible.
Always say "thanks for asking!" at the end of the answer.

{context}

Question: {question}

Helpful Answer:"""

custom_prompt = PromptTemplate(template=template, input_variables=["context", "question"])

# Define state for application
class State(TypedDict):
    question: str
    context: List[Document]
    answer: str

# Define application steps

def retrieve(state: State):
    retrieved_docs = vector_store.similarity_search(state["question"])
    return {"context": retrieved_docs}


def generate(state: State):
    docs_content = "\n\n".join(doc.page_content for doc in state["context"])
    messages = custom_prompt.invoke({"question": state["question"], "context": docs_content})
    response = llm.invoke(messages)
    return {"answer": response.content}

# Compile application and test
graph_builder = StateGraph(State).add_sequence([retrieve, generate])
graph_builder.add_edge(START, "retrieve")
graph = graph_builder.compile()

# Test the application
# response = graph.invoke({"question": "what is overlapping promotions solution?"})
# print(response["answer"])



retrieved_docs = vector_store.similarity_search(
    "showing not all families in statisic",
    k=3,
    filter=models.Filter(
        must=[
            models.FieldCondition(
                key="metadata.source",
                match=models.MatchValue(value="end")
            )
        ]
    )
)
print(f"Retrieved {len(retrieved_docs)} documents:")
for doc in retrieved_docs:
    print("docs i: ----------------------------")
    print(doc.page_content, doc.metadata)
