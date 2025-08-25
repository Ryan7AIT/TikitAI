"""
RAG system logging service for capturing metrics and interactions in JSONL format.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging
from dataclasses import dataclass, asdict

from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedDocument:
    """Represents a retrieved document with metadata."""
    doc_id: str
    doc: str
    score: float
    source: Optional[str] = None
    workspace_id: Optional[str] = None


@dataclass
class RAGLogEntry:
    """Complete RAG interaction log entry."""
    timestamp: str
    session_id: str
    user_id: Optional[str]
    user_query: str
    retrieved_docs: List[Dict[str, Any]]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    response: str
    latency_ms: int
    retrieval_latency_ms: Optional[int]
    generation_latency_ms: Optional[int]
    model_name: Optional[str]
    temperature: Optional[float]
    similarity_threshold: Optional[float]
    num_retrieved: int
    conversation_id: Optional[int]
    message_id: Optional[int]
    error: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the log entry to a dictionary."""
        return asdict(self)


@dataclass
class FeedbackLogEntry:
    """User feedback log entry."""
    timestamp: str
    session_id: str
    message_id: int
    user_id: Optional[str]
    feedback_type: str  # "up" or "down"
    original_query: str
    original_response: str
    response_latency_ms: Optional[int]
    num_retrieved_docs: Optional[int]
    model_used: Optional[str]
    conversation_id: Optional[int]
    client_ip: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the feedback log entry to a dictionary."""
        return asdict(self)


class RAGLogger:
    """Service for logging RAG system interactions and metrics."""
    
    def __init__(self):
        self.settings = get_settings()
        self.log_file_path = Path(self.settings.logs_directory) / "rag_interactions.jsonl"
        self.feedback_log_file_path = Path(self.settings.logs_directory) / "feedback_interactions.jsonl"
        self._ensure_log_directory()
        self._session_id = str(uuid.uuid4())
        
    def _ensure_log_directory(self):
        """Ensure the logs directory exists."""
        log_dir = Path(self.settings.logs_directory)
        log_dir.mkdir(exist_ok=True)
        
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters for English)."""
        if not text:
            return 0
        return max(1, len(text) // 4)
    
    def _write_log_entry(self, entry: RAGLogEntry):
        """Write a log entry to the JSONL file."""
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                json.dump(entry.to_dict(), f, ensure_ascii=False)
                f.write('\n')
        except Exception as e:
            logger.error(f"Failed to write RAG log entry: {e}")
    
    def _write_feedback_entry(self, entry: FeedbackLogEntry):
        """Write a feedback entry to the feedback JSONL file."""
        try:
            with open(self.feedback_log_file_path, 'a', encoding='utf-8') as f:
                json.dump(entry.to_dict(), f, ensure_ascii=False)
                f.write('\n')
        except Exception as e:
            logger.error(f"Failed to write feedback log entry: {e}")
    
    def log_interaction(
        self,
        user_query: str,
        response: str,
        latency_ms: int,
        retrieved_docs: List[RetrievedDocument] = None,
        retrieval_latency_ms: Optional[int] = None,
        generation_latency_ms: Optional[int] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[int] = None,
        message_id: Optional[int] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        error: Optional[str] = None,
        additional_context: Optional[str] = None
    ):
        """
        Log a complete RAG interaction.
        
        Args:
            user_query: The user's input query
            response: The generated response
            latency_ms: Total processing time in milliseconds
            retrieved_docs: List of retrieved documents with scores
            retrieval_latency_ms: Time spent on document retrieval
            generation_latency_ms: Time spent on response generation
            user_id: Optional user identifier
            conversation_id: Database conversation ID
            message_id: Database message ID
            model_name: Name of the LLM used
            temperature: Model temperature setting
            error: Error message if any
            additional_context: Any additional context used in prompt
        """
        try:
            # Process retrieved documents
            retrieved_docs_data = []
            if retrieved_docs:
                for doc in retrieved_docs:
                    doc_data = {
                        "doc_id": doc.doc_id,
                        "doc": doc.doc,
                        "score": doc.score,
                        "source": doc.source,
                        "workspace_id": doc.workspace_id
                    }
                    retrieved_docs_data.append(doc_data)
            
            # Estimate tokens
            prompt_context = additional_context or ""
            full_prompt = f"{prompt_context}\nUser: {user_query}"
            prompt_tokens = self._estimate_tokens(full_prompt)
            completion_tokens = self._estimate_tokens(response)
            total_tokens = prompt_tokens + completion_tokens
            
            # Create log entry
            log_entry = RAGLogEntry(
                timestamp=self._get_timestamp(),
                session_id=self._session_id,
                user_id=user_id,
                user_query=user_query,
                retrieved_docs=retrieved_docs_data,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                response=response,
                latency_ms=latency_ms,
                retrieval_latency_ms=retrieval_latency_ms,
                generation_latency_ms=generation_latency_ms,
                model_name=model_name,
                temperature=temperature,
                similarity_threshold=None,  # Could be added later
                num_retrieved=len(retrieved_docs_data),
                conversation_id=conversation_id,
                message_id=message_id,
                error=error
            )
            
            # Write to log file
            self._write_log_entry(log_entry)
            
            logger.debug(f"Logged RAG interaction: {message_id}")
            
        except Exception as e:
            logger.error(f"Failed to log RAG interaction: {e}")
    
    def log_error(
        self,
        user_query: str,
        error: str,
        latency_ms: int = 0,
        conversation_id: Optional[int] = None,
        message_id: Optional[int] = None,
        user_id: Optional[str] = None
    ):
        """
        Log an error during RAG processing.
        
        Args:
            user_query: The user's input query
            error: Error message
            latency_ms: Time before error occurred
            conversation_id: Database conversation ID
            message_id: Database message ID
            user_id: Optional user identifier
        """
        self.log_interaction(
            user_query=user_query,
            response="",
            latency_ms=latency_ms,
            retrieved_docs=[],
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=user_id,
            error=error
        )
    
    def log_feedback(
        self,
        message_id: int,
        feedback_type: str,
        original_query: str,
        original_response: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[int] = None,
        client_ip: Optional[str] = None,
        response_latency_ms: Optional[int] = None,
        num_retrieved_docs: Optional[int] = None,
        model_used: Optional[str] = None
    ):
        """
        Log user feedback on a response.
        
        Args:
            message_id: Database message ID
            feedback_type: "up" or "down"
            original_query: The original user query
            original_response: The original system response
            user_id: Optional user identifier
            conversation_id: Database conversation ID
            client_ip: Client IP address
            response_latency_ms: Original response latency
            num_retrieved_docs: Number of documents retrieved for original response
            model_used: Model used for original response
        """
        try:
            feedback_entry = FeedbackLogEntry(
                timestamp=self._get_timestamp(),
                session_id=self._session_id,
                message_id=message_id,
                user_id=user_id,
                feedback_type=feedback_type,
                original_query=original_query,
                original_response=original_response,
                response_latency_ms=response_latency_ms,
                num_retrieved_docs=num_retrieved_docs,
                model_used=model_used,
                conversation_id=conversation_id,
                client_ip=client_ip
            )
            
            self._write_feedback_entry(feedback_entry)
            logger.debug(f"Logged feedback for message {message_id}: {feedback_type}")
            
        except Exception as e:
            logger.error(f"Failed to log feedback: {e}")
    
    def get_session_id(self) -> str:
        """Get the current session ID."""
        return self._session_id
    
    def new_session(self) -> str:
        """Start a new session and return the new session ID."""
        self._session_id = str(uuid.uuid4())
        return self._session_id


# Global RAG logger instance
rag_logger = RAGLogger()


def get_rag_logger() -> RAGLogger:
    """Get the global RAG logger instance."""
    return rag_logger
