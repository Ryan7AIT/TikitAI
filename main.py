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


llm = ChatOllama(model="llama3.2:latest")

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

embedding_dim = len(embeddings.embed_query("hello world"))
index = faiss.IndexFlatL2(embedding_dim)

vector_store = FAISS(
    embedding_function=embeddings,
    index=index,
    docstore=InMemoryDocstore(),
    index_to_docstore_id={},
)

# step1: load the data from data/.txt files
file_paths = glob.glob("data/*.txt")
docs = []
for path in file_paths:
    loader = TextLoader(path, encoding='utf-8')
    docs.extend(loader.load())

docs = loader.load()

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

# Index the chunks
_=vector_store.add_documents(all_splits)

# Define prompt for question-answering
# N.B. for non-US LangSmith endpoints, you may need to specify
# api_url="https://api.smith.langchain.com" in hub.pull.
prompt = hub.pull("rlm/rag-prompt")

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
response = graph.invoke({"question": "what is overlapping promotions solution?"})
print(response["answer"])


