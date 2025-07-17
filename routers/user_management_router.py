from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session
from models import User, DataSource, UserDataSourceAccess
from auth import hash_password, require_admin, get_current_user

router = APIRouter(prefix="/admin/users", tags=["user-management"])


# Pydantic models for request/response
class UserCreate(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool


class UserWithAccess(BaseModel):
    id: int
    username: str
    is_admin: bool
    datasource_access: List[int]  # List of datasource IDs


class DataSourceAccessRequest(BaseModel):
    user_id: int
    datasource_id: int


class DataSourceAccessResponse(BaseModel):
    id: int
    user_id: int
    datasource_id: int
    granted_at: datetime
    granted_by: int


# User CRUD endpoints
@router.post("/", response_model=UserResponse)
def create_user(
    user_data: UserCreate,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin)
):
    """Create a new user (admin only)"""
    # Check if username already exists
    existing_user = session.exec(
        select(User).where(User.username == user_data.username)
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Create new user
    new_user = User(
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        is_admin=user_data.is_admin
    )
    
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        is_admin=new_user.is_admin
    )


@router.get("/", response_model=List[UserWithAccess])
def get_all_users(
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin)
):
    """Get all users with their datasource access (admin only)"""
    users = session.exec(select(User)).all()
    
    result = []
    for user in users:
        # Get datasource access for this user
        access_records = session.exec(
            select(UserDataSourceAccess).where(UserDataSourceAccess.user_id == user.id)
        ).all()
        
        datasource_ids = [record.datasource_id for record in access_records]
        
        result.append(UserWithAccess(
            id=user.id,
            username=user.username,
            is_admin=user.is_admin,
            datasource_access=datasource_ids
        ))
    
    return result


@router.get("/{user_id}", response_model=UserWithAccess)
def get_user(
    user_id: int,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin)
):
    """Get a specific user with their datasource access (admin only)"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get datasource access for this user
    access_records = session.exec(
        select(UserDataSourceAccess).where(UserDataSourceAccess.user_id == user_id)
    ).all()
    
    datasource_ids = [record.datasource_id for record in access_records]
    
    return UserWithAccess(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        datasource_access=datasource_ids
    )


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin)
):
    """Update a user (admin only)"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if username already exists (if updating username)
    if user_data.username and user_data.username != user.username:
        existing_user = session.exec(
            select(User).where(User.username == user_data.username)
        ).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
    
    # Update user fields
    if user_data.username:
        user.username = user_data.username
    if user_data.password:
        user.hashed_password = hash_password(user_data.password)
    if user_data.is_admin is not None:
        user.is_admin = user_data.is_admin
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin
    )


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin)
):
    """Delete a user (admin only)"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from deleting themselves
    if user_id == admin_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Delete user's datasource access records first
    access_records = session.exec(
        select(UserDataSourceAccess).where(UserDataSourceAccess.user_id == user_id)
    ).all()
    
    for record in access_records:
        session.delete(record)
    
    # Delete the user
    session.delete(user)
    session.commit()
    
    return {"message": "User deleted successfully"}


# Datasource access management endpoints
@router.post("/datasource-access", response_model=DataSourceAccessResponse)
def grant_datasource_access(
    access_data: DataSourceAccessRequest,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin)
):
    """Grant datasource access to a user (admin only)"""
    # Check if user exists
    user = session.get(User, access_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if datasource exists
    datasource = session.get(DataSource, access_data.datasource_id)
    if not datasource:
        raise HTTPException(status_code=404, detail="Datasource not found")
    
    # Check if access already exists
    existing_access = session.exec(
        select(UserDataSourceAccess).where(
            UserDataSourceAccess.user_id == access_data.user_id,
            UserDataSourceAccess.datasource_id == access_data.datasource_id
        )
    ).first()
    
    if existing_access:
        raise HTTPException(status_code=400, detail="User already has access to this datasource")
    
    # Grant access
    new_access = UserDataSourceAccess(
        user_id=access_data.user_id,
        datasource_id=access_data.datasource_id,
        granted_by=admin_user.id
    )
    
    session.add(new_access)
    session.commit()
    session.refresh(new_access)
    
    return DataSourceAccessResponse(
        id=new_access.id,
        user_id=new_access.user_id,
        datasource_id=new_access.datasource_id,
        granted_at=new_access.granted_at,
        granted_by=new_access.granted_by
    )


@router.delete("/revoke/datasource-access")
def revoke_datasource_access(
    access_data: DataSourceAccessRequest,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin)
):
    """Revoke datasource access from a user (admin only)"""
    # Find the access record
    access_record = session.exec(
        select(UserDataSourceAccess).where(
            UserDataSourceAccess.user_id == access_data.user_id,
            UserDataSourceAccess.datasource_id == access_data.datasource_id
        )
    ).first()
    
    if not access_record:
        raise HTTPException(status_code=404, detail="Access record not found")
    
    # Revoke access
    session.delete(access_record)
    session.commit()
    
    return {"message": "Datasource access revoked successfully"}


@router.get("/{user_id}/datasource-access", response_model=List[DataSourceAccessResponse])
def get_user_datasource_access(
    user_id: int,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin)
):
    """Get all datasource access for a specific user (admin only)"""
    # Check if user exists
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get access records
    access_records = session.exec(
        select(UserDataSourceAccess).where(UserDataSourceAccess.user_id == user_id)
    ).all()
    
    return [
        DataSourceAccessResponse(
            id=record.id,
            user_id=record.user_id,
            datasource_id=record.datasource_id,
            granted_at=record.granted_at,
            granted_by=record.granted_by
        )
        for record in access_records
    ]


# Helper endpoint to get available datasources
@router.get("/datasources/available", response_model=List[dict])
def get_available_datasources(
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin)
):
    """Get all available datasources (admin only)"""
    datasources = session.exec(select(DataSource)).all()
    
    return [
        {
            "id": ds.id,
            "source_type": ds.source_type,
            "reference": ds.reference,
            "category": ds.category,
            "added_at": ds.added_at
        }
        for ds in datasources
    ] 