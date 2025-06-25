from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlmodel import Session, select
from datetime import datetime

from models import ClickUpConnection
from db import get_session
from auth import get_current_user

router = APIRouter(prefix="/connections", tags=["connections"])


class ConnectionIn(BaseModel):
    name: str
    api_token: str
    team: str
    list: str

class ConnectionOut(BaseModel):
    id: int
    name: str
    team: str
    list: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


@router.get("/", response_model=List[ConnectionOut])
def list_connections(session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    conns = session.exec(select(ClickUpConnection)).all()
    return conns


@router.post("/", response_model=ConnectionOut)
def create_connection(payload: ConnectionIn, session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    conn = ClickUpConnection(**payload.dict())
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return conn


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