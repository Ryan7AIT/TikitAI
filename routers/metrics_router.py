from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from db import get_session
from models import Message, DataSource
from auth import get_current_user

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/")
def get_metrics(
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    total_msgs = session.exec(select(func.count()).select_from(Message)).one()
    avg_latency = session.exec(select(func.avg(Message.latency_ms))).one()
    data_sources = session.exec(select(func.count()).select_from(DataSource)).one()
    return {
        "messages": total_msgs,
        "average_latency_ms": avg_latency,
        "data_sources": data_sources,
    } 