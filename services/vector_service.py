"""
Vector store service for managing FAISS operations.
"""
import os
import pickle
import logging
import re
from typing import List, Optional
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader, PyPDFLoader, WebBaseLoader
from sqlmodel import Session, select
from qdrant_client.models import Distance, VectorParams
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models
from config.settings import get_settings
from langchain_community.vectorstores import Qdrant
from db import engine
from models import DataSource
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing vector store operations."""
    
    def __init__(self):
        self.settings = get_settings()
        self._vector_store: Optional[Qdrant] = None
        self._embeddings: Optional[HuggingFaceEmbeddings] = None
        self._client: Optional[QdrantClient] = None

    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        """Get or create the embeddings model."""
        if self._embeddings is None:
            self._embeddings = HuggingFaceEmbeddings(
                model_name=self.settings.embedding_model
            )
        return self._embeddings
    
    @property
    def client(self) -> QdrantClient:
        """Get or create Qdrant client."""
        if self._client is None:
            self._client = QdrantClient(
                url=self.settings.qdrant_url, 
            )
        return self._client
    
    @property
    def vector_store(self) -> Qdrant:
        """Get or create the vector store."""
        if self._vector_store is None:
            self._initialize_vector_store()
        return self._vector_store
    
    def _initialize_vector_store(self):
        """Initialize the Qdrant vector store, loading from disk if available."""
        logger.info("Initializing vector store...")
        
        collection_name = self.settings.qdrant_collection or "Aidly"
        vector_size =  len(self.embeddings.embed_query("hello world"))

       # Ensure collection exists
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection: {collection_name}")
        
        # Initialize vector store
        self._vector_store = Qdrant(
            embeddings=self.embeddings,
            client=self.client,
            collection_name=collection_name
        )
        logger.info(f"New vector store initialized with dimension {vector_size}")

    def load_documents_from_data_folder(self):
        """Load and index documents from the data folder based on database sync status."""

        # Check if the vector store (Qdrant collection) already has documents
        try:
            collection_info = self.client.get_collection(self.settings.qdrant_collection)
            current_doc_count = collection_info.points_count
        except Exception:
            current_doc_count = 0

        if current_doc_count > 0:
            logger.info(f"Vector store already loaded with {current_doc_count} documents")
            return
        
        with Session(engine) as session:
            # Get all synced datasources from database
            synced_sources = session.exec(
                select(DataSource).where(DataSource.is_synced == 1)
            ).all()
            
            if not synced_sources:
                logger.warning("No synced data sources found in database")
                return
                
            logger.info(f"Found {len(synced_sources)} synced data sources")
            
            # Process each synced source
            total_docs_added = 0
            for source in synced_sources:
                try:
                    docs_added = self._process_single_datasource(source)
                    total_docs_added += docs_added
                except Exception as e:
                    logger.error(f"Error processing datasource {source.reference}: {e}")
                    continue
            
            logger.info(f"Total documents added to vector store: {total_docs_added}")
    
    def _process_single_datasource(self, datasource) -> int:
        """Process a single datasource and add it to the vector store."""
        from models import DataSource
        
        docs: List[Document] = []
        
        try:
            if datasource.source_type == "file":
                file_path = datasource.path or os.path.join(self.settings.data_directory, datasource.reference)
                if datasource.reference.lower().endswith((".txt", ".md")):
                    loader = TextLoader(file_path, encoding="utf-8")
                    docs.extend(loader.load())
                elif datasource.reference.lower().endswith(".pdf"):
                    loader = PyPDFLoader(file_path)
                    docs.extend(loader.load())
                else:
                    logger.warning(f"Unsupported file type: {datasource.reference}")
                    return 0
            elif datasource.source_type == "url":
                loader = WebBaseLoader(datasource.reference)
                docs.extend(loader.load())
            else:
                logger.warning(f"Unsupported source type: {datasource.source_type}")
                return 0
        except Exception as e:
            logger.error(f"Error loading datasource {datasource.reference}: {e}")
            return 0
        
        if not docs:
            logger.warning(f"No documents loaded from {datasource.reference}")
            return 0
        
        # Process documents using the standardized splitting logic
        splits = self.process_documents_for_embedding(docs, [datasource.reference], datasource.workspace_id)

        if splits:
            self.vector_store.add_documents(splits)
            logger.info(f"Added {len(splits)} document splits from {datasource.reference}")
            return len(splits)
        
        return 0

    def process_documents_for_embedding(self, docs: List[Document], file_paths: List[str], workspace_id: str) -> List[Document]:
        """
        CENTRALIZED EMBEDDING LOGIC - Process documents based on file type patterns.
        Ensures each split gets source + workspace metadata.
        """
        if not docs:
            return []

        raw_text = "\n".join([doc.page_content for doc in docs])
        all_splits: List[Document] = []

        for path in file_paths:

            # for markdown files
            if path.lower().endswith((".md")):
                section_splits = re.split(r"(?=^## )", raw_text, flags=re.MULTILINE)
                chunks = [s.strip() for s in section_splits if s.strip()]

                all_splits.extend([
                    Document(
                        page_content=chunk,
                        metadata={"source": path, "workspace_id": workspace_id}
                    )
                    for chunk in chunks
                ])
                logger.info(f"Applied section-based splitting for {path}")

            # Documentation files ("_docs.txt")
            elif path.lower().endswith(("_docs.txt")):

                chunks = [chunk.strip() for chunk in raw_text.split("---") if chunk.strip()]
                all_splits.extend([
                    Document(
                        page_content=chunk,
                        metadata={"source": path, "workspace_id": workspace_id}
                    )
                    for chunk in chunks
                ])
                logger.info(f"Applied documentation-based splitting (guide sections) for {path}")

            # ClickUp files
            elif "clickup_" in path.lower():
                for doc in docs:
                    if doc.page_content.strip():
                        all_splits.append(
                            Document(
                                page_content=doc.page_content.strip(),
                                metadata={"source": path, "workspace_id": workspace_id}
                            )
                        )
                logger.info(f"Applied ClickUp-based splitting (single chunks) for {path}")

            # Default: Issue-based splitting 
            else:
                chunks = ["Issue" + chunk.strip() for chunk in raw_text.split("Issue") if chunk.strip()]
                all_splits.extend([
                    Document(
                        page_content=chunk,
                        metadata={"source": path, "workspace_id": workspace_id}
                    )
                    for chunk in chunks
                ])
                logger.info(f"Applied issue-based splitting (support tickets) for {path}")

        return all_splits

    def embed_datasource(self, datasource) -> int:
        """
        Embed a single datasource using the standardized logic.
        Returns the number of document chunks added.
        """
        docs_added = self._process_single_datasource(datasource)
            
        return docs_added
        
    @staticmethod
    def get_workspace_id_from_path(file_path: str) -> str:
        """
        Extracts workspace_id from a path like workspaces/1/file.txt
        """
        print("file path")
        print(file_path)
        parts = file_path.split(os.sep)  # split by directory
        if "workspaces" in parts:
            idx = parts.index("workspaces")
            if idx + 1 < len(parts):
                return parts[idx + 1]  # the folder after 'workspaces'
        return None


    def embed_content_string(self, content: str, source_reference: str) -> int:
        """
        Embed a content string using the standardized logic.
        Returns the number of document chunks added.
        """
        if not content.strip():
            return 0
            
        doc = Document(page_content=content,
                    metadata={"source": source_reference, "workspace": self.get_workspace_id_from_path(source_reference)})
        splits = self.process_documents_for_embedding([doc], [source_reference])
        
        if splits:
            self.vector_store.add_documents(splits)
            logger.info(f"Added {len(splits)} document splits from content string")
            
            
            return len(splits)
        
        return 0

    def _process_documents(self, all_docs: List[Document], file_paths: List[str]) -> List[Document]:
        """Process documents based on file type patterns."""
        # DEPRECATED: Use process_documents_for_embedding instead
        return self.process_documents_for_embedding(all_docs, file_paths)
        
    def add_documents(self, documents: List[Document]):
        """Add documents to the vector store."""
        logger.info(f"Adding {len(documents)} documents to vector store")
        self.vector_store.add_documents(documents)
    
    def similarity_search_with_score(self, query: str, k: int = 5, metadata_filter: dict = None):
        """Perform similarity search with scores."""
        qdrant_filter = None
        if metadata_filter:
            qdrant_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value),
                    )
                    for key, value in metadata_filter.items()
                ]
            )

        return self.vector_store.similarity_search_with_score(
            query, k=k, filter=qdrant_filter
        )

# Global vector store service instance
vector_service = VectorStoreService()


def get_vector_service() -> VectorStoreService:
    """Get the global vector store service instance."""
    return vector_service 