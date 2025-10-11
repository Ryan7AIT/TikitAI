"""
User router for handling user-specific requests like preferences.
"""
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db import get_session
from models import User, UserPreference
from auth import get_current_user

router = APIRouter(prefix="/user", tags=["user"])
logger = logging.getLogger(__name__)


class LanguagePreference(BaseModel):
    """Request model for updating language preference."""
    language: str = Field(..., min_length=1, max_length=10)


@router.post("/language")
async def update_language_preference(
    payload: LanguagePreference,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Update the user's language preference.
    
    Args:
        payload: Language preference data
        current_user: The authenticated user
        session: Database session
        
    Returns:
        Dict containing success status, language, and message
    """
    if not payload.language.strip():
        raise HTTPException(status_code=400, detail="Language cannot be empty")
    
    # Check if preference already exists
    stmt = select(UserPreference).where(
        UserPreference.user_id == current_user.id,
        UserPreference.preference == "language"
    )
    existing_pref = session.exec(stmt).first()
    
    if existing_pref:
        # Update existing preference
        existing_pref.value = payload.language
        existing_pref.updated_at = datetime.utcnow()
        session.add(existing_pref)
    else:
        # Create new preference
        new_pref = UserPreference(
            user_id=current_user.id,
            preference="language",
            value=payload.language
        )
        session.add(new_pref)
    
    session.commit()
    
    logger.info(f"Updated language preference for user {current_user.id} to {payload.language}")
    
    return {
        "success": True,
        "language": payload.language,
        "message": "Language preference updated successfully"
    }