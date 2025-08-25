"""
Chat router for handling chat requests.
"""
import time
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from db import get_session
from models import Message, Conversation
from services.rag_service import get_rag_service
from services.rag_logger import get_rag_logger, RetrievedDocument
from config.settings import get_settings

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)
interaction_logger = logging.getLogger("interactions")


class Question(BaseModel):
    """Request model for chat questions."""
    question: str = Field(..., min_length=1, max_length=1000)
    conversation_id: int | None = None
    model_name: str | None = None


@router.post("/")
async def chat_endpoint(
    payload: Question,
    request: Request,
    session: Session = Depends(get_session),
):
    """
    Main chat endpoint for processing questions through the RAG pipeline.
    
    Args:
        payload: Question data including the question text and optional conversation ID
        request: FastAPI request object
        session: Database session
        
    Returns:
        Dict containing the answer, latency, message ID, and conversation ID
    """
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    logger.info(f"Processing chat request: {payload.question[:50]}...")
    rag_logger = get_rag_logger()
    
    # Process question through RAG pipeline
    start = time.time()
    error_message = None
    answer = ""
    rag_metrics = {}
    
    try:
        rag_service = get_rag_service()
        answer, rag_metrics = rag_service.ask_question(payload.question)
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error processing question: {e}")
        # Provide a user-friendly error message instead of raising HTTP exception
        answer = "I'm having trouble processing your question right now. Please try again."
    
    latency_ms = int((time.time() - start) * 1000)
    
    # Handle conversation
    conv_id = payload.conversation_id
    if conv_id is None:
        # Create new conversation
        first_prompt = payload.question.strip()
        title = (first_prompt[:10] + "…") if len(first_prompt) > 10 else first_prompt
        conv = Conversation(title=title or time.strftime("%Y-%m-%d %H:%M"))
        session.add(conv)
        session.commit()
        session.refresh(conv)
        conv_id = conv.id
    
    # Save message to database
    msg = Message(
        question=payload.question, 
        answer=answer, 
        latency_ms=latency_ms, 
        conversation_id=conv_id
    )
    session.add(msg)
    session.commit()
    session.refresh(msg)
    
    # Convert retrieved docs info to RetrievedDocument objects for logging
    retrieved_docs = []

    if rag_metrics.get("retrieved_docs_info"):
        for doc_info in rag_metrics["retrieved_docs_info"]:
            retrieved_doc = RetrievedDocument(
                doc_id=doc_info.get("doc_id", "unknown"),
                doc=doc_info.get("doc", ""),
                score=doc_info.get("score", 0.0),
                source=doc_info.get("source", "unknown"),
                workspace_id=doc_info.get("workspace_id", "unknown")
            )
            retrieved_docs.append(retrieved_doc)
    
    # Log the complete interaction to JSONL
    try:
        # Get user ID from request headers or use IP as fallback
        user_id = request.headers.get("X-User-ID") or request.client.host if request.client else "anonymous"
        
        rag_logger.log_interaction(
            user_query=payload.question,
            response=answer,
            latency_ms=latency_ms,
            retrieved_docs=retrieved_docs,
            retrieval_latency_ms=rag_metrics.get("retrieval_latency_ms"),
            generation_latency_ms=rag_metrics.get("generation_latency_ms"),
            user_id=user_id,
            conversation_id=conv_id,
            message_id=msg.id,
            model_name=rag_metrics.get("model_name"),
            temperature=rag_metrics.get("temperature"),
            error=error_message
        )
    except Exception as log_error:
        logger.error(f"Failed to log RAG interaction: {log_error}")
    
    # Log interaction (legacy format)
    client_ip = request.client.host if request.client else "unknown"
    safe_q = payload.question.replace("\t", " ").replace("\n", " ")
    safe_a = answer.replace("\t", " ").replace("\n", " ")
    # interaction_logger.info(
    #     f"{msg.id}\tconv:{conv_id}\t{client_ip}\t{latency_ms}ms\tQ: {safe_q}\tA: {safe_a}"
    # )
    
    logger.info(f"Chat request processed successfully in {latency_ms}ms")
    
    return {
        "answer": answer, 
        "latency_ms": latency_ms, 
        "message_id": msg.id, 
        "conversation_id": conv_id
    } 