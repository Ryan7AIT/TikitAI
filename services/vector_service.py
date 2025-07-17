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
from langchain_community.document_loaders import TextLoader

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
        """Load and index documents from the data folder."""
        file_paths = glob.glob(os.path.join(self.settings.data_directory, "*.txt"))
        
        if not file_paths:
            logger.warning(f"No .txt files found in {self.settings.data_directory}")
            return
            
        logger.info(f"Found {len(file_paths)} files: {file_paths}")
        
        try:
            all_docs = []
            for path in file_paths:
                loader = TextLoader(path, encoding="utf-8")
                all_docs.extend(loader.load())
            
            if not all_docs:
                logger.warning("No documents loaded")
                return
                
            logger.info(f"Loaded {len(all_docs)} documents")
            
            # Process documents based on file type patterns
            all_splits = self._process_documents(all_docs, file_paths)
            
            # Add to vector store
            if all_splits:
                self.vector_store.add_documents(all_splits)
                logger.info(f"Added {len(all_splits)} document splits to vector store")
            
        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            raise
    
    def _process_documents(self, all_docs: List[Document], file_paths: List[str]) -> List[Document]:
        """Process documents based on file type patterns."""
        raw_text = "\n".join([doc.page_content for doc in all_docs])
        
        # Check file type patterns and split accordingly
        if any("_docs.txt" in path.lower() for path in file_paths):
            # Use guide-based splitting for documentation files
            chunks = [chunk.strip() for chunk in raw_text.split("---") if chunk.strip()]
            all_splits = [Document(page_content=chunk) for chunk in chunks]
            logger.info("Applied documentation-based splitting")
            
        elif any("clickup_" in path.lower() for path in file_paths):
            # Split each file as one chunk
            all_splits = []
            for doc in all_docs:
                all_splits.append(Document(page_content=doc.page_content.strip()))
            logger.info("Applied ClickUp-based splitting")
            
        else:
            # Use Issue-based splitting for support tickets
            chunks = [
                "Issue" + chunk.strip() for chunk in raw_text.split("Issue") if chunk.strip()
            ]
            all_splits = [Document(page_content=chunk) for chunk in chunks]
            logger.info("Applied issue-based splitting")
        
        return all_splits
    
    def add_documents(self, documents: List[Document]):
        """Add documents to the vector store."""
        try:
            self.vector_store.add_documents(documents)
            logger.info(f"Added {len(documents)} documents to vector store")
        except Exception as e:
            logger.error(f"Error adding documents to vector store: {e}")
            raise
    
    def similarity_search_with_score(self, query: str, k: Optional[int] = None) -> List[tuple]:
        """Perform similarity search with scores."""
        k = k or self.settings.similarity_search_k
        try:
            return self.vector_store.similarity_search_with_score(query, k=k)
        except Exception as e:
            logger.error(f"Error performing similarity search: {e}")
            raise
    
    def reset_vector_store(self):
        """Reset the vector store to empty state."""
        logger.info("Resetting vector store...")
        self._vector_store = None
        self._initialize_vector_store()
        logger.info("Vector store reset completed")


# Global vector store service instance
vector_service = VectorStoreService()


def get_vector_service() -> VectorStoreService:
    """Get the global vector store service instance."""
    return vector_service 