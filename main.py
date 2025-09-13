from langchain_community.chat_models import ChatOllama
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings

import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
import bs4
from langchain import hub
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import START, StateGraph,MessagesState
import re
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
import time
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage
from langgraph.graph import END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

lolcallm = "llama3.2:latest"
apillm = "gemini-2.5-flash"
GOOGLE_API_KEY="AIzaSyDSW8g-DrBwRYEpuBAgjJHCKOYW0rYK0BQ"
is_local = False

# from translator import translate_text


# print("start translation======================================")

# question = "Comment je peut utliser objective par famille"
# translated = translate_text(question)
# print("Translated:", translated)


if is_local:
    llm = ChatOllama(model=lolcallm)
else:
    llm = init_chat_model(
        model=apillm,
        model_provider="google_genai",
        api_key=GOOGLE_API_KEY,
    )

# embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2") # BAD RESULT EVEN IN ENGLISH
# use mutlilang model
# embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2") #BEST MODEL SO FARE
# embeddings = HuggingFaceEmbeddings(model_name="Qwen/Qwen3-Embedding-0.6B") #BAD RESULT IN FRENCH
# embeddings = HuggingFaceEmbeddings(model_name="Qwen/Qwen3-Embedding-4B")
# embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-large-instruct")
# embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2") #best model so far
# embeddings = HuggingFaceEmbeddings(model_name="google/embeddinggemma-300m") 

# from langchain_community.embeddings import HuggingFaceEmbeddings

# Wrap HuggingFace embeddings with Gemma-specific prompts
# class GemmaEmbeddingsWithPrompts(HuggingFaceEmbeddings):
#     def embed_query(self, text: str):
#         # Gemma expects a "query" prompt
#         prompt = f"task: search result | query: {text}"
#         return super().embed_query(prompt)

#     def embed_documents(self, texts: list[str]):
#         # Gemma expects a "document" prompt
#         prompts = [f"title: none | text: {doc}" for doc in texts]
#         return super().embed_documents(prompts)

# embeddings = GemmaEmbeddingsWithPrompts(model_name="google/embeddinggemma-300m")

embeddings = HuggingFaceEmbeddings(
    model_name="google/embeddinggemma-300m",
    query_encode_kwargs={"prompt_name": "query"},
    encode_kwargs={"prompt_name": "document"}
)

# embedding_dim = len(embeddings.embed_query("hello world"))
# index = faiss.IndexFlatL2(embedding_dim)
client = QdrantClient('http://localhost:6333')
vector_size = len(embeddings.embed_query("sample text"))

# Create collection if it doesn't exist
if not client.collection_exists("test"):
    client.create_collection(
        collection_name="test",
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
    )
    should_embed = True
else:
    # Check if collection is empty
    collection_info = client.get_collection("test")
    should_embed = collection_info.points_count == 0

# Create vector store
vector_store = QdrantVectorStore(
    client=client,
    collection_name="test",
    embedding=embeddings,
)



# Only embed documents if needed
print("________________________________________Start embedding______________________________________")
start_time = time.time()
if should_embed:
    # step1: load the data from data/workspaces/*.md files
    file_paths = glob.glob("data/workspaces/**/*.md")
    print(f"Found {len(file_paths)} files to process.")
    
    all_splits = []
    
    # Process each file individually (like in vector_service.py)
    for path in file_paths:
        loader = TextLoader(path, encoding='utf-8')
        docs = loader.load()
        
        # Get the content from this specific file
        raw_text = "\n".join([doc.page_content for doc in docs])
        
        # Extract main title (# header) to prepend to each section
        main_title = ""
        title_match = re.search(r'^# (.+)$', raw_text, re.MULTILINE)
        if title_match:
            main_title = f"# {title_match.group(1)}\n\n"
        
        # Split by ## sections (like in vector_service.py)
        section_splits = re.split(r"(?=^## )", raw_text, flags=re.MULTILINE)
        # remove white spaces and empty chunks
        chunks = [chunk.strip() for chunk in section_splits if chunk.strip()]
        
        # Filter out the title-only chunk and prepend title to section chunks
        processed_chunks = []
        for chunk in chunks:
            # Skip if it's just the title (starts with # but has no ## sections)
            if chunk.startswith('#') and not '##' in chunk:
                continue
            # If it's a ## section, prepend the main title
            elif chunk.startswith('##'):
                processed_chunks.append(main_title + chunk)
            # Handle any other content (shouldn't happen but just in case)
            else:
                processed_chunks.append(chunk)
        
        # Create documents with metadata for each chunk
        file_splits = [
            Document(
                page_content=chunk,
                metadata={"source": path}
            ) 
            for chunk in processed_chunks
        ]
        
        all_splits.extend(file_splits)
        print(f"Processed {path}: {len(file_splits)} chunks")

    # Index the chunks
    _=vector_store.add_documents(all_splits)
    print("Collection created and documents embedded successfully!")
else:
    print("Collection already exists. Using existing collection without re-embedding documents.")
end_time = time.time()
print(f"Embedding completed in {end_time - start_time:.2f} seconds.")





start_time = time.time()
retrieved_docs = vector_store.similarity_search_with_score(
    "hey how are you!",
    k=3
)
end_time = time.time()
print(f"Retrieved {len(retrieved_docs)} documents in {end_time - start_time:.2f} seconds:")
for doc, score in retrieved_docs:
    print(f"Document: ----------------------------")
    print(doc.page_content)
    print("score: ")
    print(score)
    print(f"Document: ----------------------------")


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

@tool(response_format='content_and_artifact')
def retrieve(query: str):
    """Search and Retrieve relevant documents from the Knowledge Base to answer user questions."""
    retrieved_docs = vector_store.similarity_search(query)
    serialized_docs = "\n\n".join(
        (f"Source: {doc.metadata}\nContent: {doc.page_content}") for doc in retrieved_docs
    )
    return serialized_docs, retrieved_docs

# Step 1: Generate an AIMessage that may include a tool-call to be sent.
def query_or_respond(state: MessagesState):
    """Generate tool call for retrieval or respond."""
    llm_with_tools = llm.bind_tools([retrieve])
    response = llm_with_tools.invoke(state["messages"])
    # MessagesState appends messages to state instead of overwriting
    return {"messages": [response]}

# Step 2: Execute the retrieval.
tools = ToolNode([retrieve])

# Step 3: Generate a response using the retrieved content.
def generate(state: MessagesState):
    """Generate answer."""
    # Get generated ToolMessages
    recent_tool_messages = []
    for message in reversed(state["messages"]):
        if message.type == "tool":
            recent_tool_messages.append(message)
        else:
            break
    tool_messages = recent_tool_messages[::-1]

    # Format into prompt
    docs_content = "\n\n".join(doc.content for doc in tool_messages)
    system_message_content = (
        "You are an assistant for question-answering tasks. "
        "Use the following pieces of retrieved context to answer "
        "the question. If you don't know the answer, say that you "
        "don't know. Use three sentences maximum and keep the "
        "answer concise."
        "\n\n"
        f"{docs_content}"
    )

    conversation_messages = [
        message
        for message in state["messages"]
        if message.type in ("human", "system")
        or (message.type == "ai" and not message.tool_calls)
    ]
    prompt = [SystemMessage(system_message_content)] + conversation_messages

    # Run
    response = llm.invoke(prompt)
    return {"messages": [response]}


# def generateOLD(state: State):
#     docs_content = "\n\n".join(doc.page_content for doc in state["context"])
#     messages = custom_prompt.invoke({"question": state["question"], "context": docs_content})
#     response = llm.invoke(messages)
#     return {"answer": response.content}

# Compile application and test (old style without tools)
# graph_builder = StateGraph(State).add_sequence([retrieve, generate])
# graph_builder.add_edge(START, "retrieve")
# graph = graph_builder.compile()





# graph_builder = StateGraph(MessagesState)
# graph_builder.add_node(query_or_respond)
# graph_builder.add_node(tools)
# graph_builder.add_node(generate)
# graph_builder.set_entry_point("query_or_respond")
# graph_builder.add_conditional_edges(
#     "query_or_respond",
#     tools_condition,
#     {END: END, "tools": "tools"},
# )

# graph_builder.add_edge("tools", "generate")
# graph_builder.add_edge("generate", END)



# Test the application
# response = graph.invoke({"question": "How can i use objective per family"})
# print(response["answer"])


# # Test the application with streaming
# print("Question: How can i use objective per family")
# print("Answer: ", end="", flush=True)

# for message, metadata  in graph.stream({"question": "How can i use objective per family"}, stream_mode="messages"):
#     print(message.content, end="|")


# input_message = "Hello"


# memory = MemorySaver()
# graph = graph_builder.compile(checkpointer=memory)

# # Specify an ID for the thread
# config = {"configurable": {"thread_id": "a1b2c3"}}

# # 
# for step in graph.stream(
#     {"messages": [HumanMessage(content="explain it to me")]},
#     stream_mode="values",
#     config=config,
# ):
#     step["messages"][-1].pretty_print()



