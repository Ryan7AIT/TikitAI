import json
import requests
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlmodel import Session, select
from models import UserIntegrations, UserIntegrationCredentials, ExternalDataSource, DataSource
from routers.clickup_router import _get_teams, _get_spaces, _get_lists, _make_headers, _fetch_tasks


class ClickUpService:
    """Service class to handle ClickUp API operations and reduce code duplication."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def _get_api_token(self, user_integration: UserIntegrations) -> Optional[str]:
        """Retrieve API token from user integration credentials."""
        if not user_integration:
            return None
        
        credentials = self.session.exec(
            select(UserIntegrationCredentials).where(
                UserIntegrationCredentials.user_integration_id == user_integration.id
            )
        ).first()
        
        if not credentials:
            return None
        
        try:
            api_data = json.loads(credentials.credentials)
            return api_data.get("api_token")
        except (json.JSONDecodeError, AttributeError):
            return None
    
    def _validate_integration(self, source_id: int, user_id: int) -> tuple[Optional[UserIntegrations], str]:
        """
        Validate user integration and return integration object and error message if any.
        Returns (user_integration, error_message)
        """
        user_integration = self.session.get(UserIntegrations, source_id)
        if not user_integration:
            return None, "User integration not found, make sure you are connected"
        
        external_source = self.session.get(ExternalDataSource, user_integration.integration_id)
        if not external_source or external_source.source_type != "clickup" or not user_integration.is_connected:
            return None, "ClickUp not connected for this data source"
        
        return user_integration, ""
    
    def _make_api_call(self, api_token: str, endpoint_func, *args) -> tuple[Optional[List], str]:
        """
        Make a ClickUp API call using the provided endpoint function.
        Returns (data, error_message)
        """
        try:
            data = endpoint_func(api_token, *args)
            return data, ""
        except Exception as e:
            return None, f"Failed to fetch data: {str(e)}"
    
    def _check_task_sync_status(self, task_id: str) -> bool:
        """Check if a ClickUp task is synced by looking for its file in DataSource."""
        ds_reference = f"clickup_{task_id}.txt"
        ds = self.session.exec(select(DataSource).where(DataSource.reference == ds_reference)).first()
        return bool(ds and ds.is_synced == 1)
    
    def get_teams(self, source_id: int, user_id: int) -> Dict[str, Any]:
        """Get ClickUp teams for the user integration."""
        user_integration, error = self._validate_integration(source_id, user_id)
        if error:
            return {"data": None, "success": False, "message": error}
        
        api_token = self._get_api_token(user_integration)
        if not api_token:
            return {"data": None, "success": False, "message": "API token not found"}
        
        teams_data, error = self._make_api_call(api_token, _get_teams)
        if error:
            return {"data": None, "success": False, "message": error}
        
        result = [
            {"id": int(team.get("id")), "name": team.get("name", "")}
            for team in teams_data
        ]
        
        return {"data": result, "success": True, "message": "Teams fetched successfully"}
    
    def get_spaces(self, source_id: int, team_id: int, user_id: int) -> Dict[str, Any]:
        """Get ClickUp spaces for a specific team."""
        user_integration, error = self._validate_integration(source_id, user_id)
        if error:
            return {"data": None, "success": False, "message": error}
        
        api_token = self._get_api_token(user_integration)
        if not api_token:
            return {"data": None, "success": False, "message": "API token not found"}
        
        spaces_data, error = self._make_api_call(api_token, _get_spaces, str(team_id))
        if error:
            return {"data": None, "success": False, "message": "Failed to fetch spaces, please try later"}
        
        result = [
            {"id": int(space.get("id")), "name": space.get("name", ""), "team_id": team_id}
            for space in spaces_data
        ]
        
        return {"data": result, "success": True, "message": "Spaces fetched successfully"}
    
    def get_lists(self, source_id: int, space_id: int, user_id: int) -> Dict[str, Any]:
        """Get ClickUp lists for a specific space."""
        user_integration, error = self._validate_integration(source_id, user_id)
        if error:
            return {"data": None, "success": False, "message": error}
        
        api_token = self._get_api_token(user_integration)
        if not api_token:
            return {"data": None, "success": False, "message": "API token not found"}
        
        lists_data, error = self._make_api_call(api_token, _get_lists, str(space_id))
        if error:
            return {"data": None, "success": False, "message": f"Failed to fetch lists: {str(error)}"}
        
        result = [
            {"id": int(list_item.get("id")), "name": list_item.get("name", ""), "space_id": space_id}
            for list_item in lists_data
        ]
        
        return {"data": result, "success": True, "message": "Lists fetched successfully"}
    
    def get_tasks(self, source_id: int, team_id: int, space_id: int, list_id: int, user_id: int) -> Dict[str, Any]:
        """Get ClickUp tasks for a specific list."""
        user_integration, error = self._validate_integration(source_id, user_id)
        if error:
            return {"data": None, "success": False, "message": error}
        
        api_token = self._get_api_token(user_integration)
        if not api_token:
            return {"data": None, "success": False, "message": "API token not found"}
        
        # Create a temporary ClickUpConnection object for _fetch_tasks
        from routers.clickup_router import ClickUpConnection as ClickUpConnModel
        temp_conn = ClickUpConnModel(
            api_token=api_token,
            team="",
            list="",
            team_id=str(team_id),
            list_id=str(list_id)
        )
        
        try:
            tasks = _fetch_tasks(temp_conn)
            result = []
            
            for task in tasks:
                task_id = task.get("id")
                is_synced = self._check_task_sync_status(task_id)
                
                # Parse due date
                due_date = None
                if task.get("due_date"):
                    try:
                        due_date = datetime.fromtimestamp(int(task.get("due_date")) / 1000)
                    except:
                        pass
                
                # Get assignees
                assignees = []
                if task.get("assignees"):
                    assignees = [assignee.get("username", "") for assignee in task.get("assignees", [])]
                
                result.append({
                    "id": int(task_id),
                    "name": task.get("name", ""),
                    "status": task.get("status", {}).get("status", "") if task.get("status") else "",
                    "priority": task.get("priority", {}).get("priority", "") if task.get("priority") else None,
                    "assignees": assignees,
                    "dueDate": due_date,
                    "description": task.get("description", ""),
                    "listId": list_id,
                    "isSelected": False,
                    "isSynced": is_synced
                })
            
            return {"data": result, "success": True, "message": "Tasks fetched successfully"}
            
        except Exception as e:
            return {"data": None, "success": False, "message": f"Failed to fetch tasks: {str(e)}"}
    
    def get_tickets(self, source_id: int, user_id: int, team_id: Optional[str] = None, 
                   space_id: Optional[str] = None, list_id: Optional[str] = None, 
                   search: Optional[str] = None) -> Dict[str, Any]:
        """Get ClickUp tickets with optional filtering."""
        user_integration, error = self._validate_integration(source_id, user_id)
        if error:
            return {"data": None, "success": False, "message": error}
        
        api_token = self._get_api_token(user_integration)
        if not api_token:
            return {"data": None, "success": False, "message": "API token not found"}
        
        try:
            tickets = []
            
            # Determine what to fetch based on provided filters
            if list_id:
                tickets.extend(self._fetch_tasks_from_list(api_token, list_id))
            elif space_id:
                lists = _get_lists(api_token, space_id)
                for list_item in lists:
                    tickets.extend(self._fetch_tasks_from_list(api_token, list_item.get("id")))
            elif team_id:
                spaces = _get_spaces(api_token, team_id)
                for space in spaces:
                    space_lists = _get_lists(api_token, space.get("id"))
                    for list_item in space_lists:
                        tickets.extend(self._fetch_tasks_from_list(api_token, list_item.get("id")))
            else:
                # No specific filter - fetch from all teams accessible with this token
                teams = _get_teams(api_token)
                for team in teams[:1]:  # Limit to first team to avoid timeout
                    spaces = _get_spaces(api_token, team.get("id"))
                    for space in spaces:
                        space_lists = _get_lists(api_token, space.get("id"))
                        for list_item in space_lists:
                            tickets.extend(self._fetch_tasks_from_list(api_token, list_item.get("id")))
            
            # Apply search filter if provided
            if search:
                search_lower = search.lower()
                tickets = [t for t in tickets if search_lower in t.get("name", "").lower() or 
                          (t.get("description") and search_lower in t.get("description", "").lower())]
            
            return {"data": tickets, "success": True, "message": "Tickets fetched successfully"}
            
        except Exception as e:
            return {"data": None, "success": False, "message": f"Failed to fetch tickets: {str(e)}"}
    
    def _fetch_tasks_from_list(self, api_token: str, list_id: str) -> List[Dict]:
        """Helper function to fetch tasks from a specific ClickUp list."""
        url = f"https://api.clickup.com/api/v2/list/{list_id}/task?include_closed=true"
        resp = requests.get(url, headers=_make_headers(api_token))
        
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        tasks = data.get("tasks", [])
        
        tickets = []
        for task in tasks:
            # Determine sync status
            is_synced = self._check_task_sync_status(task.get("id"))
            
            # Parse due date
            due_date = None
            if task.get("due_date"):
                try:
                    timestamp = int(task.get("due_date")) / 1000
                    due_date = datetime.fromtimestamp(timestamp).isoformat()
                except:
                    pass
            
            # Get assignees
            assignees = []
            if task.get("assignees"):
                assignees = [assignee.get("username", "") for assignee in task.get("assignees", [])]
            
            ticket = {
                "id": str(task.get("id")),
                "name": task.get("name", ""),
                "status": task.get("status", {}).get("status", "") if task.get("status") else "",
                "priority": task.get("priority", {}).get("priority", "") if task.get("priority") else None,
                "assignees": assignees,
                "dueDate": due_date,
                "description": task.get("description", ""),
                "listId": str(list_id),
                "isSynced": is_synced,
                "isSelected": False
            }
            tickets.append(ticket)
        
        return tickets
    
    def sync_task(self, source_id: int, ticket_id: str, user_id: int, workspace_id: str) -> Dict[str, Any]:
        """Sync a ClickUp task by its task ID and create/update datasource record."""
        user_integration, error = self._validate_integration(source_id, user_id)
        if error:
            return {"data": None, "success": False, "message": error}
        
        api_token = self._get_api_token(user_integration)
        if not api_token:
            return {"data": None, "success": False, "message": "API token not found"}
        
        try:
            # Import required functions and constants from data_router
            # TODO: move those function inot this service
            from routers.data_router import (
                _fetch_clickup_task, _build_file_content, _write_to_file,
                _get_or_create_datasource, _update_datasource_metadata,
                _embed_content, _mark_as_synced, CLICKUP_FILE_PREFIX, DATA_DIR
            )
            from routers.clickup_router import _fetch_comments
            import os
            
            # Retrieve task data from ClickUp API
            task_data = _fetch_clickup_task(api_token, ticket_id)
            
            # Fetch comments (for completeness, currently not used in file content)
            _fetch_comments(ticket_id, api_token)
            
            # Build local file content and save to disk
            base_dir = "data"
            filename = f"clickup_{ticket_id}.txt"
            filepath = os.path.join(base_dir, f"workspaces/{workspace_id}/{CLICKUP_FILE_PREFIX}{ticket_id}.txt")

            dir_path = os.path.dirname(filepath)
            os.makedirs(dir_path, exist_ok=True)
            content = _build_file_content(ticket_id, task_data)
            file_path = _write_to_file(content, filepath)
            
            # Create or update datasource record with workspace_id
            ds = _get_or_create_datasource(self.session, filename, file_path, workspace_id)
            _update_datasource_metadata(ds, file_path, task_data)
            
            # Embed content in vector store with workspace_id and mark as synced
            added_docs = _embed_content(content, filename, workspace_id)
            _mark_as_synced(ds)
            
            # Save changes to database
            self.session.add(ds)
            self.session.commit()
            
            result_data = {
                "status": "synced",
                "added_docs": added_docs,
                "last_synced_at": ds.last_synced_at,
                "task_id": ticket_id,
                "task_name": task_data.get('name', ''),
                "filename": filename
            }
            
            return {"data": result_data, "success": True, "message": "ClickUp task synced successfully"}
            
        except Exception as e:
            return {"data": None, "success": False, "message": f"Failed to sync ClickUp task: {str(e)}"}
