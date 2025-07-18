"""
Vector store service for managing FAISS operations.
"""
import os
import glob
import logging
from typing import List, Optional

import faiss
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader, PyPDFLoader, WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlmodel import Session, select

from config.settings import get_settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing vector store operations."""
    
    def __init__(self):
        self.settings = get_settings()
        self._vector_store: Optional[FAISS] = None
        self._embeddings: Optional[HuggingFaceEmbeddings] = None
        
    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        """Get or create the embeddings model."""
        if self._embeddings is None:
            self._embeddings = HuggingFaceEmbeddings(
                model_name=self.settings.embedding_model
            )
        return self._embeddings
    
    @property
    def vector_store(self) -> FAISS:
        """Get or create the vector store."""
        if self._vector_store is None:
            self._initialize_vector_store()
        return self._vector_store
    
    def _initialize_vector_store(self):
        """Initialize the FAISS vector store."""
        logger.info("Initializing vector store...")
        
        # Get embedding dimension
        embedding_dim = len(self.embeddings.embed_query("hello world"))
        
        # Create FAISS index
        index = faiss.IndexFlatL2(embedding_dim)
        
        # Initialize vector store
        self._vector_store = FAISS(
            embedding_function=self.embeddings,
            index=index,
            docstore=InMemoryDocstore(),
            index_to_docstore_id={},
        )
        
        logger.info(f"Vector store initialized with dimension {embedding_dim}")
    
    def load_documents_from_data_folder(self):
        """Load and index documents from the data folder based on database sync status."""
        from db import engine
        from models import DataSource
        
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
        splits = self.process_documents_for_embedding(docs, [datasource.reference])
        
        if splits:
            self.vector_store.add_documents(splits)
            logger.info(f"Added {len(splits)} document splits from {datasource.reference}")
            return len(splits)
        
        return 0
    
    def process_documents_for_embedding(self, docs: List[Document], file_paths: List[str]) -> List[Document]:
        """
        CENTRALIZED EMBEDDING LOGIC - Process documents based on file type patterns.
        This is the reference implementation that all embedding should follow.
        """
        if not docs:
            return []
            
        raw_text = "\n".join([doc.page_content for doc in docs])
        
        # Check file type patterns and split accordingly
        if any("_docs.txt" in path.lower() for path in file_paths) or any("_docs.md" in path.lower() for path in file_paths):
            # Use guide-based splitting for documentation files (only for files with "_docs" in name)
            chunks = [chunk.strip() for chunk in raw_text.split("---") if chunk.strip()]
            all_splits = [Document(page_content=chunk) for chunk in chunks]
            logger.info("Applied documentation-based splitting (guide sections)")
            
        elif any("clickup_" in path.lower() for path in file_paths):
            # ClickUp files: keep each task as a single chunk
            all_splits = []
            for doc in docs:
                if doc.page_content.strip():
                    all_splits.append(Document(page_content=doc.page_content.strip()))
            logger.info("Applied ClickUp-based splitting (single chunks)")
            
        else:
            # Use Issue-based splitting for support tickets and regular files
            chunks = [
                "Issue" + chunk.strip() for chunk in raw_text.split("Issue") if chunk.strip()
            ]
            all_splits = [Document(page_content=chunk) for chunk in chunks]
            logger.info("Applied issue-based splitting (support tickets)")
        
        return all_splits
    
    def embed_datasource(self, datasource) -> int:
        """
        Embed a single datasource using the standardized logic.
        Returns the number of document chunks added.
        """
        return self._process_single_datasource(datasource)
    
    def embed_content_string(self, content: str, source_reference: str) -> int:
        """
        Embed a content string using the standardized logic.
        Returns the number of document chunks added.
        """
        if not content.strip():
            return 0
            
        doc = Document(page_content=content)
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
    
    def similarity_search_with_score(self, query: str, k: Optional[int] = None) -> List[tuple]:
        """Perform similarity search with scores."""
        k = k or self.settings.similarity_search_k
        try:
            return self.vector_store.similarity_search_with_score(query, k=k)
        except Exception as e:
            logger.error(f"Error performing similarity search: {e}")
            return []
    
    def reset_vector_store(self):
        """Reset the vector store to empty state."""
        logger.info("Resetting vector store")
        self._vector_store = None
        self._initialize_vector_store()
    
    def get_vector_store_info(self) -> dict:
        """Get information about the current vector store state."""
        try:
            if self._vector_store is None:
                return {"status": "not_initialized", "doc_count": 0}
            
            # Get the number of documents in the vector store
            doc_count = self.vector_store.index.ntotal
            return {
                "status": "initialized", 
                "doc_count": doc_count,
                "embedding_dimension": self.vector_store.index.d
            }
        except Exception as e:
            logger.error(f"Error getting vector store info: {e}")
            return {"status": "error", "error": str(e)}


# Global vector store service instance
vector_service = VectorStoreService()


def get_vector_service() -> VectorStoreService:
    """Get the global vector store service instance."""
    return vector_service 