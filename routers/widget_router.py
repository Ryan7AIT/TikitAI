"""
Widget router for handling embeddable chat widget operations.
This enables users to generate widgets for their bots and embed them on external websites.
"""
import secrets
import time
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select, func

from db import get_session
from models import User, Bot, WidgetToken, ChatSession, Message, Workspace, WorkspaceUser
from auth import (
    get_current_user,
    create_widget_token,
    verify_widget_token,
    invalidate_widget_token,
    invalidate_all_bot_tokens,
    refresh_widget_token,
    get_widget_token_from_request
)
from config.settings import get_settings
from services.rag_service import get_rag_service

router = APIRouter(prefix="/widget", tags=["widget"])
settings = get_settings()


# ----------------------------- Request/Response Models ----------------------------- #

class GenerateWidgetRequest(BaseModel):
    """Request to generate a widget token for a bot."""
    bot_id: Optional[int] = None  # Optional - will auto-create if not provided
    bot_name: Optional[str] = None  # Optional custom name for auto-created bot
    workspace_id: Optional[int] = None  # Optional - uses current workspace if not provided


class GenerateWidgetResponse(BaseModel):
    """Response containing widget token and embed code."""
    widget_token: str
    expires_at: datetime
    embed_code: str
    bot_id: int
    bot_name: str


class StartSessionRequest(BaseModel):
    """Request to start a new chat session via widget."""
    visitor_identifier: Optional[str] = None  # Optional unique ID for the visitor


class StartSessionResponse(BaseModel):
    """Response with session details."""
    session_id: str
    bot_name: str
    welcome_message: Optional[str] = "Hello! How can I help you today?"


class SendMessageRequest(BaseModel):
    """Request to send a message in a widget chat session."""
    session_id: str
    message: str = Field(..., min_length=1, max_length=1000)


class SendMessageResponse(BaseModel):
    """Response with bot's answer."""
    answer: str
    message_id: int
    latency_ms: int


class RefreshWidgetTokenRequest(BaseModel):
    """Request to refresh an expired widget token."""
    widget_token: str


class RefreshWidgetTokenResponse(BaseModel):
    """Response with new widget token."""
    widget_token: str
    expires_at: datetime


class RevokeTokenRequest(BaseModel):
    """Request to revoke widget token(s)."""
    bot_id: int
    token_id: Optional[int] = None  # If provided, revoke specific token; else revoke all


class BotResponse(BaseModel):
    """Bot information response."""
    id: int
    name: str
    description: Optional[str]
    workspace_id: int
    is_active: bool
    created_at: datetime
    total_sessions: int
    active_tokens: int


class SessionResponse(BaseModel):
    """Chat session information."""
    id: int
    session_token: str
    visitor_identifier: Optional[str]
    started_at: datetime
    last_activity_at: datetime
    messages_count: int
    is_active: bool


# ----------------------------- Helper Functions ----------------------------- #

def verify_bot_ownership(bot_id: int, user_id: int, session: Session) -> Bot:
    """
    Verify that a user owns a specific bot.
    
    Args:
        bot_id: The ID of the bot
        user_id: The ID of the user
        session: Database session
        
    Returns:
        The Bot object if user owns it
        
    Raises:
        HTTPException: If bot doesn't exist or user doesn't own it
    """
    bot = session.get(Bot, bot_id)
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this bot"
        )
    
    return bot


def generate_session_token() -> str:
    """Generate a unique session token."""
    return f"sess_{secrets.token_urlsafe(24)}"


# ----------------------------- Widget Endpoints ----------------------------- #

@router.post("/generate", response_model=GenerateWidgetResponse)
def generate_widget(
    request: GenerateWidgetRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Generate a widget token for embedding a bot on external websites.
    
    If bot_id is provided:
        - Verifies user owns the bot
        - Uses that specific bot
    
    If bot_id is NOT provided:
        - Tries to find user's most recent active bot
        - If no bot exists, creates one automatically
        - Uses current workspace or creates default workspace
    
    Returns a signed JWT token valid for 7 days and HTML embed code.
    """
    bot = None
    
    if request.bot_id:
        # User specified a bot - verify ownership
        bot = verify_bot_ownership(request.bot_id, current_user.id, session)
    else:
        # No bot_id provided - find or create default bot
        
        # Try to find user's most recent active bot
        bot = session.exec(
            select(Bot)
            .where(Bot.owner_id == current_user.id)
            .where(Bot.is_active == True)
            .order_by(Bot.created_at.desc())
        ).first()
        
        if not bot:
            # No active bot found - create one automatically
            
            # Get workspace_id (use provided, current, or create default)
            workspace_id = request.workspace_id
            
            if not workspace_id and current_user.current_workspace_id:
                workspace_id = current_user.current_workspace_id
            
            if not workspace_id:
                # Try to find any workspace user has access to
                from models import WorkspaceUser
                workspace_user = session.exec(
                    select(WorkspaceUser)
                    .where(WorkspaceUser.user_id == current_user.id)
                ).first()
                
                if workspace_user:
                    workspace_id = workspace_user.workspace_id
                else:
                    # Create a default workspace for this user
                    default_workspace = Workspace(
                        name=f"{current_user.username}'s Workspace",
                        description="Auto-generated workspace for chatbot"
                    )
                    session.add(default_workspace)
                    session.commit()
                    session.refresh(default_workspace)
                    
                    # Add user to workspace
                    workspace_user = WorkspaceUser(
                        workspace_id=default_workspace.id,
                        user_id=current_user.id,
                        role="admin"
                    )
                    session.add(workspace_user)
                    
                    # Set as current workspace
                    current_user.current_workspace_id = default_workspace.id
                    session.add(current_user)
                    session.commit()
                    
                    workspace_id = default_workspace.id
            
            # Create default bot
            bot_name = request.bot_name or f"{current_user.username}'s Chatbot"
            
            bot = Bot(
                name=bot_name,
                description="Auto-generated chatbot for widget embedding",
                workspace_id=workspace_id,
                owner_id=current_user.id,
                system_prompt="You are a helpful and friendly AI assistant. Provide clear, concise, and accurate answers to user questions.",
                is_active=True
            )
            
            session.add(bot)
            session.commit()
            session.refresh(bot)
    
    # Verify bot is active
    if not bot.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bot is inactive. Activate it before generating a widget."
        )
    
    # Create widget token
    widget_token = create_widget_token(bot.id, current_user.id, session)
    
    # Get token expiration
    token_record = session.exec(
        select(WidgetToken)
        .where(WidgetToken.bot_id == bot.id)
        .where(WidgetToken.is_active == True)
        .order_by(WidgetToken.created_at.desc())
    ).first()
    
    expires_at = token_record.expires_at if token_record else datetime.utcnow()
    
    # Generate embed code
    embed_code = f'''<script src="{settings.widget_base_url}/static/widget.js" 
        data-bot-id="{bot.id}" 
        data-token="{widget_token}"
        data-api-base="{settings.widget_base_url}/widget">
</script>'''
    
    return GenerateWidgetResponse(
        widget_token=widget_token,
        expires_at=expires_at,
        embed_code=embed_code,
        bot_id=bot.id,
        bot_name=bot.name
    )


@router.post("/session/start", response_model=StartSessionResponse)
def start_session(
    request: StartSessionRequest,
    widget_payload: dict = Depends(get_widget_token_from_request),
    session: Session = Depends(get_session)
):
    """
    Start a new chat session for a widget visitor.
    
    Requires a valid widget token. Creates a session record and returns session ID.
    """
    bot_id = widget_payload.get("bot_id")
    
    # Verify bot exists and is active
    bot = session.get(Bot, bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if not bot.is_active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot is currently inactive"
        )
    
    # Check active session limit for this bot
    active_sessions_count = session.exec(
        select(func.count(ChatSession.id))
        .where(ChatSession.bot_id == bot_id)
        .where(ChatSession.is_active == True)
    ).first()
    
    if active_sessions_count >= settings.widget_max_sessions_per_bot:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bot has reached maximum concurrent sessions. Please try again later."
        )
    
    # Create new session
    session_token = generate_session_token()
    
    chat_session = ChatSession(
        bot_id=bot_id,
        session_token=session_token,
        visitor_identifier=request.visitor_identifier,
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow()
    )
    
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    
    # Prepare welcome message (could be customized per bot)
    welcome_message = f"Hello! I'm Aidly. How can I help you today?"
    if bot.system_prompt and "welcome" in bot.system_prompt.lower():
        # Extract welcome message from system prompt if available
        # This is a simple implementation - could be enhanced
        welcome_message = bot.system_prompt.split('\n')[0]
    
    return StartSessionResponse(
        session_id=session_token,
        bot_name=bot.name,
        welcome_message=welcome_message
    )


@router.post("/chat", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    widget_payload: dict = Depends(get_widget_token_from_request),
    session: Session = Depends(get_session)
):
    """
    Send a message in a widget chat session.
    
    Requires a valid widget token and session ID. Processes the message through
    the RAG pipeline and returns the bot's response.
    """
    bot_id = widget_payload.get("bot_id")
    
    # Verify session exists and belongs to this bot
    chat_session = session.exec(
        select(ChatSession)
        .where(ChatSession.session_token == request.session_id)
        .where(ChatSession.bot_id == bot_id)
    ).first()
    
    if not chat_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or doesn't belong to this bot"
        )
    
    if not chat_session.is_active:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session has expired. Please start a new session."
        )
    
    # Get bot details
    bot = session.get(Bot, bot_id)
    if not bot or not bot.is_active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot is currently inactive"
        )
    
    # Process message through RAG pipeline
    start = time.time()
    answer = ""
    
    try:
        rag_service = get_rag_service()
        
        # Use bot's workspace for context
        answer, rag_metrics = rag_service.ask_question(
            request.message,
            workspace_id=bot.workspace_id,
            user_id=bot.owner_id  # Use bot owner's context
        )
    except Exception as e:
        # Log error and return friendly message
        print(f"Error processing widget message: {e}")
        answer = "I'm having trouble processing your question right now. Please try again."
    
    latency_ms = int((time.time() - start) * 1000)
    
    # Save message to database
    # message = Message(
    #     question=request.message,
    #     answer=answer,
    #     latency_ms=latency_ms,
    #     chat_session_id=chat_session.id,
    #     user_id=None  # Widget messages don't have a platform user
    # )
    
    # session.add(message)
    
    # Update session activity
    chat_session.last_activity_at = datetime.utcnow()
    chat_session.messages_count += 1
    session.add(chat_session)
    
    session.commit()
    # session.refresh(message)
    
    return SendMessageResponse(
        answer=answer,
        # message_id=message.id,
        message_id=99,
        latency_ms=latency_ms
    )


@router.post("/refresh", response_model=RefreshWidgetTokenResponse)
def refresh_token(
    request: RefreshWidgetTokenRequest,
    session: Session = Depends(get_session)
):
    """
    Refresh an expired widget token.
    
    Accepts an expired widget token and returns a new one if the bot is still active
    and the token is within the grace period.
    """
    new_token = refresh_widget_token(request.widget_token, session)
    
    if not new_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token cannot be refreshed. Please generate a new widget token."
        )
    
    # Get new token expiration
    token_record = session.exec(
        select(WidgetToken)
        .where(WidgetToken.is_active == True)
        .order_by(WidgetToken.created_at.desc())
    ).first()
    
    expires_at = token_record.expires_at if token_record else datetime.utcnow()
    
    return RefreshWidgetTokenResponse(
        widget_token=new_token,
        expires_at=expires_at
    )


@router.post("/revoke")
def revoke_token(
    request: RevokeTokenRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Revoke widget token(s) for a bot.
    
    If token_id is provided, revokes that specific token.
    Otherwise, revokes all active tokens for the bot.
    """
    # Verify bot ownership
    bot = verify_bot_ownership(request.bot_id, current_user.id, session)
    
    if request.token_id:
        # Revoke specific token
        token_record = session.get(WidgetToken, request.token_id)
        
        if not token_record or token_record.bot_id != bot.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found or doesn't belong to this bot"
            )
        
        token_record.is_active = False
        session.add(token_record)
        session.commit()
        
        return {
            "message": "Widget token revoked successfully",
            "tokens_revoked": 1
        }
    else:
        # Revoke all tokens for this bot
        count = invalidate_all_bot_tokens(bot.id, session)
        
        return {
            "message": f"All widget tokens for bot '{bot.name}' revoked successfully",
            "tokens_revoked": count
        }


# ----------------------------- Bot Management Endpoints ----------------------------- #

@router.get("/bots", response_model=List[BotResponse])
def list_user_bots(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    List all bots owned by the current user.
    """
    bots = session.exec(
        select(Bot)
        .where(Bot.owner_id == current_user.id)
        .order_by(Bot.created_at.desc())
    ).all()
    
    result = []
    for bot in bots:
        # Count total sessions
        total_sessions = session.exec(
            select(func.count(ChatSession.id))
            .where(ChatSession.bot_id == bot.id)
        ).first() or 0
        
        # Count active tokens
        active_tokens = session.exec(
            select(func.count(WidgetToken.id))
            .where(WidgetToken.bot_id == bot.id)
            .where(WidgetToken.is_active == True)
            .where(WidgetToken.expires_at > datetime.utcnow())
        ).first() or 0
        
        result.append(BotResponse(
            id=bot.id,
            name=bot.name,
            description=bot.description,
            workspace_id=bot.workspace_id,
            is_active=bot.is_active,
            created_at=bot.created_at,
            total_sessions=total_sessions,
            active_tokens=active_tokens
        ))
    
    return result


class CreateBotRequest(BaseModel):
    """Request to create a new bot."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    workspace_id: int
    system_prompt: Optional[str] = None


@router.post("/bots", response_model=BotResponse)
def create_bot(
    request: CreateBotRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Create a new bot for the current user.
    """
    # Verify workspace exists and user has access
    workspace = session.get(Workspace, request.workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    # Create bot
    bot = Bot(
        name=request.name,
        description=request.description,
        workspace_id=request.workspace_id,
        owner_id=current_user.id,
        system_prompt=request.system_prompt,
        is_active=True
    )
    
    session.add(bot)
    session.commit()
    session.refresh(bot)
    
    return BotResponse(
        id=bot.id,
        name=bot.name,
        description=bot.description,
        workspace_id=bot.workspace_id,
        is_active=bot.is_active,
        created_at=bot.created_at,
        total_sessions=0,
        active_tokens=0
    )


class UpdateBotRequest(BaseModel):
    """Request to update a bot."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None


@router.put("/bots/{bot_id}", response_model=BotResponse)
def update_bot(
    bot_id: int,
    request: UpdateBotRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Update a bot's settings.
    """
    # Verify bot ownership
    bot = verify_bot_ownership(bot_id, current_user.id, session)
    
    # Update fields
    if request.name is not None:
        bot.name = request.name
    if request.description is not None:
        bot.description = request.description
    if request.system_prompt is not None:
        bot.system_prompt = request.system_prompt
    if request.is_active is not None:
        bot.is_active = request.is_active
    
    bot.updated_at = datetime.utcnow()
    
    session.add(bot)
    session.commit()
    session.refresh(bot)
    
    # Get stats
    total_sessions = session.exec(
        select(func.count(ChatSession.id))
        .where(ChatSession.bot_id == bot.id)
    ).first() or 0
    
    active_tokens = session.exec(
        select(func.count(WidgetToken.id))
        .where(WidgetToken.bot_id == bot.id)
        .where(WidgetToken.is_active == True)
        .where(WidgetToken.expires_at > datetime.utcnow())
    ).first() or 0
    
    return BotResponse(
        id=bot.id,
        name=bot.name,
        description=bot.description,
        workspace_id=bot.workspace_id,
        is_active=bot.is_active,
        created_at=bot.created_at,
        total_sessions=total_sessions,
        active_tokens=active_tokens
    )


@router.delete("/bots/{bot_id}")
def delete_bot(
    bot_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Delete a bot and all associated data.
    """
    # Verify bot ownership
    bot = verify_bot_ownership(bot_id, current_user.id, session)
    
    # Revoke all widget tokens
    invalidate_all_bot_tokens(bot.id, session)
    
    # Deactivate all sessions
    sessions = session.exec(
        select(ChatSession).where(ChatSession.bot_id == bot.id)
    ).all()
    
    for chat_session in sessions:
        chat_session.is_active = False
        session.add(chat_session)
    
    # Delete the bot
    session.delete(bot)
    session.commit()
    
    return {"message": f"Bot '{bot.name}' deleted successfully"}


@router.get("/bots/{bot_id}/sessions", response_model=List[SessionResponse])
def list_bot_sessions(
    bot_id: int,
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    List all chat sessions for a bot.
    """
    # Verify bot ownership
    bot = verify_bot_ownership(bot_id, current_user.id, session)
    
    query = select(ChatSession).where(ChatSession.bot_id == bot.id)
    
    if active_only:
        query = query.where(ChatSession.is_active == True)
    
    query = query.order_by(ChatSession.started_at.desc())
    
    sessions = session.exec(query).all()
    
    return [
        SessionResponse(
            id=s.id,
            session_token=s.session_token,
            visitor_identifier=s.visitor_identifier,
            started_at=s.started_at,
            last_activity_at=s.last_activity_at,
            messages_count=s.messages_count,
            is_active=s.is_active
        )
        for s in sessions
    ]
