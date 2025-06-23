from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    is_admin: bool = False


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    answer: str
    latency_ms: int
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    conversation_id: Optional[int] = Field(default=None, foreign_key="conversation.id")


class DataSource(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_type: str  # 'file' or 'url'
    reference: str  # path or URL
    added_at: datetime = Field(default_factory=datetime.utcnow)
    last_synced_at: Optional[datetime] = Field(default=None, index=True)


class Conversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True) 