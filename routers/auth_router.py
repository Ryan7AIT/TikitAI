from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session, engine
from models import User
from auth import authenticate_user, create_access_token, hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginPayload, session: Session = Depends(get_session)):
    user = authenticate_user(payload.username, payload.password, session)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


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