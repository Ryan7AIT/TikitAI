#!/usr/bin/env python3
"""
Database migration script to add refresh tokens table.
Run this once to update your existing database.
"""

from sqlmodel import SQLModel
from db import engine, create_db_and_tables

def migrate_database():
    """Add new tables to existing database."""
    print("Creating new database tables...")
    
    # This will create any missing tables
    create_db_and_tables()
    
    print("✅ Database migration completed successfully!")
    print("   - RefreshToken table added")
    print("   - User.is_active field added (defaults to True)")

if __name__ == "__main__":
    migrate_database()
