from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, func

from db import get_session
from models import User, Workspace, WorkspaceUser, Role, RoleAssignment
from auth import get_current_user, require_admin

router = APIRouter(prefix="/api", tags=["workspace"])


# Pydantic models for request/response
class WorkspaceResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    user_count: int
    is_active: bool


class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class UserProfileResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: str
    permissions: List[str]
    current_workspace_id: Optional[int]
    current_workspace_name: Optional[str]
    is_super_admin: bool


class AddUserToWorkspaceRequest(BaseModel):
    user_id: int
    role: Optional[str] = "member"


class WorkspaceUserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: str
    joined_at: datetime


# User Profile Endpoints
@router.get("/users/me", response_model=UserProfileResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get current user profile with workspace and role information."""
    
    # Get user's roles and permissions
    role_assignments = session.exec(
        select(RoleAssignment, Role)
        .join(Role, RoleAssignment.role_id == Role.id)
        .where(RoleAssignment.user_id == current_user.id)
    ).all()
    
    roles = [assignment[1].name for assignment in role_assignments]
    permissions = []
    for assignment in role_assignments:
        role = assignment[1]
        if role.permissions:
            permissions.extend(role.permissions.split(','))
    
    # Remove duplicates and strip whitespace
    permissions = list(set([p.strip() for p in permissions if p.strip()]))
    
    # Get current workspace name
    current_workspace_name = None
    if current_user.current_workspace_id:
        workspace = session.get(Workspace, current_user.current_workspace_id)
        if workspace:
            current_workspace_name = workspace.name
    
    # Determine primary role (first role or 'user' if no roles)
    primary_role = roles[0] if roles else "user"
    
    return UserProfileResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=primary_role,
        permissions=permissions,
        current_workspace_id=current_user.current_workspace_id,
        current_workspace_name=current_workspace_name,
        is_super_admin=current_user.is_admin
    )


# User's Workspace Endpoints
@router.get("/workspaces/me", response_model=List[WorkspaceResponse])
def get_user_workspaces(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get workspaces that the current user belongs to."""
    
    # Get workspaces where user is a member
    workspace_users = session.exec(
        select(WorkspaceUser, Workspace)
        .join(Workspace, WorkspaceUser.workspace_id == Workspace.id)
        .where(WorkspaceUser.user_id == current_user.id)
    ).all()
    
    workspaces = []
    for workspace_user, workspace in workspace_users:
        # Get user count for workspace
        user_count = session.exec(
            select(func.count(WorkspaceUser.id))
            .where(WorkspaceUser.workspace_id == workspace.id)
        ).first() or 0
        
        workspaces.append(WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            description=workspace.description,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
            user_count=user_count,
            is_active=workspace.is_active
        ))
    
    return workspaces


@router.get("/workspaces/current", response_model=WorkspaceResponse)
def get_current_workspace(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get current workspace details."""
    
    if not current_user.current_workspace_id:
        raise HTTPException(status_code=404, detail="No current workspace set")
    
    workspace = session.get(Workspace, current_user.current_workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Current workspace not found")
    
    # Get user count for workspace
    user_count = session.exec(
        select(func.count(WorkspaceUser.id))
        .where(WorkspaceUser.workspace_id == workspace.id)
    ).first() or 0
    
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        user_count=user_count,
        is_active=workspace.is_active
    )


@router.post("/workspaces/switch/{workspace_id}")
def switch_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Switch to a workspace."""
    
    # Check if workspace exists
    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Check if user has access to this workspace
    workspace_user = session.exec(
        select(WorkspaceUser)
        .where(WorkspaceUser.workspace_id == workspace_id)
        .where(WorkspaceUser.user_id == current_user.id)
    ).first()
    
    if not workspace_user:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")
    
    # Update user's current workspace
    current_user.current_workspace_id = workspace_id
    session.add(current_user)
    session.commit()
    
    return {"message": "Workspace switched successfully", "workspace_id": workspace_id}


# Admin Workspace Management Endpoints
@router.get("/workspaces", response_model=List[WorkspaceResponse])
def get_all_workspaces(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """Get all workspaces (admin only)."""
    
    workspaces = session.exec(select(Workspace)).all()
    
    result = []
    for workspace in workspaces:
        # Get user count for workspace
        user_count = session.exec(
            select(func.count(WorkspaceUser.id))
            .where(WorkspaceUser.workspace_id == workspace.id)
        ).first() or 0
        
        result.append(WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            description=workspace.description,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
            user_count=user_count,
            is_active=workspace.is_active
        ))
    
    return result


@router.post("/workspaces", response_model=WorkspaceResponse)
def create_workspace(
    workspace_data: WorkspaceCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """Create a new workspace (admin only)."""
    
    
    workspace = Workspace(
        name=workspace_data.name,
        description=workspace_data.description,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        user_count=0,
        is_active=workspace.is_active
    )


@router.put("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(
    workspace_id: str,
    workspace_data: WorkspaceUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """Update a workspace (admin only)."""
    
    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if workspace_data.name is not None:
        workspace.name = workspace_data.name
    if workspace_data.description is not None:
        workspace.description = workspace_data.description
    if workspace_data.is_active is not None:
        workspace.is_active = workspace_data.is_active
    
    workspace.updated_at = datetime.utcnow()
    
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    
    # Get user count
    user_count = session.exec(
        select(func.count(WorkspaceUser.id))
        .where(WorkspaceUser.workspace_id == workspace.id)
    ).first() or 0
    
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        user_count=user_count,
        is_active=workspace.is_active
    )


@router.delete("/workspaces/{workspace_id}")
def delete_workspace(
    workspace_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """Delete a workspace (admin only)."""
    
    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Remove all workspace-user relationships
    workspace_users = session.exec(
        select(WorkspaceUser).where(WorkspaceUser.workspace_id == workspace_id)
    ).all()
    
    for workspace_user in workspace_users:
        session.delete(workspace_user)
    
    # Update users who have this as their current workspace
    users_with_current_workspace = session.exec(
        select(User).where(User.current_workspace_id == workspace_id)
    ).all()
    
    for user in users_with_current_workspace:
        user.current_workspace_id = None
        session.add(user)
    
    # Delete the workspace
    session.delete(workspace)
    session.commit()
    
    return {"message": "Workspace deleted successfully"}


# Workspace User Management Endpoints
@router.get("/workspaces/{workspace_id}/users", response_model=List[WorkspaceUserResponse])
def get_workspace_users(
    workspace_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """Get users in a workspace (admin only)."""
    
    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    workspace_users = session.exec(
        select(WorkspaceUser, User)
        .join(User, WorkspaceUser.user_id == User.id)
        .where(WorkspaceUser.workspace_id == workspace_id)
    ).all()
    
    result = []
    for workspace_user, user in workspace_users:
        result.append(WorkspaceUserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=workspace_user.role or "member",
            joined_at=workspace_user.joined_at
        ))
    
    return result


@router.post("/workspaces/{workspace_id}/users")
def add_user_to_workspace(
    workspace_id: str,
    request: AddUserToWorkspaceRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """Add a user to a workspace (admin only)."""
    
    # Check if workspace exists
    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Check if user exists
    user = session.get(User, request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is already in workspace
    existing_workspace_user = session.exec(
        select(WorkspaceUser)
        .where(WorkspaceUser.workspace_id == workspace_id)
        .where(WorkspaceUser.user_id == request.user_id)
    ).first()
    
    if existing_workspace_user:
        raise HTTPException(status_code=400, detail="User is already in this workspace")
    
    # Add user to workspace
    workspace_user = WorkspaceUser(
        workspace_id=workspace_id,
        user_id=request.user_id,
        role=request.role,
        joined_at=datetime.utcnow()
    )
    
    session.add(workspace_user)
    session.commit()
    
    return {"message": "User added to workspace successfully"}


@router.delete("/workspaces/{workspace_id}/users/{user_id}")
def remove_user_from_workspace(
    workspace_id: str,
    user_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """Remove a user from a workspace (admin only)."""
    
    # Check if workspace exists
    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Find workspace user relationship
    workspace_user = session.exec(
        select(WorkspaceUser)
        .where(WorkspaceUser.workspace_id == workspace_id)
        .where(WorkspaceUser.user_id == user_id)
    ).first()
    
    if not workspace_user:
        raise HTTPException(status_code=404, detail="User not found in this workspace")
    
    # If this is the user's current workspace, clear it
    user = session.get(User, user_id)
    if user and user.current_workspace_id == workspace_id:
        user.current_workspace_id = None
        session.add(user)
    
    # Remove workspace user relationship
    session.delete(workspace_user)
    session.commit()
    
    return {"message": "User removed from workspace successfully"} 