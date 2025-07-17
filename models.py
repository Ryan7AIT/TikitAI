from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    is_admin: bool = False


class UserDataSourceAccess(SQLModel, table=True):
    """Tracks which users have access to which datasources"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    datasource_id: int = Field(foreign_key="datasource.id")
    granted_at: datetime = Field(default_factory=datetime.utcnow)
    granted_by: int = Field(foreign_key="user.id")  # Admin who granted access


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    answer: str
    latency_ms: int
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    conversation_id: Optional[int] = Field(default=None, foreign_key="conversation.id")
    feedback: Optional[str] = Field(default=None)


class DataSource(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_type: str  # 'file' or 'url'
    reference: str  # path or URL
    added_at: datetime = Field(default_factory=datetime.utcnow)
    last_synced_at: Optional[datetime] = Field(default=None, index=True)
    size_mb: Optional[float] = Field(default=None) 
    category: Optional[str] = Field(default=None)  
    tags: Optional[str] = Field(default=None)
    is_synced: Optional[int] = Field(default=None)
    path: Optional[str] = Field(default=None)

class Conversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


# ----------------------------- External Integrations ----------------------------- #


class ExternalDataSource(SQLModel, table=True):
    """Tracks available external data source integrations and their connection status."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)  # e.g., "ClickUp", "Notion"
    description: str
    source_type: str  # e.g., "clickup", "notion"
    is_connected: bool = Field(default=False)
    connection_id: Optional[int] = Field(default=None, foreign_key="clickupconnection.id")  # Reference to specific connection
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ClickUpConnection(SQLModel, table=True):
    """Stores reusable ClickUp credential sets so admins don't need to re-enter them."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)  # human label
    api_token: str
    team: str
    list: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True) 