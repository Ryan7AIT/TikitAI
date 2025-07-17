import os
import glob
from datetime import datetime
from typing import List
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session
from models import DataSource, ExternalDataSource, ClickUpConnection
from auth import get_current_user

# Reuse vector store and helper from app
from services.vector_service import get_vector_service
from langchain_community.document_loaders import TextLoader, PyPDFLoader, WebBaseLoader
from langchain_core.documents import Document
from routers.clickup_router import _fetch_comments, _make_headers
import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter
import logging

CLICKUP_FILE_PREFIX = "clickup_"

router = APIRouter(prefix="/datasources", tags=["data"])

DATA_DIR = "data"  # ensure exists
os.makedirs(DATA_DIR, exist_ok=True)


class DataSourceOut(BaseModel):
    id: int
    source_type: str
    reference: str
    added_at: datetime
    last_synced_at: datetime | None = None
    size_mb: float | None = None
    category: str | None = None
    tags: str | None = None
    is_synced: int | None = None
    path: str | None = None

    class Config:
        orm_mode = True

class ExternalDataSourceOut(BaseModel):
    id: int
    name: str
    description: str
    is_connected: bool
    type: str

    class Config:
        orm_mode = True

class ExternalDataSourceDetailsOut(BaseModel):
    id: int
    name: str
    description: str
    is_connected: bool
    type: str

    class Config:
        orm_mode = True

class ClickUpTeamOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

class ClickUpSpaceOut(BaseModel):
    id: int
    name: str
    team_id: int

    class Config:
        orm_mode = True

class ClickUpListOut(BaseModel):
    id: int
    name: str
    space_id: int

    class Config:
        orm_mode = True

class ClickUpTaskOut(BaseModel):
    id: int
    name: str
    status: str
    priority: str | None
    assignees: List[str]
    dueDate: datetime | None
    description: str | None
    listId: int
    isSelected: bool | None
    isSynced: bool | None

    class Config:
        orm_mode = True

class ClickUpTicket(BaseModel):
    id: str
    name: str
    status: str
    priority: str | None
    assignees: List[str]
    dueDate: str | None
    description: str | None
    listId: str
    isSynced: bool | None
    isSelected: bool | None

    class Config:
        orm_mode = True

@router.get("/external", response_model=List[ExternalDataSourceOut])
def get_external_data(
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    external_sources = session.exec(select(ExternalDataSource)).all()
    
    result = []
    for source in external_sources:
        result.append(ExternalDataSourceOut(
            id=source.id,
            name=source.name,
            description=source.description,
            is_connected=source.is_connected,
            type=source.source_type
        ))
    
    return result

class ConnectExternalPayload(BaseModel):
    api_token: str
    team: Optional[str] = None
    list: Optional[str] = None

@router.post("/external/{source_id}/connect")
def connect_external_data(
    source_id: int,
    payload: ConnectExternalPayload,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    external_source = session.get(ExternalDataSource, source_id)
    if not external_source:
        raise HTTPException(status_code=404, detail="External data source not found")

    if external_source.source_type == "clickup":
        # Test the ClickUp connection
        from routers.clickup_router import _get_teams, _make_headers
        try:
            teams = _get_teams(payload.api_token)
            if not teams:
                raise HTTPException(status_code=400, detail="Unable to fetch teams with provided token")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to connect to ClickUp: {str(e)}")
        
        # Create or update ClickUp connection
        connection = ClickUpConnection(
            name=f"ClickUp Connection {external_source.id}",
            api_token=payload.api_token,
            team=payload.team or "",
            list=payload.list or ""
        )
        session.add(connection)
        session.commit()
        session.refresh(connection)
        
        # Update external source
        external_source.is_connected = True
        external_source.connection_id = connection.id
        from datetime import datetime
        external_source.updated_at = datetime.utcnow()
        session.add(external_source)
        session.commit()
        
        return ExternalDataSourceOut(
            id=external_source.id,
            name=external_source.name,
            description=external_source.description,
            is_connected=True,
            type=external_source.source_type
        )
    else:
        raise HTTPException(status_code=400, detail=f"Connection not implemented for {external_source.source_type}")

# get external data details
@router.get("/external/{source_id}", response_model=ExternalDataSourceDetailsOut)
def get_external_data_details(
    source_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    external_source = session.get(ExternalDataSource, source_id)
    if not external_source:
        raise HTTPException(status_code=404, detail="External data source not found")
    
    return ExternalDataSourceDetailsOut(
        id=external_source.id,
        name=external_source.name,
        description=external_source.description,
        is_connected=external_source.is_connected,
        type=external_source.source_type
    )

# get external/${dataSourceId}/clickup/teams
@router.get("/external/{source_id}/clickup/teams", response_model=List[ClickUpTeamOut])
def get_external_data_teams(
    source_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    external_source = session.get(ExternalDataSource, source_id)
    if not external_source:
        raise HTTPException(status_code=404, detail="External data source not found")
    
    if external_source.source_type != "clickup" or not external_source.is_connected:
        raise HTTPException(status_code=400, detail="ClickUp not connected for this data source")
    
    # Get the ClickUp connection
    connection = session.get(ClickUpConnection, external_source.connection_id)
    if not connection:
        raise HTTPException(status_code=400, detail="ClickUp connection not found")
    
    # Fetch teams from ClickUp API
    from routers.clickup_router import _get_teams
    try:
        teams = _get_teams(connection.api_token)
        result = []
        for team in teams:
            result.append(ClickUpTeamOut(
                id=int(team.get("id")),
                name=team.get("name", "")
            ))
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch teams: {str(e)}")

# get external/${dataSourceId}/clickup/teams/${teamId}/spaces
@router.get("/external/{source_id}/clickup/teams/{team_id}/spaces", response_model=List[ClickUpSpaceOut])
def get_external_data_spaces(
    source_id: int,
    team_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    external_source = session.get(ExternalDataSource, source_id)
    if not external_source:
        raise HTTPException(status_code=404, detail="External data source not found")
    
    if external_source.source_type != "clickup" or not external_source.is_connected:
        raise HTTPException(status_code=400, detail="ClickUp not connected for this data source")
    
    # Get the ClickUp connection
    connection = session.get(ClickUpConnection, external_source.connection_id)
    if not connection:
        raise HTTPException(status_code=400, detail="ClickUp connection not found")
    
    # Fetch spaces from ClickUp API
    from routers.clickup_router import _get_spaces
    try:
        spaces = _get_spaces(connection.api_token, str(team_id))
        result = []
        for space in spaces:
            result.append(ClickUpSpaceOut(
                id=int(space.get("id")),
                name=space.get("name", ""),
                team_id=team_id
            ))
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch spaces: {str(e)}")

@router.get("/external/{source_id}/clickup/spaces/{space_id}/lists", response_model=List[ClickUpListOut])
def get_external_data_lists(
    source_id: int,
    space_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    external_source = session.get(ExternalDataSource, source_id)
    if not external_source:
        raise HTTPException(status_code=404, detail="External data source not found")
    
    if external_source.source_type != "clickup" or not external_source.is_connected:
        raise HTTPException(status_code=400, detail="ClickUp not connected for this data source")
    
    # Get the ClickUp connection
    connection = session.get(ClickUpConnection, external_source.connection_id)
    if not connection:
        raise HTTPException(status_code=400, detail="ClickUp connection not found")
    
    # Fetch lists from ClickUp API
    from routers.clickup_router import _get_lists
    try:
        lists = _get_lists(connection.api_token, str(space_id))
        result = []
        for list_item in lists:
            result.append(ClickUpListOut(
                id=int(list_item.get("id")),
                name=list_item.get("name", ""),
                space_id=space_id
            ))
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch lists: {str(e)}")

@router.get("/external/{source_id}/clickup/teams/{team_id}/spaces/{space_id}/lists/{list_id}/tasks", response_model=List[ClickUpTaskOut])
def get_external_data_tasks(
    source_id: int,
    team_id: int,
    space_id: int,
    list_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    external_source = session.get(ExternalDataSource, source_id)
    if not external_source:
        raise HTTPException(status_code=404, detail="External data source not found")
    
    if external_source.source_type != "clickup" or not external_source.is_connected:
        raise HTTPException(status_code=400, detail="ClickUp not connected for this data source")
    
    # Get the ClickUp connection
    connection = session.get(ClickUpConnection, external_source.connection_id)
    if not connection:
        raise HTTPException(status_code=400, detail="ClickUp connection not found")
    
    # Create a temporary ClickUpConnection object for _fetch_tasks
    from routers.clickup_router import ClickUpConnection as ClickUpConnModel, _fetch_tasks
    temp_conn = ClickUpConnModel(
        api_token=connection.api_token,
        team="",  # we'll set the resolved IDs directly
        list="",
        team_id=str(team_id),
        list_id=str(list_id)
    )
    
    try:
        # Fetch tasks from ClickUp API
        tasks = _fetch_tasks(temp_conn)
        result = []
        
        # Check sync status for each task
        import os
        DATA_DIR = "data"
        CLICKUP_FILE_PREFIX = "clickup_"
        
        for task in tasks:
            task_id = task.get("id")
            file_path = os.path.join(DATA_DIR, f"{CLICKUP_FILE_PREFIX}{task_id}.txt")
            
            # Check if task is synced
            ds = session.exec(select(DataSource).where(DataSource.reference == file_path)).first()
            is_synced = bool(ds and ds.last_synced_at)
            
            # Parse due date
            due_date = None
            if task.get("due_date"):
                from datetime import datetime
                try:
                    due_date = datetime.fromtimestamp(int(task.get("due_date")) / 1000)
                except:
                    pass
            
            # Get assignees
            assignees = []
            if task.get("assignees"):
                assignees = [assignee.get("username", "") for assignee in task.get("assignees", [])]
            
            result.append(ClickUpTaskOut(
                id=int(task_id),
                name=task.get("name", ""),
                status=task.get("status", {}).get("status", "") if task.get("status") else "",
                priority=task.get("priority", {}).get("priority", "") if task.get("priority") else None,
                assignees=assignees,
                dueDate=due_date,
                description=task.get("description", ""),
                listId=list_id,
                isSelected=False,  # Default to not selected
                isSynced=is_synced
            ))
        
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch tasks: {str(e)}")


@router.get("/external/{source_id}/clickup/tickets", response_model=List[ClickUpTicket])
def get_clickup_tickets(
    source_id: int,
    team_id: Optional[str] = Query(None, alias="teamId"),
    space_id: Optional[str] = Query(None, alias="spaceId"),
    list_id: Optional[str] = Query(None, alias="listId"),
    search: Optional[str] = Query(None),
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Fetch ClickUp tickets/tasks with optional filtering by team, space, list, and search query."""
    external_source = session.get(ExternalDataSource, source_id)
    if not external_source:
        raise HTTPException(status_code=404, detail="External data source not found")
    
    if external_source.source_type != "clickup" or not external_source.is_connected:
        raise HTTPException(status_code=400, detail="ClickUp not connected for this data source")
    
    # Get the ClickUp connection
    connection = session.get(ClickUpConnection, external_source.connection_id)
    if not connection:
        raise HTTPException(status_code=400, detail="ClickUp connection not found")
    
    try:
        from routers.clickup_router import _get_teams, _get_spaces, _get_lists, _make_headers
        import requests
        
        tickets = []
        
        # Determine what to fetch based on provided filters
        if list_id:
            # Fetch tasks from specific list
            tickets.extend(_fetch_tasks_from_list(connection.api_token, list_id,session))
        elif space_id:
            # Fetch all lists in space, then all tasks
            lists = _get_lists(connection.api_token, space_id)
            for list_item in lists:
                tickets.extend(_fetch_tasks_from_list(connection.api_token, list_item.get("id"),session))
        elif team_id:
            # Fetch all spaces in team, then all lists, then all tasks
            spaces = _get_spaces(connection.api_token, team_id)
            for space in spaces:
                space_lists = _get_lists(connection.api_token, space.get("id"))
                for list_item in space_lists:
                    tickets.extend(_fetch_tasks_from_list(connection.api_token, list_item.get("id"),session))
        else:
            # No specific filter - fetch from all teams accessible with this token
            teams = _get_teams(connection.api_token)
            for team in teams[:1]:  # Limit to first team to avoid timeout
                spaces = _get_spaces(connection.api_token, team.get("id"))
                for space in spaces:
                    space_lists = _get_lists(connection.api_token, space.get("id"))
                    for list_item in space_lists:
                        tickets.extend(_fetch_tasks_from_list(connection.api_token, list_item.get("id"),session))
        
        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            tickets = [t for t in tickets if search_lower in t.name.lower() or 
                      (t.description and search_lower in t.description.lower())]
        
        
        return tickets
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch tickets: {str(e)}")


def _fetch_tasks_from_list(api_token: str, list_id: str,session: Session) -> List[ClickUpTicket]:
    """Helper function to fetch tasks from a specific ClickUp list."""
    from routers.clickup_router import _make_headers
    import requests
    
    url = f"https://api.clickup.com/api/v2/list/{list_id}/task?include_closed=true"
    resp = requests.get(url, headers=_make_headers(api_token))
    
    if resp.status_code != 200:
        return []  # Skip lists that can't be accessed
    
    data = resp.json()
    tasks = data.get("tasks", [])
    
    tickets = []
    # Open a single DB session to check sync status for all tasks
    with session:
        for task in tasks:
            # Determine sync status from DataSource table
            ds_reference = f"clickup_{task.get('id')}.txt"
            ds = session.exec(select(DataSource).where(DataSource.reference == ds_reference)).first()
            is_synced = bool(ds and ds.is_synced == 1)

            # Parse due date
            due_date = None
            if task.get("due_date"):
                try:
                    # ClickUp returns timestamps in milliseconds
                    timestamp = int(task.get("due_date")) / 1000
                    from datetime import datetime
                    due_date = datetime.fromtimestamp(timestamp).isoformat()
                except:
                    pass
            
            # Get assignees
            assignees = []
            if task.get("assignees"):
                assignees = [assignee.get("username", "") for assignee in task.get("assignees", [])]
            
            ticket = ClickUpTicket(
                id=str(task.get("id")),
                name=task.get("name", ""),
                status=task.get("status", {}).get("status", "") if task.get("status") else "",
                priority=task.get("priority", {}).get("priority", "") if task.get("priority") else None,
                assignees=assignees,
                dueDate=due_date,
                description=task.get("description", ""),
                listId=str(list_id),
                isSynced=is_synced,
                isSelected=False
            )
            tickets.append(ticket)

    return tickets


# end of external data


# start of local data
@router.get("/", response_model=List[DataSourceOut])
def list_sources(
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    sources = session.exec(select(DataSource)).all()
    return sources


@router.post("/upload", response_model=List[DataSourceOut])
async def upload_file(
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    tags: str = Form(...),
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    saved_sources = []
    # Save file
    for file in files:
        dest_path = os.path.join(DATA_DIR, file.filename)
        with open(dest_path, "wb") as f:
            f.write(await file.read())

        ds = DataSource(source_type="file", reference=file.filename, size_mb=os.path.getsize(dest_path) / (1024 * 1024), category=category, tags=tags, path=dest_path)
        session.add(ds)
        session.commit()
        session.refresh(ds)
        saved_sources.append(ds)

    # Create record
    return saved_sources


class UrlPayload(BaseModel):
    url: str


@router.post("/add-url", response_model=DataSourceOut)
def add_url(
    payload: UrlPayload,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    ds = DataSource(source_type="url", reference=payload.url)
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds


@router.delete("/{source_id}")
def delete_source(
    source_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    ds = session.get(DataSource, source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")

    # Remove file if exists
    if ds.source_type == "file" and os.path.exists(ds.reference):
        try:
            os.remove(ds.reference)
        except Exception:
            pass

    session.delete(ds)
    session.commit()

    # Rebuild vector store to ensure removed docs are gone
    rebuild_vector_store(session)

    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Helper functions for ClickUp task synchronization
# ---------------------------------------------------------------------------

def _get_clickup_connection(session: Session) -> ClickUpConnection:
    """Fetch the first available ClickUp connection or raise an HTTP error."""
    connection = session.exec(select(ClickUpConnection)).first()
    if not connection:
        raise HTTPException(
            status_code=400,
            detail="No ClickUp connection available. Please configure ClickUp connection first.",
        )
    return connection


def _fetch_clickup_task(api_token: str, task_id: str) -> dict:
    """Retrieve task details from ClickUp API."""
    headers = _make_headers(api_token)
    task_url = f"https://api.clickup.com/api/v2/task/{task_id}"
    response = requests.get(task_url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch task from ClickUp")
    return response.json()


def _extract_solution(task_data: dict) -> str:
    """Extract the value from the custom field named 'Solution'."""
    for field in task_data.get("custom_fields", []):
        if field.get("name") == "Solution":
            return field.get("value") or "No solution provided."
    return "No solution provided."


def _build_file_content(ticket_id: str, task_data: dict) -> str:
    """Compose the textual representation to store in the local file."""
    lines = [
        f"Task ID: {ticket_id}",
        f"Issue: {task_data.get('name', '')}",
        f"Problem: {task_data.get('description', '')}",
        "Solution:",
        _extract_solution(task_data),
    ]
    return "\n".join(lines)


def _write_to_file(content: str, filename: str) -> str:
    """Persist the given content inside DATA_DIR and return the file path."""
    file_path = os.path.join(DATA_DIR, filename)
    with open(file_path, "w", encoding="utf-8") as fp:
        fp.write(content)
    return file_path


def _get_or_create_datasource(session: Session, filename: str, file_path: str) -> DataSource:
    """Retrieve an existing DataSource or create a new one for the given file."""
    ds = session.exec(select(DataSource).where(DataSource.reference == filename)).first()
    if ds is None:
        ds = DataSource(source_type="file", reference=filename, path=file_path)
    return ds


def _update_datasource_metadata(ds: DataSource, file_path: str, task_data: dict) -> None:
    """Populate DataSource fields such as size, category, and tags."""
    ds.size_mb = os.path.getsize(file_path) / (1024 * 1024)  # MB
    ds.category = (
        task_data.get("status", {}).get("status", "Unknown") if task_data.get("status") else "Unknown"
    )
    if task_data.get("assignees"):
        assignees = [assignee.get("username", "") for assignee in task_data.get("assignees", [])]
        ds.tags = ", ".join(assignees) if assignees else None


def _embed_content(content: str, is_clickup: bool = False) -> int:
    """Split the content and add each chunk to the vector store. Returns number of chunks added."""
    doc = Document(page_content=content)
    if is_clickup:
                    get_vector_service().add_documents([doc])
    else:
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
        splits = splitter.split_documents([doc])
        get_vector_service().add_documents(splits)
    return 1


def _mark_as_synced(ds: DataSource) -> None:
    """Update DataSource flags to indicate successful sync."""
    from datetime import datetime as _dt

    ds.last_synced_at = _dt.utcnow()
    ds.is_synced = 1


def _sync_clickup_task(ticket_id: str, session: Session) -> dict:
    """Orchestrate ClickUp task synchronization and return a response payload."""
    connection = _get_clickup_connection(session)

    # Retrieve task & comments (comments currently unused but fetched for completeness)
    task_data = _fetch_clickup_task(connection.api_token, ticket_id)
    _fetch_comments(ticket_id, connection.api_token)

    # Build local file
    filename = f"{CLICKUP_FILE_PREFIX}{ticket_id}.txt"
    content = _build_file_content(ticket_id, task_data)
    file_path = _write_to_file(content, filename)

    # Upsert datasource record
    ds = _get_or_create_datasource(session, filename, file_path)
    _update_datasource_metadata(ds, file_path, task_data)

    # Embed content and mark datasource as synced
    added_docs = _embed_content(content, is_clickup=True)
    _mark_as_synced(ds)

    session.add(ds)
    session.commit()

    return {
        "status": "synced",
        "added_docs": added_docs,
        "last_synced_at": ds.last_synced_at,
    }

# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@router.post("/external/{source_id}/clickup/tickets/{ticket_id}/sync")
def sync_clickup_task(
    ticket_id: str,
    source_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Sync a ClickUp task by its task ID. Creates datasource record if it doesn't exist."""

    try:
        return _sync_clickup_task(ticket_id, session)
    except HTTPException:
        # Propagate fastapi HTTP errors as-is
        raise
    except Exception as exc:
        logging.exception("Unexpected error while syncing ClickUp task")
        raise HTTPException(status_code=400, detail=f"Failed to sync ClickUp task: {exc}") from exc


@router.post("/regular/{source_id}/sync")
def sync_regular_source(
    source_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Sync regular datasources (files/URLs) by datasource ID."""
    ds = session.get(DataSource, source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")

    # Handle regular files and URLs
    documents: List[Document] = []
    dir = 'data'
    try:
        if ds.source_type == "file":
            if ds.reference.lower().endswith(".txt"):
                loader = TextLoader(os.path.join(dir, ds.reference), encoding="utf-8")
                documents.extend(loader.load())
            elif ds.reference.lower().endswith(".pdf"):
                loader = PyPDFLoader(os.path.join(dir, ds.reference))
                documents.extend(loader.load())
            else:
                raise ValueError("Unsupported file type")
        elif ds.source_type == "url":
            loader = WebBaseLoader(ds.reference)
            documents.extend(loader.load())
        else:
            raise ValueError("Unsupported source type")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Add to vector store
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    if documents:
        if ds.reference.lower().endswith(".txt"):
            # simple char split as earlier
            splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
            splits = splitter.split_documents(documents)
        else:
            splits = documents
        get_vector_service().add_documents(splits)

    # Mark as synced
    from datetime import datetime as _dt
    ds.last_synced_at = _dt.utcnow()
    ds.is_synced = 1
    session.add(ds)
    session.commit()

    return {"status": "synced", "added_docs": len(documents), "last_synced_at": ds.last_synced_at}


@router.post("/regular/{source_id}/unsync")
def unsync_regular_source(
    source_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Unsync a regular datasource by datasource ID."""
    ds = session.get(DataSource, source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")

    # Remove file if it's a regular file
    if ds.source_type == "file" and ds.reference:
        file_path = os.path.join(DATA_DIR, ds.reference) if not os.path.isabs(ds.reference) else ds.reference
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    # Remove from database
    session.delete(ds)
    session.commit()

    # Rebuild vector store to ensure removed docs are gone
    rebuild_vector_store(session)

    return {"status": "unsynced"}


@router.post("/external/{source_id}/clickup/tickets/{task_id}/unsync")
def unsync_clickup_task(
    task_id: str,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Unsync a ClickUp task by its task ID."""
    
    # Find datasource by filename pattern
    filename = f"clickup_{task_id}.txt"
    ds = session.exec(select(DataSource).where(DataSource.reference == filename)).first()
    
    if not ds:
        raise HTTPException(status_code=404, detail="ClickUp task not found in datasources")

    # Remove file
    file_path = os.path.join(DATA_DIR, filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    # Remove from database
    session.delete(ds)
    session.commit()

    # Rebuild vector store to ensure removed docs are gone
    rebuild_vector_store(session)

    return {"status": "unsynced"}


@router.post("/sync")
def sync_all_sources(
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Sync all datasources that are not currently synced (excluding ClickUp tasks which are synced individually)."""
    sources = session.exec(select(DataSource).where(DataSource.is_synced != 1)).all()
    
    synced_count = 0
    total_docs = 0
    errors = []

    for ds in sources:
        try:
            # Handle regular files and URLs (ClickUp tasks are handled via separate endpoints)
            documents: List[Document] = []
            dir = 'data'
            try:
                if ds.source_type == "file":
                    if ds.reference.lower().endswith(".txt"):
                        loader = TextLoader(os.path.join(dir, ds.reference), encoding="utf-8")
                        documents.extend(loader.load())
                    elif ds.reference.lower().endswith(".pdf"):
                        loader = PyPDFLoader(os.path.join(dir, ds.reference))
                        documents.extend(loader.load())
                elif ds.source_type == "url":
                    loader = WebBaseLoader(ds.reference)
                    documents.extend(loader.load())

                if documents:
                    from langchain_text_splitters import RecursiveCharacterTextSplitter
                    if ds.reference.lower().endswith(".txt"):
                        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
                        splits = splitter.split_documents(documents)
                    else:
                        splits = documents
                    get_vector_service().add_documents(splits)
                    total_docs += len(splits)

                # Mark as synced
                from datetime import datetime as _dt
                ds.last_synced_at = _dt.utcnow()
                ds.is_synced = 1
                session.add(ds)
                session.commit()
                synced_count += 1

            except Exception as e:
                errors.append(f"Failed to sync {ds.reference}: {str(e)}")
                continue

        except Exception as e:
            errors.append(f"Failed to sync datasource {ds.id}: {str(e)}")
            continue

    return {
        "status": "completed",
        "synced_count": synced_count,
        "total_docs": total_docs,
        "errors": errors
    }



# Helper to rebuild FAISS index from all current sources (called after delete)
def rebuild_vector_store(session: Session):
    # Reset the vector store
    vector_service = get_vector_service()
    vector_service.reset_vector_store()

    sources = session.exec(select(DataSource)).all()

    from langchain_text_splitters import RecursiveCharacterTextSplitter

    for src in sources:
        docs: List[Document] = []
        try:
            if src.source_type == "file":
                if src.reference.lower().endswith(".txt"):
                    loader = TextLoader(src.reference, encoding="utf-8")
                    docs.extend(loader.load())
                elif src.reference.lower().endswith(".pdf"):
                    loader = PyPDFLoader(src.reference)
                    docs.extend(loader.load())
            elif src.source_type == "url":
                loader = WebBaseLoader(src.reference)
                docs.extend(loader.load())
        except Exception:
            continue

        if docs:
            if src.reference.lower().endswith(".txt") and not src.reference.lower().startswith(CLICKUP_FILE_PREFIX):
                if "_docs.txt" in src.reference.lower():
                    # Use guide-based splitting for documentation files
                    raw_text = "\n".join([doc.page_content for doc in docs])
                    chunks = [chunk.strip() for chunk in raw_text.split("---") if chunk.strip()]
                    splits = [Document(page_content=chunk) for chunk in chunks]
                else:
                    # Use Issue-based splitting for support tickets
                    raw_text = "\n".join([doc.page_content for doc in docs])
                    chunks = [
                        "Issue" + chunk.strip() for chunk in raw_text.split("Issue") if chunk.strip()
                    ]
                    splits = [Document(page_content=chunk) for chunk in chunks]
            else:
                splits = docs
            if len(splits) == 0:
                continue
            get_vector_service().add_documents(splits)


class FileContentResponse(BaseModel):
    filename: str
    content: str
    size_bytes: int

    class Config:
        orm_mode = True


class SaveFileRequest(BaseModel):
    content: str

    class Config:
        orm_mode = True


class SaveFileResponse(BaseModel):
    filename: str
    message: str
    size_bytes: int

    class Config:
        orm_mode = True


@router.get("/files/{filename}/content", response_model=FileContentResponse)
def get_file_content(
    filename: str,
    _: str = Depends(get_current_user),
):
    """
    Get the content of a file from the data folder.
    
    Input: filename (path parameter) - the name of the file to read
    Output: FileContentResponse with filename, content, and size in bytes
    """
    # Sanitize filename to prevent directory traversal attacks
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename. Only simple filenames are allowed.")
    
    file_path = os.path.join(DATA_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=400, detail="Path is not a file")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        file_size = os.path.getsize(file_path)
        
        return FileContentResponse(
            filename=filename,
            content=content,
            size_bytes=file_size
        )
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File contains non-UTF8 content and cannot be read as text")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")


@router.post("/files/{filename}/content", response_model=SaveFileResponse)
def save_file_content(
    filename: str,
    request: SaveFileRequest,
    _: str = Depends(get_current_user),
):
    """
    Save content to a file in the data folder, replacing existing content if file exists.
    
    Input: 
    - filename (path parameter) - the name of the file to save/replace
    - content (request body) - the text content to save
    
    Output: SaveFileResponse with filename, success message, and file size in bytes
    """
    # Sanitize filename to prevent directory traversal attacks
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename. Only simple filenames are allowed.")
    
    file_path = os.path.join(DATA_DIR, filename)
    
    try:
        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # Write content to file (this will overwrite existing file)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(request.content)
        
        file_size = os.path.getsize(file_path)
        
        return SaveFileResponse(
            filename=filename,
            message="File saved successfully",
            size_bytes=file_size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")


class FileInfo(BaseModel):
    filename: str
    size_bytes: int
    modified_at: datetime

    class Config:
        orm_mode = True


class ListFilesResponse(BaseModel):
    files: List[FileInfo]
    total_count: int

    class Config:
        orm_mode = True


@router.get("/files", response_model=ListFilesResponse)
def list_available_files(
    _: str = Depends(get_current_user),
):
    """
    List all available files in the data folder, excluding ClickUp files (those starting with 'clickup_').
    
    Input: None
    Output: ListFilesResponse with array of files and total count
    """
    try:
        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
        
        files = []
        
        # Get all files in the data directory
        for filename in os.listdir(DATA_DIR):
            file_path = os.path.join(DATA_DIR, filename)
            
            # Skip directories and ClickUp files
            if not os.path.isfile(file_path) or filename.startswith("clickup_"):
                continue
            
            # Get file info
            file_stat = os.stat(file_path)
            modified_time = datetime.fromtimestamp(file_stat.st_mtime)
            
            files.append(FileInfo(
                filename=filename,
                size_bytes=file_stat.st_size,
                modified_at=modified_time
            ))
        
        # Sort files by filename
        files.sort(key=lambda x: x.filename)
        
        return ListFilesResponse(
            files=files,
            total_count=len(files)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")


@router.get("/{source_id}/preview")
def preview_source(
    source_id: int,
    session: Session = Depends(get_session),
):
    ds = session.get(DataSource, source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")

    if ds.source_type == "file":
        if not os.path.exists(ds.reference):
            raise HTTPException(status_code=404, detail="File missing on disk")
        # For txt -> text/plain, for pdf -> application/pdf
        media_type = "text/plain" if ds.reference.lower().endswith(".txt") else "application/pdf"
        from fastapi.responses import FileResponse

        return FileResponse(ds.reference, media_type=media_type, filename=os.path.basename(ds.reference))
    elif ds.source_type == "url":
        # Redirect
        from fastapi.responses import RedirectResponse
        return RedirectResponse(ds.reference)
    else:
        raise HTTPException(status_code=400, detail="Unsupported source type") 