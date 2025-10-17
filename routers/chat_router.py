"""
Chat router for handling chat requests.
"""
import time
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from db import get_session
from models import Message, Conversation, User, Ticket
from services.rag_service import get_rag_service
from services.rag_logger import get_rag_logger, RetrievedDocument
from config.settings import get_settings
from auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)
interaction_logger = logging.getLogger("interactions")


class Question(BaseModel):
    """Request model for chat questions."""
    question: str = Field(..., min_length=1, max_length=1000)
    conversation_id: int | None = None
    model_name: str | None = None
    is_system_message: bool = False


class TicketData(BaseModel):
    """Ticket data structure."""
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    priority: str = Field(..., pattern="^(low|medium|high)$")
    category: str = Field(..., pattern="^(bug|feature|question|other)$")


class GenerateTicketRequest(BaseModel):
    """Request model for generating a ticket."""
    conversation_id: int | None = None


class GenerateTicketResponse(BaseModel):
    """Response model for generated ticket."""
    ticket: TicketData


class SubmitTicketRequest(BaseModel):
    """Request model for submitting a ticket."""
    conversation_id: int | None = None
    ticket: TicketData


class SubmitTicketResponse(BaseModel):
    """Response model for submitted ticket."""
    success: bool
    ticket_id: int | None = None
    ticket_url: str | None = None
    message: str


@router.post("/")
async def chat_endpoint(
    payload: Question,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Main chat endpoint for processing questions through the RAG pipeline.
    
    Args:
        payload: Question data including the question text and optional conversation ID
        request: FastAPI request object
        current_user: The authenticated user making the request
        session: Database session
        
    Returns:
        Dict containing the answer, latency, message ID, and conversation ID
    """
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    # Check if user has a current workspace
    if not current_user.current_workspace_id:
        raise HTTPException(status_code=400, detail="User must have an active workspace")
    
    logger.info(f"Processing chat request for user {current_user.id} in workspace {current_user.current_workspace_id}: {payload.question[:50]}...")
    rag_logger = get_rag_logger()
    
    # Process question through RAG pipeline
    start = time.time()
    error_message = None
    answer = ""
    rag_metrics = {}
    
    try:
        rag_service = get_rag_service()
        answer, rag_metrics = rag_service.ask_question(
            payload.question, 
            workspace_id=current_user.current_workspace_id,
            user_id=current_user.id
        )
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
        conv = Conversation(title=title or time.strftime("%Y-%m-%d %H:%M"), user_id=current_user.id, workspace_id=current_user.current_workspace_id)
        session.add(conv)
        session.commit()
        session.refresh(conv)
        conv_id = conv.id
    
    # Save message to database
    msg = Message(
        question=payload.question, 
        answer=answer, 
        latency_ms=latency_ms, 
        conversation_id=conv_id,
        user_id=current_user.id
    )
    session.add(msg)
    session.commit()
    session.refresh(msg)

    if payload.is_system_message:
        return {
            "answer": "Your ticket has been created successfully. You will receive an update when it is processed. Thank you!",
            "latency_ms": latency_ms, 
            "message_id": msg.id, 
            "conversation_id": conv_id
        }
    
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
        # Use the current user's ID instead of extracting from headers
        user_id = current_user.id
        
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
            error=error_message,
            # Translation information
            source_language=rag_metrics.get("source_language"),
            response_language=rag_metrics.get("response_language"),
            was_translated=rag_metrics.get("was_translated"),
            original_question=rag_metrics.get("original_question"),
            translated_question=rag_metrics.get("translated_question")
        )
    except Exception as log_error:
        logger.error(f"Failed to log RAG interaction: {log_error}")
    
    logger.info(f"Chat request processed successfully in {latency_ms}ms")
    
    return {
        "answer": answer, 
        "latency_ms": latency_ms, 
        "message_id": msg.id, 
        "conversation_id": conv_id
    }


@router.post("/generate-ticket", response_model=GenerateTicketResponse)
async def generate_ticket_endpoint(
    payload: GenerateTicketRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Generate a support ticket from a conversation using AI analysis.
    
    Args:
        payload: Request containing conversation_id (optional)
        current_user: The authenticated user making the request
        session: Database session
        
    Returns:
        Generated ticket data with title, description, priority, and category
    """
    logger.info(f"Generating ticket for user {current_user.id}, conversation: {payload.conversation_id}")
    
    # If no conversation_id provided, return a template
    if payload.conversation_id is None:
        return GenerateTicketResponse(
            ticket=TicketData(
                title="New Support Ticket",
                description="Please describe your issue in detail...",
                priority="medium",
                category="question"
            )
        )
    
    # Verify conversation exists and belongs to user
    conversation = session.get(Conversation, payload.conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if conversation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this conversation")
    
    # Retrieve all messages from the conversation
    messages = session.query(Message).filter(
        Message.conversation_id == payload.conversation_id
    ).order_by(Message.timestamp).all()
    
    if not messages:
        raise HTTPException(status_code=400, detail="Conversation has no messages")
    
    # TODO: Replace this dummy implementation with actual LLM-based analysis
    # For now, create a dummy ticket based on the first message
    first_message = messages[0]
    conversation_summary = f"{len(messages)} message(s) exchanged"
    
    # Dummy ticket generation (to be replaced with LLM logic)
    dummy_ticket = TicketData(
        title=f"Support Request: {first_message.question[:50]}..." if len(first_message.question) > 50 else f"Support Request: {first_message.question}",
        description=f"User initiated a conversation with the following question:\n\n{first_message.question}\n\nConversation contains {conversation_summary}.\n\nLast response: {messages[-1].answer[:200]}..." if len(messages[-1].answer) > 200 else messages[-1].answer,
        priority="medium",  # TODO: Determine based on conversation analysis
        category="question"  # TODO: Categorize based on content analysis
    )
    
    logger.info(f"Generated dummy ticket for conversation {payload.conversation_id}")
    return GenerateTicketResponse(ticket=dummy_ticket)


@router.post("/submit-ticket", response_model=SubmitTicketResponse)
async def submit_ticket_endpoint(
    payload: SubmitTicketRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Submit and create a support ticket in the database.
    
    Args:
        payload: Request containing ticket data and optional conversation_id
        current_user: The authenticated user making the request
        session: Database session
        
    Returns:
        Success response with ticket_id, ticket_url, and confirmation message
    """
    logger.info(f"Submitting ticket for user {current_user.id}, conversation: {payload.conversation_id}")
    
    try:
        # Verify conversation exists if provided
        if payload.conversation_id is not None:
            conversation = session.get(Conversation, payload.conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            if conversation.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied to this conversation")
        
        # Validate priority and category
        valid_priorities = ["low", "medium", "high"]
        valid_categories = ["bug", "feature", "question", "other"]
        
        if payload.ticket.priority not in valid_priorities:
            raise HTTPException(status_code=400, detail=f"Invalid priority. Must be one of: {', '.join(valid_priorities)}")
        
        if payload.ticket.category not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}")
        
        # Create the ticket
        new_ticket = Ticket(
            conversation_id=payload.conversation_id,
            user_id=current_user.id,
            title=payload.ticket.title,
            description=payload.ticket.description,
            priority=payload.ticket.priority,
            category=payload.ticket.category,
            status="open"
        )
        
        session.add(new_ticket)
        session.commit()
        session.refresh(new_ticket)
        
        # Generate ticket URL (modify based on your actual support system URL structure)
        ticket_url = f"https://support.yourapp.com/tickets/{new_ticket.id}"
        
        logger.info(f"Successfully created ticket {new_ticket.id} for user {current_user.id}")
        
        return SubmitTicketResponse(
            success=True,
            ticket_id=new_ticket.id,
            ticket_url=ticket_url,
            message=f"✅ Your support ticket has been successfully created! You can follow its status at: {ticket_url}"
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error creating ticket: {e}")
        return SubmitTicketResponse(
            success=False,
            message="We encountered an error while creating your ticket. Please try again or contact support@yourapp.com"
        )
 