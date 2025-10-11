"""
Feedback router for handling feature requests and bug reports.
"""
from datetime import datetime
from typing import List, Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select, func, or_, and_

from db import get_session
from models import User, Feedback, FeedbackVote, FeedbackComment
from auth import get_current_user, require_admin

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


# Pydantic models for request/response
class AuthorResponse(BaseModel):
    """Author information for feedback items"""
    id: int
    name: str
    avatar: str


class FeedbackResponse(BaseModel):
    """Response model for feedback items"""
    id: int
    type: str
    title: str
    description: str
    category: Optional[str]
    priority: str
    status: str
    votes: int
    hasVoted: bool
    author: AuthorResponse
    createdAt: datetime
    updatedAt: datetime
    comments: int
    tags: List[str] = []


class PaginationResponse(BaseModel):
    """Pagination information"""
    currentPage: int
    totalPages: int
    totalItems: int
    itemsPerPage: int


class FeedbackListResponse(BaseModel):
    """Response for list of feedback items"""
    success: bool = True
    data: List[FeedbackResponse]
    pagination: PaginationResponse


class FeedbackCreateRequest(BaseModel):
    """Request model for creating feedback"""
    type: Literal["feature", "bug"]
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    priority: Literal["low", "medium", "high"] = "medium"
    category: Optional[str] = None


class FeedbackCreateResponse(BaseModel):
    """Response for feedback creation"""
    success: bool = True
    message: str
    data: FeedbackResponse


class VoteResponse(BaseModel):
    """Response for vote operations"""
    votes: int
    hasVoted: bool


class VoteOperationResponse(BaseModel):
    """Response wrapper for vote operations"""
    success: bool = True
    message: str
    data: VoteResponse


class StatusUpdateRequest(BaseModel):
    """Request model for updating feedback status (admin only)"""
    status: Literal["pending", "in-progress", "completed", "rejected"]
    adminNote: Optional[str] = None


class StatusUpdateResponse(BaseModel):
    """Response for status update"""
    success: bool = True
    message: str
    data: dict


def get_author_initials(username: str) -> str:
    """Generate initials from username"""
    parts = username.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[1][0]}".upper()
    return username[:2].upper() if len(username) >= 2 else username.upper()


def build_feedback_response(
    feedback: Feedback,
    author: User,
    has_voted: bool,
    comment_count: int
) -> FeedbackResponse:
    """Build a feedback response object"""
    return FeedbackResponse(
        id=feedback.id,
        type=feedback.type,
        title=feedback.title,
        description=feedback.description,
        category=feedback.category,
        priority=feedback.priority,
        status=feedback.status,
        votes=feedback.votes,
        hasVoted=has_voted,
        author=AuthorResponse(
            id=author.id,
            name=author.username,
            avatar=get_author_initials(author.username)
        ),
        createdAt=feedback.created_at,
        updatedAt=feedback.updated_at,
        comments=comment_count,
        tags=[]  # Can be extended later
    )


@router.get("/features", response_model=FeedbackListResponse)
async def get_features(
    status: Optional[str] = Query(None, description="Filter by status"),
    sort: Optional[str] = Query("newest", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Retrieve all feature requests with optional filtering and pagination.
    """
    # Base query for features
    query = select(Feedback).where(
        and_(
            Feedback.type == "feature",
            Feedback.deleted_at.is_(None)
        )
    )
    
    # Apply status filter
    if status:
        query = query.where(Feedback.status == status)
    
    # Apply sorting
    if sort == "oldest":
        query = query.order_by(Feedback.created_at.asc())
    elif sort == "popular":
        query = query.order_by(Feedback.votes.desc())
    elif sort == "priority":
        # Custom priority sorting: high > medium > low
        priority_order = {"high": 3, "medium": 2, "low": 1}
        query = query.order_by(Feedback.created_at.desc())  # Default for now
    else:  # newest
        query = query.order_by(Feedback.created_at.desc())
    
    # Count total items
    count_query = select(func.count()).select_from(Feedback).where(
        and_(
            Feedback.type == "feature",
            Feedback.deleted_at.is_(None)
        )
    )
    if status:
        count_query = count_query.where(Feedback.status == status)
    
    total_items = session.exec(count_query).one()
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    
    # Execute query
    feedbacks = session.exec(query).all()
    
    # Build response data
    feedback_responses = []
    for feedback in feedbacks:
        # Get author
        author = session.get(User, feedback.author_id)
        if not author:
            continue
        
        # Check if current user has voted
        vote_query = select(FeedbackVote).where(
            and_(
                FeedbackVote.feedback_id == feedback.id,
                FeedbackVote.user_id == current_user.id
            )
        )
        has_voted = session.exec(vote_query).first() is not None
        
        # Count comments
        comment_count_query = select(func.count()).select_from(FeedbackComment).where(
            and_(
                FeedbackComment.feedback_id == feedback.id,
                FeedbackComment.deleted_at.is_(None)
            )
        )
        comment_count = session.exec(comment_count_query).one()
        
        feedback_responses.append(
            build_feedback_response(feedback, author, has_voted, comment_count)
        )
    
    # Calculate pagination
    total_pages = (total_items + limit - 1) // limit
    
    return FeedbackListResponse(
        data=feedback_responses,
        pagination=PaginationResponse(
            currentPage=page,
            totalPages=total_pages,
            totalItems=total_items,
            itemsPerPage=limit
        )
    )


@router.get("/bugs", response_model=FeedbackListResponse)
async def get_bugs(
    status: Optional[str] = Query(None, description="Filter by status"),
    sort: Optional[str] = Query("newest", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Retrieve all bug reports with optional filtering and pagination.
    """
    # Base query for bugs
    query = select(Feedback).where(
        and_(
            Feedback.type == "bug",
            Feedback.deleted_at.is_(None)
        )
    )
    
    # Apply status filter
    if status:
        query = query.where(Feedback.status == status)
    
    # Apply sorting
    if sort == "oldest":
        query = query.order_by(Feedback.created_at.asc())
    elif sort == "popular":
        query = query.order_by(Feedback.votes.desc())
    elif sort == "priority":
        query = query.order_by(Feedback.created_at.desc())  # Default for now
    else:  # newest
        query = query.order_by(Feedback.created_at.desc())
    
    # Count total items
    count_query = select(func.count()).select_from(Feedback).where(
        and_(
            Feedback.type == "bug",
            Feedback.deleted_at.is_(None)
        )
    )
    if status:
        count_query = count_query.where(Feedback.status == status)
    
    total_items = session.exec(count_query).one()
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    
    # Execute query
    feedbacks = session.exec(query).all()
    
    # Build response data
    feedback_responses = []
    for feedback in feedbacks:
        # Get author
        author = session.get(User, feedback.author_id)
        if not author:
            continue
        
        # Check if current user has voted
        vote_query = select(FeedbackVote).where(
            and_(
                FeedbackVote.feedback_id == feedback.id,
                FeedbackVote.user_id == current_user.id
            )
        )
        has_voted = session.exec(vote_query).first() is not None
        
        # Count comments
        comment_count_query = select(func.count()).select_from(FeedbackComment).where(
            and_(
                FeedbackComment.feedback_id == feedback.id,
                FeedbackComment.deleted_at.is_(None)
            )
        )
        comment_count = session.exec(comment_count_query).one()
        
        feedback_responses.append(
            build_feedback_response(feedback, author, has_voted, comment_count)
        )
    
    # Calculate pagination
    total_pages = (total_items + limit - 1) // limit
    
    return FeedbackListResponse(
        data=feedback_responses,
        pagination=PaginationResponse(
            currentPage=page,
            totalPages=total_pages,
            totalItems=total_items,
            itemsPerPage=limit
        )
    )


@router.post("", response_model=FeedbackCreateResponse, status_code=201)
async def create_feedback(
    feedback_data: FeedbackCreateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Create a new feedback item (feature request or bug report).
    """
    # Create feedback item
    new_feedback = Feedback(
        type=feedback_data.type,
        title=feedback_data.title.strip(),
        description=feedback_data.description.strip(),
        category=feedback_data.category,
        priority=feedback_data.priority,
        status="pending",
        votes=0,
        author_id=current_user.id,
        workspace_id=current_user.current_workspace_id
    )
    
    session.add(new_feedback)
    session.commit()
    session.refresh(new_feedback)
    
    # Build response
    feedback_response = build_feedback_response(
        new_feedback,
        current_user,
        has_voted=False,
        comment_count=0
    )
    
    return FeedbackCreateResponse(
        message="Feedback submitted successfully",
        data=feedback_response
    )


@router.post("/{feedback_id}/upvote", response_model=VoteOperationResponse)
async def add_upvote(
    feedback_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Add an upvote to a feedback item.
    """
    # Check if feedback exists
    feedback = session.get(Feedback, feedback_id)
    if not feedback or feedback.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    # Check if user already voted
    existing_vote = session.exec(
        select(FeedbackVote).where(
            and_(
                FeedbackVote.feedback_id == feedback_id,
                FeedbackVote.user_id == current_user.id
            )
        )
    ).first()
    
    if existing_vote:
        raise HTTPException(status_code=400, detail="You have already voted on this item")
    
    # Create vote
    new_vote = FeedbackVote(
        feedback_id=feedback_id,
        user_id=current_user.id
    )
    session.add(new_vote)
    
    # Update vote count
    feedback.votes += 1
    feedback.updated_at = datetime.utcnow()
    
    session.commit()
    session.refresh(feedback)
    
    return VoteOperationResponse(
        message="Upvote added successfully",
        data=VoteResponse(
            votes=feedback.votes,
            hasVoted=True
        )
    )


@router.delete("/{feedback_id}/upvote", response_model=VoteOperationResponse)
async def remove_upvote(
    feedback_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Remove an upvote from a feedback item.
    """
    # Check if feedback exists
    feedback = session.get(Feedback, feedback_id)
    if not feedback or feedback.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    # Check if user has voted
    existing_vote = session.exec(
        select(FeedbackVote).where(
            and_(
                FeedbackVote.feedback_id == feedback_id,
                FeedbackVote.user_id == current_user.id
            )
        )
    ).first()
    
    if not existing_vote:
        raise HTTPException(status_code=400, detail="You have not voted on this item")
    
    # Remove vote
    session.delete(existing_vote)
    
    # Update vote count
    feedback.votes = max(0, feedback.votes - 1)
    feedback.updated_at = datetime.utcnow()
    
    session.commit()
    session.refresh(feedback)
    
    return VoteOperationResponse(
        message="Upvote removed successfully",
        data=VoteResponse(
            votes=feedback.votes,
            hasVoted=False
        )
    )


@router.get("/{feedback_id}", response_model=FeedbackCreateResponse)
async def get_feedback_detail(
    feedback_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get detailed information about a specific feedback item.
    """
    # Get feedback
    feedback = session.get(Feedback, feedback_id)
    if not feedback or feedback.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    # Get author
    author = session.get(User, feedback.author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    
    # Check if current user has voted
    vote_query = select(FeedbackVote).where(
        and_(
            FeedbackVote.feedback_id == feedback_id,
            FeedbackVote.user_id == current_user.id
        )
    )
    has_voted = session.exec(vote_query).first() is not None
    
    # Count comments
    comment_count_query = select(func.count()).select_from(FeedbackComment).where(
        and_(
            FeedbackComment.feedback_id == feedback_id,
            FeedbackComment.deleted_at.is_(None)
        )
    )
    comment_count = session.exec(comment_count_query).one()
    
    feedback_response = build_feedback_response(feedback, author, has_voted, comment_count)
    
    return FeedbackCreateResponse(
        message="Feedback retrieved successfully",
        data=feedback_response
    )


@router.patch("/{feedback_id}/status", response_model=StatusUpdateResponse)
async def update_feedback_status(
    feedback_id: int,
    status_data: StatusUpdateRequest,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """
    Update the status of a feedback item (admin only).
    """
    # Get feedback
    feedback = session.get(Feedback, feedback_id)
    if not feedback or feedback.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    # Update status
    feedback.status = status_data.status
    feedback.updated_at = datetime.utcnow()
    
    session.commit()
    session.refresh(feedback)
    
    return StatusUpdateResponse(
        message="Status updated successfully",
        data={
            "id": feedback.id,
            "status": feedback.status,
            "updatedAt": feedback.updated_at.isoformat()
        }
    )
