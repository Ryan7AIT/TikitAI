import os
from datetime import datetime
from typing import List
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from pydantic import BaseModel
from sqlmodel import Session, exists, select
from db import get_session
from models import DataSource, ExternalDataSource, ClickUpConnection, UserIntegrations, UserIntegrationCredentials
from auth import get_current_user

from services.vector_service import get_vector_service
from langchain_community.document_loaders import TextLoader, PyPDFLoader, WebBaseLoader
from langchain_core.documents import Document
from routers.clickup_router import _fetch_comments, _make_headers
import requests

import logging
from markdown import markdown
from weasyprint import HTML
import tempfile, json
from fastapi.responses import FileResponse


CLICKUP_FILE_PREFIX = "clickup_"
router = APIRouter(prefix="/datasources", tags=["data"])
DATA_DIR = "data"  
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
    owner_id: Optional[int] = None
    workspace_id: Optional[int] = None

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

class ConnectExternalPayload(BaseModel):
    api_token: str
    team: Optional[str] = None
    list: Optional[str] = None

class UrlPayload(BaseModel):
    url: str

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


@router.get("/external", response_model=List[ExternalDataSourceOut])
def get_external_data(
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    external_sources = session.exec(select(ExternalDataSource)).all()
    
    result = []
    for source in external_sources:
        is_connected = session.exec(
            select(exists().where(
                UserIntegrations.user_id == _.id,
                UserIntegrations.integration_id == source.id
            ))
        ).first()

        result.append(ExternalDataSourceOut(
            id=source.id,
            name=source.name,
            description=source.description,
            is_connected= is_connected,
            type=source.source_type
        ))
    
    return result

@router.post("/external/{source_id}/connect")
def connect_external_data(
    source_id: int,
    payload: ConnectExternalPayload,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    # TODO: change this to get the api token from the backend
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
        
        return {
            'succes' : True,
            'message' : "Successfully connected to ClickUp",
            'data' : []
            }
    else:
        raise HTTPException(status_code=400, detail=f"Connection not implemented for {external_source.source_type}")

@router.get("/external/{source_id}/integrations", response_model=List[UserIntegrations])
def get_user_integrations(
    source_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    external_source = session.get(ExternalDataSource, source_id)
    if not external_source:
        raise HTTPException(status_code=404, detail="External data source not found")
    
    user_integrations = session.exec(
        select(UserIntegrations).where(
            UserIntegrations.integration_id == source_id,
            UserIntegrations.user_id == _.id
        )
    ).all()
    
    return user_integrations

# get external data details
@router.get("/external/{integration_id}", response_model=ExternalDataSourceDetailsOut)
def get_external_data_details(
    integration_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    # source_id = user_integration_id
    # external_source = session.get(UserIntegrations, integration_id)
    statement = (
        select(UserIntegrations, ExternalDataSource)
        .join(ExternalDataSource, UserIntegrations.integration_id == ExternalDataSource.id)
        .where(UserIntegrations.id == integration_id, UserIntegrations.user_id == _.id) 
    )

    user_integration, external_source = session.exec(statement).first()
    print(external_source)
    if not external_source:
        raise HTTPException(status_code=404, detail="External data source not found")
    
    return ExternalDataSourceDetailsOut(
        id=external_source.id,
        name="test",
        description="tese description",
        is_connected=external_source.is_connected,
        type=external_source.source_type
    )

# update extrean data deatils
@router.patch("/external/{integration_id}", response_model=ExternalDataSourceDetailsOut)
def update_external_data_details(
    integration_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    user_integration = session.get(UserIntegrations, integration_id)
    if not user_integration or user_integration.user_id != _.id:
        raise HTTPException(status_code=404, detail="User integration not found")
    
    # Update name and description in UserIntegrations table
    if name is not None:
        user_integration.name = name
    if description is not None:
        user_integration.description = description
    user_integration.updated_at = datetime.utcnow()
    session.add(user_integration)
    session.commit()
    session.refresh(user_integration)

    return ExternalDataSourceDetailsOut(
        id=user_integration.integration_id,
        name=user_integration.name or "",
        description=user_integration.description or "",
        is_connected=user_integration.is_connected,
        type=session.get(ExternalDataSource, user_integration.integration_id).source_type
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
        workspace_id = _.current_workspace_id
        sources = session.exec(
            select(DataSource)
            .where(
                (DataSource.source_type == "file") &
                (DataSource.workspace_id == workspace_id)
            )
        ).all()
        return sources

@router.post("/upload", response_model=List[DataSourceOut])
async def upload_file(
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    tags: str = Form(...),
    workspace_id: str = Form(None),
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    saved_sources = []
    workspace_id = workspace_id  or _.current_workspace_id
    owner_id = _.id

    workspace_dir = os.path.join(DATA_DIR, "workspaces", str(workspace_id))
    os.makedirs(workspace_dir, exist_ok=True)

    # Save file
    for file in files:
        dest_path = os.path.join(workspace_dir, file.filename)
        with open(dest_path, "wb") as f:
            f.write(await file.read())

        ds = DataSource(source_type="file", reference=file.filename, size_mb=os.path.getsize(dest_path) / (1024 * 1024), category=category, tags=tags, path=dest_path, workspace_id=workspace_id, owner_id=owner_id)
        session.add(ds)
        session.commit()
        session.refresh(ds)
        saved_sources.append(ds)

    return saved_sources

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
    if ds.source_type == "file" and os.path.exists('data/' + ds.reference):
        try:
            os.remove('data/' + ds.reference)
        except Exception:
            pass

    session.delete(ds)
    session.commit()

    # Rebuild vector store to ensure removed docs are gone
    rebuild_vector_store(session)

    return {"status": "deleted"}

# export pdf
@router.post("/export-pdf")
async def export_markdown_to_pdf(
    md_text: str = Form(...),
    company_name: str = Form("DATAFIRST"),
    logo_url: str = Form(None),              # e.g. https://example.com/logo.png
    stats_json: str = Form("{}")             # JSON string: {"Total Pages": 5, ...}
):
    # Convert Markdown to HTML
    html_md = markdown(md_text)

    # Parse stats
    try:
        stats = json.loads(stats_json)
    except json.JSONDecodeError:
        stats = {}

    # Build a stats table HTML
    stats_rows = "".join(
        f"<tr><th>{key}</th><td>{value}</td></tr>"
        for key, value in stats.items()
    )
    stats_block = f"""
    <section class="stats">
      <h2>Document Statistics</h2>
      <table>
        <tbody>
          {stats_rows}
        </tbody>
      </table>
    </section>
    """ if stats_rows else ""

    # Full HTML template
    html = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <style>
          @page {{
            size: A4;
            margin: 20mm 15mm 20mm 15mm;
            @bottom-center {{
              content: "Page " counter(page) " of " counter(pages);
              font-size: 0.75rem;
              color: #666;
            }}
          }}
          body {{
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            color: #333;
            line-height: 1.5;
          }}
          header {{
            display: flex;
            align-items: center;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
            margin-bottom: 20px;
          }}
          header img {{
            height: 50px;
            margin-right: 15px;
          }}
          header h1 {{
            font-size: 1.5rem;
            margin: 0;
          }}
          .stats {{
            margin-bottom: 20px;
            padding: 10px;
            background: #f9f9f9;
            border: 1px solid #eee;
          }}
          .stats h2 {{
            font-size: 1.1rem;
            margin-top: 0;
          }}
          .stats table {{
            width: 100%;
            border-collapse: collapse;
          }}
          .stats th, .stats td {{
            text-align: left;
            padding: 4px 8px;
            border-bottom: 1px solid #eee;
          }}
          .markdown-body {{
            /* GitHub-like Markdown styling */
            font-size: 0.95rem;
          }}
          .markdown-body h1, .markdown-body h2, .markdown-body h3 {{
            color: #222;
            margin-top: 1.5em;
          }}
          .markdown-body pre, .markdown-body code {{
            background: #f3f4f6;
            padding: 0.2em 0.4em;
            border-radius: 4px;
            font-family: Menlo, monospace;
          }}
          .markdown-body blockquote {{
            border-left: 4px solid #ddd;
            color: #666;
            margin: 1em 0;
            padding-left: 1em;
            background: #fafafa;
          }}
          .markdown-body a {{
            color: #0366d6;
            text-decoration: none;
          }}
          .markdown-body a:hover {{
            text-decoration: underline;
          }}
        </style>
      </head>
      <body>
        <header>
          { f'<img src="{logo_url}" alt="Logo">' if logo_url else '' }
          <h1>{company_name}</h1>
        </header>

        {stats_block}

        <article class="markdown-body">
          {html_md}
        </article>
      </body>
    </html>
    """

    # Render to PDF
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as pdf_file:
        HTML(string=html).write_pdf(pdf_file.name)
        return FileResponse(
            pdf_file.name,
            media_type="application/pdf",
            filename="document.pdf"
        )

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

def _embed_content(content: str, source_reference: str) -> int:
    """Split the content and add each chunk to the vector store using standardized logic. Returns number of chunks added."""
    return get_vector_service().embed_content_string(content, source_reference)

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
    added_docs = _embed_content(content, filename)
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
            if ds.reference.lower().endswith(".txt") or ds.reference.lower().endswith(".md"):
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

    # Add to vector store using standardized embedding logic
    added_docs = 0
    if documents:
        splits = get_vector_service().process_documents_for_embedding(documents, [ds.reference])
        if splits:
            get_vector_service().add_documents(splits)
            added_docs = len(splits)

    # Mark as synced
    from datetime import datetime as _dt
    ds.last_synced_at = _dt.utcnow()
    ds.is_synced = 1
    session.add(ds)
    session.commit()

    return {"status": "synced", "added_docs": added_docs, "last_synced_at": ds.last_synced_at}


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
    # if ds.source_type == "file" and ds.reference:
    #     file_path = os.path.join(DATA_DIR, ds.reference) if not os.path.isabs(ds.reference) else ds.reference
    #     if os.path.exists(file_path):
    #         try:
    #             os.remove(file_path)
    #         except Exception:
    #             pass

    # Remove from database
    # session.delete(ds)
    # update is_synced to 0
    ds.is_synced = 0
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


@router.post("/regular/sync")
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
                    if ds.reference.lower().endswith(".txt") or ds.reference.lower().endswith(".md"):
                        loader = TextLoader(os.path.join(dir, ds.reference), encoding="utf-8")
                        documents.extend(loader.load())
                    elif ds.reference.lower().endswith(".pdf"):
                        loader = PyPDFLoader(os.path.join(dir, ds.reference))
                        documents.extend(loader.load())
                elif ds.source_type == "url":
                    loader = WebBaseLoader(ds.reference)
                    documents.extend(loader.load())

                if documents:
                    splits = get_vector_service().process_documents_for_embedding(documents, [ds.reference])
                    if splits:
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

@router.post("/regular/unsync")
def unsync_all_sources(
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Unsync all datasources that are currently synced."""
    sources = session.exec(select(DataSource).where(DataSource.is_synced == 1)).all()

    for ds in sources:
        ds.is_synced = 0
        session.commit()

    # Rebuild vector store to ensure removed docs are gone
    rebuild_vector_store(session)

    return {"status": "unsynced"}

# Helper to rebuild FAISS index from all synced sources (called after delete)
def rebuild_vector_store(session: Session):
    """Rebuild the vector store using only synced datasources from the database."""
    # Reset the vector store
    vector_service = get_vector_service()
    vector_service.reset_vector_store()

    # Get only synced datasources
    synced_sources = session.exec(select(DataSource).where(DataSource.is_synced == 1)).all()
    
    total_docs_added = 0
    for src in synced_sources:
        try:
            docs_added = vector_service.embed_datasource(src)
            total_docs_added += docs_added
        except Exception as e:
            logging.error(f"Error rebuilding vector store for datasource {src.reference}: {e}")
            continue
    
    logging.info(f"Vector store rebuilt with {total_docs_added} document chunks from {len(synced_sources)} synced datasources")

# markdown preview routes

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

    workspace_id = _.current_workspace_id
    file_path = os.path.join(DATA_DIR, "workspaces", str(workspace_id), filename)

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


    try:
        # Ensure data directory exists
        workspace_id = _.current_workspace_id
        file_path = os.path.join(DATA_DIR, "workspaces", str(workspace_id), filename)

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

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
        os.makedirs(DATA_DIR, exist_ok=True)
        workspace_id = _.current_workspace_id
        current_workspace = os.path.join(DATA_DIR, "workspaces", str(workspace_id))
        files = []

        for filename in os.listdir(current_workspace):
            file_path = os.path.join(current_workspace, filename)

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
        # files.sort(key=lambda x: x.filename)
        
        return ListFilesResponse(
            files=files,
            total_count=len(files)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

@router.get("/files/{reference}/is_in_db")
def is_file_in_db(
    reference: str,
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """
    Check if a file is in the database.
    
    Input: 
    - reference (path parameter) - the file reference to check
    
    Output: JSON response with 'exists' field
    """
    file_exists = session.query(exists().where(DataSource.reference == reference)).scalar()
    return {"exists": file_exists}

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

@router.get("/debug/vector-store-info")
def get_vector_store_info(
    _: str = Depends(get_current_user),
):
    """Debug endpoint to check vector store status and document count."""
    vector_service = get_vector_service()
    info = vector_service.get_vector_store_info()
    return info

@router.post("/debug/reload-vector-store")
def reload_vector_store(
    session: Session = Depends(get_session),
    _: str = Depends(get_current_user),
):
    """Debug endpoint to reload all synced documents into the vector store."""
    vector_service = get_vector_service()
    
    # Reset and reload
    vector_service.reset_vector_store()
    vector_service.load_documents_from_data_folder()
    
    # Get updated info
    info = vector_service.get_vector_store_info()
    
    return {
        "status": "reloaded",
        "vector_store_info": info
    } 