from typing import List
from datetime import datetime
from enum import Enum
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session
from models import Message
from auth import get_current_user
from services.rag_logger import get_rag_logger

router = APIRouter(prefix="/messages", tags=["messages"])

feedback_logger = logging.getLogger("feedback")


class MessageOut(BaseModel):
    id: int
    question: str
    answer: str
    latency_ms: int
    timestamp: datetime

    class Config:
        orm_mode = True


class FeedbackType(str, Enum):
    up = "up"
    down = "down"


class FeedbackIn(BaseModel):
    feedback: FeedbackType


@router.get("/", response_model=List[MessageOut])
def list_messages(
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    msgs = session.exec(select(Message).order_by(Message.timestamp.desc())).all()
    return msgs


@router.post("/{message_id}/feedback")
def leave_feedback(
    message_id: int,
    payload: FeedbackIn,
    request: Request,
    session: Session = Depends(get_session),
):
    # Ensure message exists
    message = session.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Update message with feedback
    message.feedback = payload.feedback
    session.add(message)
    session.commit()

    # Log to traditional feedback logger (legacy)
    client_ip = request.client.host if request.client else "unknown"
    feedback_logger.info(f"{message_id}\t{client_ip}\t{payload.feedback}")
    
    # Log to structured JSONL feedback log
    try:
        rag_logger = get_rag_logger()
        user_id = request.headers.get("X-User-ID") or client_ip
        
        rag_logger.log_feedback(
            message_id=message_id,
            feedback_type=payload.feedback.value,
            original_query=message.question,
            original_response=message.answer,
            user_id=user_id,
            conversation_id=message.conversation_id,
            client_ip=client_ip,
            response_latency_ms=message.latency_ms,
            num_retrieved_docs=None,  # We could enhance this by storing in Message model
            model_used=None  # We could enhance this by storing in Message model
        )
    except Exception as e:
        # Don't fail the request if logging fails
        feedback_logger.error(f"Failed to log structured feedback: {e}")
    
    return {"status": "ok"} 