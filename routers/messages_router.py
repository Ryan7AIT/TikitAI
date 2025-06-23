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

    client_ip = request.client.host if request.client else "unknown"
    feedback_logger.info(f"{message_id}\t{client_ip}\t{payload.feedback}")
    return {"status": "ok"} 