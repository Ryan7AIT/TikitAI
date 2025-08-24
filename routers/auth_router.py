from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import Optional
from db import get_session, engine
from models import User
from auth import (
    authenticate_user, 
    create_token_pair, 
    verify_refresh_token,
    invalidate_refresh_token,
    invalidate_all_user_tokens,
    hash_password,
    get_current_user
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshPayload(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginPayload, response: Response, session: Session = Depends(get_session)):
    """Authenticate user and return access + refresh tokens."""
    user = authenticate_user(payload.username, payload.password, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    access_token, refresh_token = create_token_pair(user.id, session)
    
    # Set refresh token as HTTP-only cookie for security
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="strict",
        max_age=30 * 24 * 60 * 60  # 30 days in seconds
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token  # Also return in body for flexibility
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(
    payload: RefreshPayload = None,
    refresh_token_cookie: Optional[str] = Cookie(None, alias="refresh_token"),
    response: Response = None,
    session: Session = Depends(get_session)
):
    """Refresh access token using refresh token."""
    # Try to get refresh token from cookie first, then from request body
    refresh_token = refresh_token_cookie
    if not refresh_token and payload:
        refresh_token = payload.refresh_token
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not provided"
        )
    
    user = verify_refresh_token(refresh_token, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Create new token pair
    new_access_token, new_refresh_token = create_token_pair(user.id, session)
    
    # Update the refresh token cookie
    if response:
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=True,  # Set to True in production with HTTPS
            samesite="strict",
            max_age=30 * 24 * 60 * 60  # 30 days in seconds
        )
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )


@router.post("/logout")
def logout(
    refresh_token_cookie: Optional[str] = Cookie(None, alias="refresh_token"),
    response: Response = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Logout user by invalidating refresh token."""
    # Try to get refresh token from cookie first, then from request body
    refresh_token = refresh_token_cookie
    if refresh_token:
        invalidate_refresh_token(refresh_token, session)
    
    # Clear the refresh token cookie
    if response:
        response.delete_cookie(key="refresh_token")
    
    return {"message": "Successfully logged out"}


@router.post("/logout-all")
def logout_all_devices(
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Logout user from all devices by invalidating all refresh tokens."""
    invalidate_all_user_tokens(current_user.id, session)
    
    # Clear the refresh token cookie
    response.delete_cookie(key="refresh_token")
    
    return {"message": "Successfully logged out from all devices"}


@router.on_event("startup")
def create_admin_user():
    """Ensure default admin user exists."""
    with Session(engine) as session:
        admin = session.exec(select(User).where(User.username == "admin")).first()
        if not admin:
            admin = User(
                username="admin",
                hashed_password=hash_password("admin"),
                is_admin=True,
            )
            session.add(admin)
            session.commit() 