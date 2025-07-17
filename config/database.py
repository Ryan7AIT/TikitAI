"""
Database initialization and setup for the RAG Chat Application.
"""
import logging
from sqlmodel import Session, select

from db import create_db_and_tables, engine
from models import User
from auth import hash_password
from config.settings import get_settings

logger = logging.getLogger(__name__)


def initialize_database():
    """Initialize the database and create tables."""
    try:
        create_db_and_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise


def create_default_admin():
    """Create default admin user if it doesn't exist."""
    settings = get_settings()
    
    try:
        with Session(engine) as session:
            # Check if admin user already exists
            existing_admin = session.exec(
                select(User).where(User.username == "admin")
            ).first()
            
            if not existing_admin:
                # Create default admin user
                admin_user = User(
                    username="admin", 
                    hashed_password=hash_password("admin"), 
                    is_admin=True
                )
                session.add(admin_user)
                session.commit()
                logger.info("Default admin user created")
            else:
                logger.info("Admin user already exists")
                
    except Exception as e:
        logger.error(f"Failed to create default admin user: {e}")
        raise


def setup_database():
    """Complete database setup including tables and default data."""
    logger.info("Starting database setup...")
    
    initialize_database()
    create_default_admin()
    
    logger.info("Database setup completed successfully") 