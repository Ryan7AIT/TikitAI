from fastapi import APIRouter, Depends, HTTPException,Request
from pydantic import BaseModel
from typing import List, Optional
from sqlmodel import Session, select
from datetime import datetime
import json
from fastapi.responses import RedirectResponse
import requests
from jose import jwt, JWTError
from fastapi import Query

from models import ClickUpConnection, ExternalDataSource, UserIntegrations, UserIntegrationCredentials
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


class savedConnection(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    type: Optional[str] = None   

    class Config:
        from_attributes = True


@router.get("/", response_model=List[savedConnection])
def list_connections(type: Optional[str] = Query(None), session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    if type == 'clickup':
        conns = session.exec(select(UserIntegrations).where(UserIntegrations.integration_id == 1).where(UserIntegrations.user_id == _.id)).all()
        # TODO: make the id dynamic (using enums 1== clickup)
    else:
        conns = session.exec(select(UserIntegrations)).all()

    result = []
    for conn in conns:
        data = {
            "id": conn.id,
            "name": conn.name,
            "created_at": conn.created_at,
            "updated_at": conn.updated_at,
        }
        data["type"] = "clickup" if conn.integration_id == 1 else "other"
        result.append(data)
    return result
    

@router.post("/")
def create_connection(payload: ConnectionIn, session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    # conn = ClickUpConnection(**payload.dict())
    # session.add(conn)
    # session.commit()
    # session.refresh(conn)
    user_integration = UserIntegrations(
        user_id= _.id,
        integration_id=payload.integration_id,
        is_connected=False,
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

    # todo. test the connection here
    external_source = session.get(ExternalDataSource, payload.integration_id)
    if not external_source:
        raise HTTPException(status_code=404, detail="External data source not found")
    
    if external_source.source_type == "clickup":
        # Test the ClickUp connection
        from routers.clickup_router import _get_teams, _make_headers
        try:
            teams = _get_teams(payload.api_token or payload.token)
            if not teams:
                raise HTTPException(status_code=400, detail="Unable to fetch teams with provided token")
            user_integration.is_connected = True
            session.add(user_integration)
            session.commit()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to connect to ClickUp: {str(e)}")
        
    return {
        'success': True,
        'message': "Successfully connected",
        'data': user_integration
    }

@router.delete("/{conn_id}")
def delete_connection(conn_id: int, session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    conn = session.get(UserIntegrations, conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    session.delete(conn)
    session.commit()

    credentials = session.exec(
        select(UserIntegrationCredentials).where(
            UserIntegrationCredentials.user_integration_id == conn.id
        )
    ).all()
    for cred in credentials:
        session.delete(cred)
    session.commit()
    return {"status": "deleted"}

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

# TODO: change this to patch request (cors problem)
@router.post("/{conn_id}/last-used")
def update_last_used(conn_id: int, session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    user_integration = session.get(UserIntegrations, conn_id)
    if not user_integration:
        # Create a new user integration if it doesn't exist
        user_integration = UserIntegrations(
            user_id=_.id,
            integration_id=1,  # Default to ClickUp (integration_id=1)
            is_connected=True,
            name=f"Auto-created integration for user {_.username}",
            description="Auto-created user integration"
        )
        session.add(user_integration)
        session.commit()
        session.refresh(user_integration)
        message = 'New user integration created and marked as used'
    else:
        # Update existing user integration
        user_integration.updated_at = datetime.utcnow()
        user_integration.is_connected = True
        session.add(user_integration)
        session.commit()
        message = 'Last used timestamp updated'
    
    return {
        'success': True,
        'message': message,
        'data': user_integration.id
    }
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
    
from config.settings import get_settings

# oauth rooutes
settings = get_settings()
CLIENT_ID = settings.CLIENT_ID
CLIENT_SECRET = settings.CLIENT_SECRET
REDIRECT_URI = settings.REDIRECT_URI
AUTHORIZE_URL = settings.AUTHORIZE_URL
TOKEN_URL = settings.TOKEN_URL

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
