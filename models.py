from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON, TEXT


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: Optional[str] = Field(default=None, index=True)
    hashed_password: str
    is_admin: bool = False
    current_workspace_id: Optional[str] = Field(default=None, foreign_key="workspace.id")


class UserPreference(SQLModel, table=True):
    """Stores user preferences like language settings."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    preference: str = Field(index=True)  # e.g., "language"
    value: str  # e.g., "fr"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class RefreshToken(SQLModel, table=True):
    """Stores refresh tokens for JWT authentication"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token_hash: str = Field(index=True)
    expires_at: datetime = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)


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
    owner_id: Optional[str] = Field(default=None, foreign_key="workspace.id")
    workspace_id: Optional[int] = Field(default=None, foreign_key="workspace.id")

class Conversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


# ----------------------------- External Integrations ----------------------------- #

# integrations
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


class UserIntegrations(SQLModel, table=True):
    """Tracks user-specific integrations and their connection status."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    integration_id: int = Field(foreign_key="externaldatasource.id")
    is_connected: bool = Field(default=False)
    name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    active_repository_id: Optional[int] = Field(default=None)  
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)

class UserIntegrationCredentials(SQLModel, table=True):
    """Stores user-specific integration credentials."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_integration_id: int = Field(foreign_key="userintegrations.id")
    credentials: dict = Field(sa_column=Column(TEXT), default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)

# ----------------------------- User Roles ----------------------------- #

class Role(SQLModel, table=True):
    """Represents a user role with a set of permissions."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    # Store permissions as a comma-separated string for simplicity
    permissions: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class RoleAssignment(SQLModel, table=True):
    """Associates users with roles (many-to-many)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    role_id: int = Field(foreign_key="role.id")
    user_id: int = Field(foreign_key="user.id")
    assigned_at: datetime = Field(default_factory=datetime.utcnow) 


class Workspace(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    is_active: bool = Field(default=True)
    active_repository_id: Optional[int] = Field(default=None)
    active_repository_branch: Optional[str] = Field(default=None)


class WorkspaceUser(SQLModel, table=True):
    """Many-to-many relationship between workspaces and users"""
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id")
    user_id: int = Field(foreign_key="user.id")
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    role: Optional[str] = Field(default="member")  # "admin", "member", etc.


# ----------------------------- Feedback System ----------------------------- #

class Feedback(SQLModel, table=True):
    """Stores feature requests and bug reports from users"""
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str = Field(index=True)  # "feature" or "bug"
    title: str = Field(max_length=255)
    description: str = Field(sa_column=Column(TEXT))
    category: Optional[str] = Field(default=None, max_length=100)
    priority: str = Field(default="medium")  # "low", "medium", "high"
    status: str = Field(default="pending", index=True)  # "pending", "in-progress", "completed", "rejected"
    votes: int = Field(default=0, index=True)
    author_id: int = Field(foreign_key="user.id")
    workspace_id: Optional[int] = Field(default=None, foreign_key="workspace.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    deleted_at: Optional[datetime] = Field(default=None)


class FeedbackVote(SQLModel, table=True):
    """Tracks which users have voted on which feedback items"""
    id: Optional[int] = Field(default=None, primary_key=True)
    feedback_id: int = Field(foreign_key="feedback.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FeedbackComment(SQLModel, table=True):
    """Comments on feedback items"""
    id: Optional[int] = Field(default=None, primary_key=True)
    feedback_id: int = Field(foreign_key="feedback.id", index=True)
    author_id: int = Field(foreign_key="user.id")
    content: str = Field(sa_column=Column(TEXT))
    votes: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(default=None)


# ----------------------------- Support Ticket System ----------------------------- #

class Ticket(SQLModel, table=True):
    """Support tickets created from user conversations or manually"""
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: Optional[int] = Field(default=None, foreign_key="conversation.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(max_length=200)
    description: str = Field(sa_column=Column(TEXT))
    priority: str = Field(max_length=20, index=True)  # "low", "medium", "high"
    category: str = Field(max_length=50, index=True)  # "bug", "feature", "question", "other"
    status: str = Field(default="open", max_length=50, index=True)  # "open", "in_progress", "resolved", "closed"
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    resolved_at: Optional[datetime] = Field(default=None) 
