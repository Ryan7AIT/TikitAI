from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import List, Optional
import requests, os

from db import get_session
from models import DataSource
from services.vector_service import get_vector_service
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from auth import get_current_user

router = APIRouter(prefix="/clickup", tags=["clickup"])

DATA_DIR = "data"
CLICKUP_FILE_PREFIX = "clickup_"  # filenames will be clickup_<task_id>.txt

# ------------------------------- Pydantic Schemas ------------------------------- #
# The user now supplies readable names (or ids). We lazily resolve ids via ClickUp API.

class ClickUpConnection(BaseModel):
    api_token: str
    team: Optional[str] = None  # name or id – optional when only testing token
    list: Optional[str] = None  # name or id – optional until a list is chosen

    # resolved ids get cached on instance (not part of schema persistence)
    team_id: Optional[str] = None
    list_id: Optional[str] = None

class ClickUpTask(BaseModel):
    id: str
    name: str
    status: str
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    synced: bool = False

class SyncPayload(BaseModel):
    connection: ClickUpConnection
    task_ids: Optional[List[str]] = None  # if None → sync all



# ------------------------------- Helper functions ------------------------------- #

def _make_headers(token: str):
    return {"Authorization": token, "Content-Type": "application/json"}


def _fetch_tasks(conn: ClickUpConnection) -> List[dict]:
    """Return raw task dicts from ClickUp list."""
    _ensure_ids(conn)
    url = f"https://api.clickup.com/api/v2/list/{conn.list_id}/task?include_closed=true"
    resp = requests.get(url, headers=_make_headers(conn.api_token))
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to fetch tasks from ClickUp")
    data = resp.json()
    return data.get("tasks", [])


def _fetch_comments(task_id: str, token: str) -> List[str]:
    url = f"https://api.clickup.com/api/v2/task/{task_id}/comment"
    resp = requests.get(url, headers=_make_headers(token))
    if resp.status_code != 200:
        return []
    data = resp.json()
    comments = []
    for c in data.get("comments", []):
        text = c.get("comment_text") or ""
        comments.append(text)
    return comments


def _task_to_file(task: dict, comments: List[str]) -> str:
    # TODO: add more fields to the file and format it better
    """Serialize task + comments into text and save to data dir. Returns file path."""
    task_id = task.get("id")
    path = os.path.join(DATA_DIR, f"{CLICKUP_FILE_PREFIX}{task_id}.txt")
    lines = [
        f"Task ID: {task_id}",
        f"Issue: {task.get('name')}",
        f"Problem: {task.get('description') or ''}",
        "Solution:",
    ]
    lines.extend(comments)
    content = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path

# ---------- ID resolution helpers ---------- #


def _get_teams(token: str):
    url = "https://api.clickup.com/api/v2/team"
    resp = requests.get(url, headers=_make_headers(token))
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Unable to fetch teams from ClickUp")
    return resp.json().get("teams", [])


def _resolve_team_id(token: str, team_value: str) -> str:
    """Return team_id given a name or id string."""
    if team_value.isdigit():
        return team_value
    teams = _get_teams(token)
    for t in teams:
        if t.get("name", "").lower() == team_value.lower():
            return t.get("id")
    raise HTTPException(status_code=404, detail="Team not found in ClickUp")


def _resolve_list_id(token: str, team_id: str, list_value: str) -> str:
    """Search all spaces & lists under the team by name; if value is digits treat as id."""
    if list_value.isdigit():
        return list_value

    # fetch spaces
    spaces_url = f"https://api.clickup.com/api/v2/team/{team_id}/space"
    spaces_resp = requests.get(spaces_url, headers=_make_headers(token))
    if spaces_resp.status_code != 200:
        raise HTTPException(status_code=spaces_resp.status_code, detail="Unable to fetch spaces from ClickUp")
    spaces = spaces_resp.json().get("spaces", [])

    # iterate spaces to find lists
    for sp in spaces:
        space_id = sp.get("id")
        # folderless lists
        lists_resp = requests.get(f"https://api.clickup.com/api/v2/space/{space_id}/list", headers=_make_headers(token))
        if lists_resp.status_code == 200:
            for l in lists_resp.json().get("lists", []):
                if l.get("name", "").lower() == list_value.lower():
                    return l.get("id")
        # folders in space
        folders_resp = requests.get(f"https://api.clickup.com/api/v2/space/{space_id}/folder", headers=_make_headers(token))
        if folders_resp.status_code == 200:
            for folder in folders_resp.json().get("folders", []):
                folder_id = folder.get("id")
                lists_in_folder = folder.get("lists", [])  # sometimes included
                if not lists_in_folder:
                    li_resp = requests.get(f"https://api.clickup.com/api/v2/folder/{folder_id}/list", headers=_make_headers(token))
                    if li_resp.status_code == 200:
                        lists_in_folder = li_resp.json().get("lists", [])
                for l in lists_in_folder:
                    if l.get("name", "").lower() == list_value.lower():
                        return l.get("id")
    raise HTTPException(status_code=404, detail="List not found in ClickUp")


def _get_spaces(token: str, team_id: str):
    """Return all spaces for a given team id."""
    url = f"https://api.clickup.com/api/v2/team/{team_id}/space"
    resp = requests.get(url, headers=_make_headers(token))
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Unable to fetch spaces from ClickUp")
    return resp.json().get("spaces", [])


def _get_lists(token: str, space_id: str):
    """Return all lists (folderless + inside folders) for a given space."""
    # folderless lists
    lists_url = f"https://api.clickup.com/api/v2/space/{space_id}/list"
    resp = requests.get(lists_url, headers=_make_headers(token))
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Unable to fetch lists from ClickUp space")
    lists_out = resp.json().get("lists", [])

    # folders + their lists
    folders_url = f"https://api.clickup.com/api/v2/space/{space_id}/folder"
    f_resp = requests.get(folders_url, headers=_make_headers(token))
    if f_resp.status_code == 200:
        for folder in f_resp.json().get("folders", []):
            folder_lists = folder.get("lists", [])
            if not folder_lists:
                # fallback – sometimes lists omitted, fetch directly
                fid = folder.get("id")
                li_resp = requests.get(f"https://api.clickup.com/api/v2/folder/{fid}/list", headers=_make_headers(token))
                if li_resp.status_code == 200:
                    folder_lists = li_resp.json().get("lists", [])
            lists_out.extend(folder_lists)
    return lists_out


def _ensure_ids(conn: ClickUpConnection):
    """Populate conn.team_id and conn.list_id if missing. Raises if needed infos are absent."""
    if not conn.team and not conn.team_id:
        raise HTTPException(status_code=400, detail="team is required for this operation")
    if not conn.list and not conn.list_id:
        raise HTTPException(status_code=400, detail="list is required for this operation")
    if not conn.team_id:
        conn.team_id = _resolve_team_id(conn.api_token, conn.team)
    if not conn.list_id:
        conn.list_id = _resolve_list_id(conn.api_token, conn.team_id, conn.list)

# ------------------------------- API Endpoints ------------------------------- #

@router.post("/test")
def test_connection(conn: ClickUpConnection, _: str = Depends(get_current_user)):
    """Verify that the provided token (and optionally team/list) can reach ClickUp."""
    try:
        if conn.team and conn.list:
            _ = _fetch_tasks(conn)
        else:
            # token-only: just fetch teams as validation
            _ = _get_teams(conn.api_token)
        return {"status": "ok"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks", response_model=List[ClickUpTask])
def list_tasks(conn: ClickUpConnection, session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    """Return tasks with sync status information."""
    raw_tasks = _fetch_tasks(conn)
    tasks_out = []
    for t in raw_tasks:
        task_id = t.get("id")
        file_path = os.path.join(DATA_DIR, f"{CLICKUP_FILE_PREFIX}{task_id}.txt")
        ds = session.exec(select(DataSource).where(DataSource.reference == file_path)).first()
        synced = bool(ds and ds.last_synced_at)
        tasks_out.append(
            ClickUpTask(
                id=task_id,
                name=t.get("name"),
                status=t.get("status", {}).get("status") if t.get("status") else None,
                assignee= t.get("assignees", [{}])[0].get("username") if t.get("assignees") else None,
                due_date=t.get("due_date"),
                synced=synced,
            )
        )
    return tasks_out


@router.post("/sync")
def sync_tasks(payload: SyncPayload, session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    conn = payload.connection
    raw_tasks = _fetch_tasks(conn)
    # tasks to sync
    ids_to_sync = set(payload.task_ids or [t.get("id") for t in raw_tasks])

    added_docs = 0
    for t in raw_tasks:
        if t.get("id") not in ids_to_sync:
            continue
        comments = _fetch_comments(t.get("id"), conn.api_token)
        file_path = _task_to_file(t, comments)

        # Update / insert datasource
        ds = session.exec(select(DataSource).where(DataSource.reference == file_path)).first()
        from datetime import datetime as _dt
        if not ds:
            ds = DataSource(source_type="file", reference=file_path, last_synced_at=_dt.utcnow())
            session.add(ds)
        else:
            ds.last_synced_at = _dt.utcnow()
        session.commit()

        # Load and embed using standardized logic
        content = open(file_path, "r", encoding="utf-8").read()
        docs_added = get_vector_service().embed_content_string(content, os.path.basename(file_path))
        added_docs += docs_added

    return {"status": "synced", "tasks_synced": len(ids_to_sync), "added_docs": added_docs}


@router.post("/unsync")
def unsync_tasks(payload: SyncPayload, session: Session = Depends(get_session), _: str = Depends(get_current_user)):
    """Remove tasks from vector store and delete datasource files."""
    conn = payload.connection
    _ensure_ids(conn)
    ids_to_unsync = set(payload.task_ids or [])
    if not ids_to_unsync:
        raise HTTPException(status_code=400, detail="No task_ids provided for unsync")

    removed = 0
    for task_id in ids_to_unsync:
        file_path = os.path.join(DATA_DIR, f"{CLICKUP_FILE_PREFIX}{task_id}.txt")
        ds = session.exec(select(DataSource).where(DataSource.reference == file_path)).first()
        if ds:
            session.delete(ds)
            session.commit()
            removed += 1
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
    # Rebuild vector store to remove deleted docs
    from routers.data_router import rebuild_vector_store
    rebuild_vector_store(session)

    return {"status": "unsynced", "tasks_removed": removed}


class CommentPayload(BaseModel):
    connection: ClickUpConnection
    task_id: str


@router.post("/comments")
def get_task_comments(payload: CommentPayload, _: str = Depends(get_current_user)):
    _ensure_ids(payload.connection)
    comments = _fetch_comments(payload.task_id, payload.connection.api_token)
    return {"comments": comments}

# -------------------- New hierarchy helper endpoints -------------------- #

class TokenOnly(BaseModel):
    api_token: str

class TeamPayload(BaseModel):
    api_token: str
    team_id: str

class SpacePayload(BaseModel):
    api_token: str
    space_id: str

@router.post("/teams")
def list_teams(payload: TokenOnly, _: str = Depends(get_current_user)):
    teams = _get_teams(payload.api_token)
    return [{"id": t.get("id"), "name": t.get("name")} for t in teams]

@router.post("/spaces")
def list_spaces(payload: TeamPayload, _: str = Depends(get_current_user)):
    spaces = _get_spaces(payload.api_token, payload.team_id)
    return [{"id": s.get("id"), "name": s.get("name")} for s in spaces]

@router.post("/lists")
def list_lists(payload: SpacePayload, _: str = Depends(get_current_user)):
    lists_ = _get_lists(payload.api_token, payload.space_id)
    return [{"id": l.get("id"), "name": l.get("name")} for l in lists_] 




