from typing import Any, List, Optional
from datetime import datetime

from auth import get_current_user
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
    user: str = Depends(get_current_user),
):
    title = payload.title or f"Conversation {int(datetime.utcnow().timestamp())}"
    conv = Conversation(title=title, user_id=user.id)
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

class APIResponse(BaseModel):
    data: Optional[Any]
    success: bool
    message: str

@router.get("/", response_model=APIResponse)
def list_conversations(
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    # add order by id descending to get latest conversations first
    user_conversations = session.exec(select(Conversation).where(Conversation.user_id == _.id).order_by(Conversation.id.desc())).all()

    return APIResponse(data=user_conversations, success=True, message="Conversations retrieved successfully.")



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