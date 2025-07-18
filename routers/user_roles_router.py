from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db import get_session
from models import Role, RoleAssignment, User
from auth import get_current_user, require_admin

router = APIRouter(prefix="/api/roles", tags=["roles"])


# ----------------------------- Pydantic Schemas ----------------------------- #

class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    permissions: List[str]


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class UserRole(BaseModel):
    id: int
    name: str
    description: Optional[str]
    permissions: List[str]
    created_at: datetime
    updated_at: datetime
    user_count: Optional[int] = None

    class Config:
        orm_mode = True


class RoleUser(BaseModel):
    id: int
    username: str
    is_admin: bool
    assigned_at: datetime

    class Config:
        orm_mode = True


# ----------------------------- Helper Functions ----------------------------- #

def _permissions_to_str(perms: List[str]) -> str:
    return ",".join(perms)


def _str_to_permissions(perms_str: Optional[str]) -> List[str]:
    return [p for p in perms_str.split(",") if p] if perms_str else []


def _role_to_schema(session: Session, role: Role) -> UserRole:
    assignments = session.exec(
        select(RoleAssignment).where(RoleAssignment.role_id == role.id)
    ).all()
    return UserRole(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=_str_to_permissions(role.permissions),
        created_at=role.created_at,
        updated_at=role.updated_at,
        user_count=len(assignments),
    )


# ----------------------------- Role CRUD Endpoints ----------------------------- #

@router.get("/", response_model=List[UserRole])
def list_roles(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    roles = session.exec(select(Role)).all()
    return [_role_to_schema(session, r) for r in roles]


@router.get("/{role_id}", response_model=UserRole)
def get_role(
    role_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return _role_to_schema(session, role)


@router.post("/", response_model=UserRole)
def create_role(
    payload: RoleCreate,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    # Ensure unique name
    existing = session.exec(select(Role).where(Role.name == payload.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Role name already exists")

    role = Role(
        name=payload.name,
        description=payload.description,
        permissions=_permissions_to_str(payload.permissions),
    )
    session.add(role)
    session.commit()
    session.refresh(role)
    return _role_to_schema(session, role)


@router.put("/{role_id}", response_model=UserRole)
def update_role(
    role_id: int,
    payload: RoleUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if payload.name and payload.name != role.name:
        # Check unique name
        conflict = session.exec(select(Role).where(Role.name == payload.name)).first()
        if conflict:
            raise HTTPException(status_code=400, detail="Role name already exists")
        role.name = payload.name

    if payload.description is not None:
        role.description = payload.description
    if payload.permissions is not None:
        role.permissions = _permissions_to_str(payload.permissions)

    role.updated_at = datetime.utcnow()
    session.add(role)
    session.commit()
    session.refresh(role)
    return _role_to_schema(session, role)


@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Delete assignments
    assignments = session.exec(
        select(RoleAssignment).where(RoleAssignment.role_id == role_id)
    ).all()
    for a in assignments:
        session.delete(a)
    session.delete(role)
    session.commit()
    return {"detail": "Role deleted"}


# ----------------------------- User Assignment Endpoints ----------------------------- #

class UserAssignment(BaseModel):
    user_id: int


@router.get("/{role_id}/users", response_model=List[RoleUser])
def get_users_in_role(
    role_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    assignments = session.exec(
        select(RoleAssignment).where(RoleAssignment.role_id == role_id)
    ).all()

    user_ids = [a.user_id for a in assignments]
    users = []
    if user_ids:
        users = session.exec(select(User).where(User.id.in_(user_ids))).all()

    user_map = {u.id: u for u in users}
    result: List[RoleUser] = []
    for a in assignments:
        u = user_map.get(a.user_id)
        if u:
            result.append(
                RoleUser(
                    id=u.id,
                    username=u.username,
                    is_admin=u.is_admin,
                    assigned_at=a.assigned_at,
                )
            )
    return result


@router.post("/{role_id}/users")
def add_user_to_role(
    role_id: int,
    payload: UserAssignment,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    user = session.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already assigned
    existing = session.exec(
        select(RoleAssignment).where(
            (RoleAssignment.role_id == role_id) & (RoleAssignment.user_id == payload.user_id)
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already assigned to role")

    assignment = RoleAssignment(role_id=role_id, user_id=payload.user_id)
    session.add(assignment)
    session.commit()
    return {"detail": "User added to role"}


@router.delete("/{role_id}/users/{user_id}")
def remove_user_from_role(
    role_id: int,
    user_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    assignment = session.exec(
        select(RoleAssignment).where(
            (RoleAssignment.role_id == role_id) & (RoleAssignment.user_id == user_id)
        )
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    session.delete(assignment)
    session.commit()
    return {"detail": "User removed from role"} 