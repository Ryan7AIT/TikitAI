from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text

DATABASE_URL = "sqlite:///app.db"

engine = create_engine(
    DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
)


def create_db_and_tables():
    """Create database tables based on SQLModel metadata. (created in models.py)"""
    SQLModel.metadata.create_all(engine)

    # --- lightweight migrations ---
    with engine.connect() as conn:
        # Ensure last_synced_at column exists on datasource
        cols = conn.execute(text("PRAGMA table_info(datasource)")).fetchall()
        if cols and not any(row[1] == "last_synced_at" for row in cols):
            conn.execute(text("ALTER TABLE datasource ADD COLUMN last_synced_at DATETIME"))
            conn.commit()

        cols = conn.execute(text("PRAGMA table_info(message)")).fetchall()
        if cols and not any(row[1] == "conversation_id" for row in cols):
            conn.execute(text("ALTER TABLE message ADD COLUMN conversation_id INTEGER"))
            conn.commit()

        cols = conn.execute(text("PRAGMA table_info(message)")).fetchall()
        if cols and not any(row[1] == "feedback" for row in cols):
            conn.execute(text("ALTER TABLE message ADD COLUMN feedback TEXT"))
            conn.commit()

        cols = conn.execute(text("PRAGMA table_info(datasource)")).fetchall()
        if cols and not any(row[1] == "size_mb" for row in cols):
            conn.execute(text("ALTER TABLE datasource ADD COLUMN size_mb REAL"))
            conn.commit()
        if cols and not any(row[1] == "category" for row in cols):
            conn.execute(text("ALTER TABLE datasource ADD COLUMN category TEXT"))
            conn.commit()
        if cols and not any(row[1] == "tags" for row in cols):
            conn.execute(text("ALTER TABLE datasource ADD COLUMN tags TEXT"))
            conn.commit()
        if cols and not any(row[1] == "is_synced" for row in cols):
            conn.execute(text("ALTER TABLE datasource ADD COLUMN is_synced INTEGER"))
            conn.commit()
        if cols and not any(row[1] == "path" for row in cols):
            conn.execute(text("ALTER TABLE datasource ADD COLUMN path TEXT"))
            conn.commit()

        cols = conn.execute(text("PRAGMA table_info(user)")).fetchall()
        if cols and not any(row[1] == "is_super_admin" for row in cols):
            conn.execute(text("ALTER TABLE user ADD COLUMN is_super_admin INTEGER"))
            conn.commit()

        cols = conn.execute(text("PRAGMA table_info(user)")).fetchall()
        if cols and not any(row[1] == "current_workspace_id" for row in cols):
            conn.execute(text("ALTER TABLE user ADD COLUMN current_workspace_id INTEGER"))
            conn.commit()

        cols = conn.execute(text("PRAGMA table_info(datasource)")).fetchall()
        if cols and not any(row[1] == "workspace_id" for row in cols):
            conn.execute(text("ALTER TABLE datasource ADD COLUMN workspace_id INTEGER"))
            conn.commit()

        cols = conn.execute(text("PRAGMA table_info(conversation)")).fetchall()
        if cols and not any(row[1] == "workspace_id" for row in cols):
            conn.execute(text("ALTER TABLE conversation ADD COLUMN workspace_id INTEGER"))
            conn.commit()

        cols = conn.execute(text("PRAGMA table_info(user)")).fetchall()
        if cols and not any(row[1] == "email" for row in cols):
            conn.execute(text("ALTER TABLE user ADD COLUMN email TEXT"))
            conn.commit()

        # add owner_id to datasource
        cols = conn.execute(text("PRAGMA table_info(datasource)")).fetchall()
        if cols and not any(row[1] == "owner_id" for row in cols):
            conn.execute(text("ALTER TABLE datasource ADD COLUMN owner_id INTEGER"))
            conn.commit()

        # add name and description to UserIntegrations
        cols = conn.execute(text("PRAGMA table_info(userintegrations)")).fetchall()
        if cols and not any(row[1] == "name" for row in cols):
            conn.execute(text("ALTER TABLE userintegrations ADD COLUMN name TEXT"))
            conn.commit()
        if cols and not any(row[1] == "description" for row in cols):
            conn.execute(text("ALTER TABLE userintegrations ADD COLUMN description TEXT"))
            conn.commit()
        if cols and not any(row[1] == "active_repository_id" for row in cols):
            conn.execute(text("ALTER TABLE userintegrations ADD COLUMN active_repository_id INTEGER"))
            conn.commit()

        # add active_repository_id to workspace
        cols = conn.execute(text("PRAGMA table_info(workspace)")).fetchall()
        if cols and not any(row[1] == "active_repository_id" for row in cols):
            conn.execute(text("ALTER TABLE workspace ADD COLUMN active_repository_id INTEGER"))
            conn.commit()

        # add active_repository_branch to workspace
        cols = conn.execute(text("PRAGMA table_info(workspace)")).fetchall()
        if cols and not any(row[1] == "active_repository_branch" for row in cols):
            conn.execute(text("ALTER TABLE workspace ADD COLUMN active_repository_branch TEXT"))
            conn.commit()

        # add user_id to conversation
        cols = conn.execute(text("PRAGMA table_info(conversation)")).fetchall()
        if cols and not any(row[1] == "user_id" for row in cols):
            conn.execute(text("ALTER TABLE conversation ADD COLUMN user_id INTEGER"))
            conn.commit()

    # Initialize external data sources if they don't exist
    _initialize_external_data_sources()


def _initialize_external_data_sources():
    """Populate ExternalDataSource table with default integrations."""
    from models import ExternalDataSource
    
    with Session(engine) as session:
        # Check if external data sources already exist
        existing = session.exec(text("SELECT COUNT(*) FROM externaldatasource")).first()
        if existing and existing[0] > 0:
            return  # Already initialized
        
        # Add default external data sources
        default_sources = [
            {
                "name": "ClickUp",
                "description": "ClickUp is a project management tool that allows you to create and manage your projects.",
                "source_type": "clickup",
                "is_connected": False
            },
            {
                "name": "Slack",
                "description": "Slack is a messaging app for teams that makes it easy to communicate and collaborate.",
                "source_type": "slack",
                "is_connected": False
            },
            {
                "name": "Discord",
                "description": "Discord is a communication platform designed for creating communities.",
                "source_type": "discord",
                "is_connected": False
            },
            {
                "name": "GitHub",
                "description": "GitHub is a platform for version control and collaboration.",
                "source_type": "github",
                "is_connected": False
            },
            {
                "name": "Notion",
                "description": "Notion is a project management tool that allows you to create and manage your projects.",
                "source_type": "notion", 
                "is_connected": False
            },
        ]
        
        for source_data in default_sources:
            source = ExternalDataSource(**source_data)
            session.add(source)
        
        session.commit()



def get_session():
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session 