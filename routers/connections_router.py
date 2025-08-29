from fastapi import APIRouter, Depends, HTTPException,Request
from pydantic import BaseModel
from typing import List, Optional
from sqlmodel import Session, select
from datetime import datetime
import json
from fastapi.responses import RedirectResponse
import requests
from jose import jwt, JWTError

from models import ClickUpConnection, UserIntegrations, UserIntegrationCredentials
from db import get_session
from auth import get_current_user

router = APIRouter(prefix="/connections", tags=["connections"])


class ConnectionIn(BaseModel):
    name: str
    api_token: Optional[str] = None
    token : Optional[str] = None  # alias for api_token
    team: Optional[str] = None
    list: Optional[str] = None
    integration_id: int  

class ConnectionOut(BaseModel):
    id: int
    name: str
    team: str
    list: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class integrationInfo(BaseModel):
    id: int
    name: str
    description: str
    is_connected: bool
    type: str


@router.get("/", response_model=List[ConnectionOut])
def list_connections(session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    conns = session.exec(select(ClickUpConnection)).all()
    return conns

@router.post("/")
def create_connection(payload: ConnectionIn, session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    # conn = ClickUpConnection(**payload.dict())
    # session.add(conn)
    # session.commit()
    # session.refresh(conn)
    user_integration = UserIntegrations(
        user_id= _.id,
        integration_id=payload.integration_id,
        is_connected=True,
        name=payload.name,
        description=f"Connection to ClickUp list {payload.list}"
    )

    session.add(user_integration)
    session.commit()
    session.refresh(user_integration)


    user_integration_credentials = UserIntegrationCredentials(
        user_integration_id=user_integration.id,
        credentials=json.dumps({
            "api_token": payload.api_token or payload.token,
            "team": payload.team,
            "list": payload.list
        }),
    )

    session.add(user_integration_credentials)
    session.commit()
    session.refresh(user_integration_credentials)

    return user_integration

@router.get("/{conn_id}", response_model=ConnectionOut)
def get_connection(conn_id: int, session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    conn = session.get(ClickUpConnection, conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn

@router.put("/{conn_id}", response_model=ConnectionOut)
def update_connection(conn_id: int, payload: ConnectionIn, session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    conn = session.get(ClickUpConnection, conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    for k, v in payload.dict().items():
        setattr(conn, k, v)
    conn.updated_at = datetime.utcnow()
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return conn


@router.delete("/{conn_id}")
def delete_connection(conn_id: int, session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    conn = session.get(ClickUpConnection, conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    session.delete(conn)
    session.commit()
    return {"status": "deleted"}

@router.post("/{conn_id}/test")
def test_saved_connection(conn_id: int, session: Session = Depends(get_session), _: str = Depends(get_current_user)):

    """Test a stored connection by hitting ClickUp list endpoint."""
    from routers.clickup_router import ClickUpConnection as _ClickUpConn, _fetch_tasks  # reuse helper

    rec = session.get(ClickUpConnection, conn_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Connection not found")

    conn_obj = _ClickUpConn(api_token=rec.api_token, team=rec.team, list=rec.list)
    try:
        _ = _fetch_tasks(conn_obj)
        return {"status": "ok"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 
    
# oauth rooutes
CLIENT_ID = "4a6783825a88ff007feef387a11fdf1d946d52a588470c5669182bb0ed0aaec8"
CLIENT_SECRET = "gloas-75a0afa6777b6dce9de503b96095a2b6024fca735b774e5d93364a2f80c4f63a"
REDIRECT_URI = "http://localhost:8000/connections/gitlab/callback"
AUTHORIZE_URL = "https://gitlab.com/oauth/authorize"
TOKEN_URL = "https://gitlab.com/oauth/token"

@router.get("/gitlab/login")
def gitlab_login(request: Request):
    token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    
    payload = jwt.decode(token, "CHANGE_ME", algorithms=["HS256"])
    user_id = payload.get("sub")
    state = user_id  # Use user ID as state to identify the user in callback
    url = (
        f"{AUTHORIZE_URL}"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=api+write_repository"
        f"&state={state}"
    )
    return RedirectResponse(url)


@router.get("/gitlab/callback")
def gitlab_callback(code: str, state: str, session: Session = Depends(get_session)):
    token_resp = requests.post(TOKEN_URL, data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    })
    token_data = token_resp.json()

    user_integration = UserIntegrations(
        user_id=int(state),   
        integration_id=4,  # TODO: make an enum for this
        is_connected=True,
        name="GitLab OAuth",
        description="OAuth connection to GitLab"
    )

    session.add(user_integration)
    session.commit()
    session.refresh(user_integration)

    user_integration_credentials = UserIntegrationCredentials(
        user_integration_id=user_integration.id,
        credentials=json.dumps(token_data),
    )

    session.add(user_integration_credentials)
    session.commit()
    
    return RedirectResponse("http://localhost:4200/settings?gitlab=connected")
