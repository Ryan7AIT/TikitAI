from datetime import datetime, timedelta
from typing import Optional, Tuple
import secrets
import hashlib

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select

from config.settings import get_settings
from db import get_session
from models import User, RefreshToken

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer scheme
security = HTTPBearer()

# JWT configuration
settings = get_settings()
SECRET_KEY: str = settings.secret_key
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS: int = settings.refresh_token_expire_days


def hash_password(password: str) -> str:
    """Hash a plaintext password."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a hash."""
    return pwd_context.verify(password, hashed)


def authenticate_user(username: str, password: str, session: Session) -> Optional[User]:
    """Return the user if the username/password are correct."""
    statement = select(User).where(User.username == username)
    user = session.exec(statement).first()
    if user and verify_password(password, user.hashed_password):
        return user
    return None


def create_access_token(user_id: int) -> str:
    """Create a signed JWT access token (short-lived)."""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access"
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def cleanup_expired_tokens(user_id: int, session: Session) -> None:
    """Clean up expired and inactive tokens for a user."""
    # Delete expired tokens
    expired_tokens = session.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.expires_at < datetime.utcnow()
        )
    ).all()
    
    for token in expired_tokens:
        session.delete(token)
    
    # Delete old inactive tokens (keep only recent ones for audit)
    old_inactive = session.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_active == False,
            RefreshToken.created_at < datetime.utcnow() 
        )
    ).all()
    
    for token in old_inactive:
        session.delete(token)


def create_refresh_token(user_id: int, session: Session) -> str:
    """Create a refresh token and store its hash in the database."""
    # Clean up expired/old tokens first
    cleanup_expired_tokens(user_id, session)
    
    # Generate a secure random token
    token = secrets.token_urlsafe(32)
    
    # Hash the token for storage
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    # Set expiration
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Keep only the 2 most recent active tokens per user (multi-device support)
    active_tokens = session.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_active == True
        ).order_by(RefreshToken.created_at.desc())
    ).all()
    
    # If user has 2+ active tokens, deactivate the oldest ones
    if len(active_tokens) >= 2:
        tokens_to_deactivate = active_tokens[1:]  # Keep the most recent one
        for old_token in tokens_to_deactivate:
            old_token.is_active = False
    
    # Store new refresh token
    refresh_token_record = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    session.add(refresh_token_record)
    session.commit()
    
    return token


def create_token_pair(user_id: int, session: Session) -> Tuple[str, str]:
    """Create both access and refresh tokens."""
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id, session)
    return access_token, refresh_token


def verify_refresh_token(token: str, session: Session) -> Optional[User]:
    """Verify a refresh token and return the associated user."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    # Find the refresh token in database
    refresh_token_record = session.exec(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_active == True,
            RefreshToken.expires_at > datetime.utcnow()
        )
    ).first()
    
    if not refresh_token_record:
        return None
    
    # Get the user
    user = session.get(User, refresh_token_record.user_id)
    if not user:
        return None
    
    return user


def invalidate_refresh_token(token: str, session: Session) -> bool:
    """Invalidate a specific refresh token."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    refresh_token_record = session.exec(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_active == True
        )
    ).first()
    
    if refresh_token_record:
        refresh_token_record.is_active = False
        session.commit()
        return True
    
    return False


def invalidate_all_user_tokens(user_id: int, session: Session) -> None:
    """Delete all refresh tokens for a user (logout from all devices)."""
    # Clean up expired tokens first
    cleanup_expired_tokens(user_id, session)
    
    # Delete all remaining tokens for this user
    user_tokens = session.exec(
        select(RefreshToken).where(RefreshToken.user_id == user_id)
    ).all()
    
    for token in user_tokens:
        session.delete(token)
    
    session.commit()


# Dependency to retrieve the current user from the token

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Ensure this is an access token
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
            
        user_id = int(user_id_str)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user = session.get(User, user_id)
    return user



def require_admin(current_user: User = Depends(get_current_user)):
    """Ensure the current user has admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user 


def cleanup_all_expired_tokens(session: Session) -> dict:
    """Clean up all expired tokens from the database."""
    # Delete expired tokens
    expired_tokens = session.exec(
        select(RefreshToken).where(RefreshToken.expires_at < datetime.utcnow())
    ).all()
    expired_count = len(expired_tokens)
    
    for token in expired_tokens:
        session.delete(token)
    
    # Delete old inactive tokens (older than 7 days)
    old_inactive = session.exec(
        select(RefreshToken).where(
            RefreshToken.is_active == False,
            RefreshToken.created_at < datetime.utcnow() - timedelta(days=7)
        )
    ).all()
    inactive_count = len(old_inactive)
    
    for token in old_inactive:
        session.delete(token)
    
    session.commit()
    
    return {
        "expired_tokens_deleted": expired_count,
        "old_inactive_tokens_deleted": inactive_count,
        "total_cleaned": expired_count + inactive_count
    } 