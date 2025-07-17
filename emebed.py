from langchain_community.document_loaders import TextLoader
import glob
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS

# this file is for testing the embeddings model

# Get all .txt files in the 'data' folder 
file_paths = glob.glob("data/*.txt")

# Load all documents
docs = []
for path in file_paths:
    loader = TextLoader(path, encoding='utf-8')  # use utf-8 unless you know it's different
    docs.extend(loader.load())

# Print loaded documents
# print(docs[0].metadata)

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, add_start_index=True)

all_splits = text_splitter.split_documents(docs)

# print(len(all_splits))

# embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
# use mutlilang model
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

texts = [doc.page_content for doc in all_splits]
vectors = embeddings.embed_documents(texts)

# print(f"Generated vectors of length {len(vectors[0])}")

# Store vectors in a vector store
embedding_dim = len(embeddings.embed_query("hello world"))
index = faiss.IndexFlatL2(embedding_dim)

vector_store = FAISS(
    embedding_function=embeddings,
    index=index,
    docstore=InMemoryDocstore(),
    index_to_docstore_id={},
)

ids = vector_store.add_documents(all_splits)


results = vector_store.similarity_search(
    "Overlapping Promotions"
)

print(results[0])



