from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, delete

from db import get_session
from models import Conversation, Message

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime

    class Config:
        orm_mode = True


class ConversationCreate(BaseModel):
    title: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: str


@router.post("/", response_model=ConversationOut)
def create_conversation(
    payload: ConversationCreate,
    session: Session = Depends(get_session),
):
    title = payload.title or f"Conversation {int(datetime.utcnow().timestamp())}"
    conv = Conversation(title=title)
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv


@router.put("/{conv_id}", response_model=ConversationOut)
def update_conversation(conv_id: int, payload: ConversationUpdate, session: Session = Depends(get_session)):
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.title = payload.title
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv


@router.delete("/{conv_id}")
def delete_conversation(conv_id: int, session: Session = Depends(get_session)):
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # delete messages first
    session.exec(delete(Message).where(Message.conversation_id == conv_id))
    session.delete(conv)
    session.commit()
    return {"status": "deleted"}


@router.get("/", response_model=List[ConversationOut])
def list_conversations(
    session: Session = Depends(get_session),
):
    return session.exec(select(Conversation).order_by(Conversation.created_at.desc())).all()


class MessageOut(BaseModel):
    id: int
    question: str
    answer: str
    timestamp: datetime
    feedback: Optional[str] = None

    class Config:
        orm_mode = True


@router.get("/{conv_id}/messages", response_model=List[MessageOut])
def get_conversation_messages(
    conv_id: int,
    session: Session = Depends(get_session),
):
    if not session.get(Conversation, conv_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return session.exec(select(Message).where(Message.conversation_id == conv_id).order_by(Message.timestamp)).all() 