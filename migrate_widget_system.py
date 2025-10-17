"""
Database migration script to add Widget System tables.

This script adds the following tables:
- Bot: Chatbots that can be embedded via widgets
- WidgetToken: JWT tokens for widget authentication
- ChatSession: Sessions for widget visitors
- Updates Message table to support widget sessions

Run this script after updating models.py to create the new tables.
"""

from sqlmodel import SQLModel, create_engine, Session, select
from models import (
    User, Bot, WidgetToken, ChatSession, Message, 
    Workspace, WorkspaceUser, RefreshToken
)
from config.settings import get_settings
from auth import hash_password

settings = get_settings()

def run_migration():
    """Run the database migration to add widget system tables."""
    
    print("🔄 Starting Widget System migration...")
    
    # Create engine
    engine = create_engine(settings.database_url, echo=True)
    
    # Create all tables (this will only create new ones)
    print("\n📊 Creating new tables...")
    SQLModel.metadata.create_all(engine)
    
    print("\n✅ Widget System tables created successfully!")
    print("\nNew tables added:")
    print("  - Bot: Chatbots for embedding")
    print("  - WidgetToken: Widget authentication tokens")
    print("  - ChatSession: Visitor chat sessions")
    print("  - Message.chat_session_id: Link messages to widget sessions")
    
    # Optional: Create a sample bot for testing
    create_sample = input("\n❓ Create a sample bot for testing? (y/n): ").lower().strip()
    
    if create_sample == 'y':
        create_sample_bot(engine)
    
    print("\n🎉 Migration completed successfully!")
    print("\n📝 Next steps:")
    print("  1. Update main.py to include widget_router")
    print("  2. Test widget generation: POST /widget/generate")
    print("  3. Create bots via: POST /widget/bots")
    print("  4. Generate widget tokens and embed on websites")

def create_sample_bot(engine):
    """Create a sample bot for testing."""
    
    with Session(engine) as session:
        # Find admin user
        admin = session.exec(select(User).where(User.username == "admin")).first()
        
        if not admin:
            print("\n⚠️  No admin user found. Creating one...")
            admin = User(
                username="admin",
                hashed_password=hash_password("admin"),
                is_admin=True
            )
            session.add(admin)
            session.commit()
            session.refresh(admin)
        
        # Find or create a workspace
        workspace = session.exec(select(Workspace)).first()
        
        if not workspace:
            print("\n⚠️  No workspace found. Creating one...")
            from models import Workspace
            workspace = Workspace(
                name="Default Workspace",
                description="Default workspace for testing"
            )
            session.add(workspace)
            session.commit()
            session.refresh(workspace)
            
            # Add admin to workspace
            workspace_user = WorkspaceUser(
                workspace_id=workspace.id,
                user_id=admin.id,
                role="admin"
            )
            session.add(workspace_user)
            
            # Set as admin's current workspace
            admin.current_workspace_id = workspace.id
            session.add(admin)
            session.commit()
        
        # Check if sample bot already exists
        existing_bot = session.exec(
            select(Bot).where(Bot.name == "Demo Support Bot")
        ).first()
        
        if existing_bot:
            print("\n✅ Sample bot already exists!")
            print(f"   Bot ID: {existing_bot.id}")
            print(f"   Name: {existing_bot.name}")
            return
        
        # Create sample bot
        sample_bot = Bot(
            name="Demo Support Bot",
            description="A demo chatbot for testing the widget system",
            workspace_id=workspace.id,
            owner_id=admin.id,
            system_prompt=(
                "You are a helpful customer support assistant. "
                "Be friendly, professional, and concise in your responses. "
                "Welcome users warmly and help them with their questions."
            ),
            is_active=True
        )
        
        session.add(sample_bot)
        session.commit()
        session.refresh(sample_bot)
        
        print("\n✅ Sample bot created successfully!")
        print(f"   Bot ID: {sample_bot.id}")
        print(f"   Name: {sample_bot.name}")
        print(f"   Owner: {admin.username}")
        print(f"   Workspace: {workspace.name}")
        print("\n💡 To generate a widget token:")
        print(f"   1. Login as admin to get access token")
        print(f"   2. POST /widget/generate with body: {{\"bot_id\": {sample_bot.id}}}")


if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
