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


def get_session():
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session 