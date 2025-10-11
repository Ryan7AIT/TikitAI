"""
Core FastAPI application setup.
"""
import os
import logging
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from config.database import setup_database
from services.rag_service import initialize_rag_system

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    # Create FastAPI app
    app = FastAPI(title=settings.api_title)
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
    )
    
    # Setup logging
    setup_logging()
    
    # Initialize database and RAG system
    setup_database()
    initialize_rag_system()
    
    # Include API routers
    include_routers(app)
    
    # Setup static file serving
    setup_static_files(app)
    
    logger.info("FastAPI application created and configured")
    return app


def setup_logging():
    """Configure application logging."""
    settings = get_settings()
    
    # Create logs directory
    os.makedirs(settings.logs_directory, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup interaction logger
    # interaction_logger = logging.getLogger("interactions")
    # if not interaction_logger.handlers:
    #     interaction_logger.setLevel(logging.INFO)
    #     ih = logging.FileHandler(os.path.join(settings.logs_directory, "interactions.log"))
    #     ih.setFormatter(logging.Formatter("%(asctime)s\t%(message)s"))
    #     interaction_logger.addHandler(ih)
    
    # # Setup feedback logger
    # feedback_logger = logging.getLogger("feedback")
    # if not feedback_logger.handlers:
    #     feedback_logger.setLevel(logging.INFO)
    #     fh = logging.FileHandler(os.path.join(settings.logs_directory, "feedback.log"))
    #     fh.setFormatter(logging.Formatter("%(asctime)s\t%(message)s"))
    #     feedback_logger.addHandler(fh)


def include_routers(app: FastAPI):
    """Include all API routers."""
    from routers.auth_router import router as auth_router
    from routers.chat_router import router as chat_router
    from routers.data_router import router as data_router
    from routers.messages_router import router as messages_router
    from routers.conversations_router import router as conversations_router
    from routers.metrics_router import router as metrics_router
    from routers.clickup_router import router as clickup_router
    from routers.connections_router import router as connections_router
    from routers.user_management_router import router as user_management_router
    from routers.user_roles_router import router as user_roles_router
    from routers.workspace_router import router as workspace_router
    from routers.feedback_router import router as feedback_router
    from routers.user_router import router as user_router
    
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(data_router)
    app.include_router(messages_router)
    app.include_router(conversations_router)
    app.include_router(metrics_router)
    app.include_router(clickup_router)
    app.include_router(connections_router)
    app.include_router(user_management_router)
    app.include_router(user_roles_router)
    app.include_router(workspace_router)
    app.include_router(feedback_router)
    app.include_router(user_router)
    
    logger.info("All routers included")


def setup_static_files(app: FastAPI):
    """Setup static file serving for frontend."""
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    
    if os.path.isdir(frontend_dir):
        app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
        
        # admin_dir = os.path.join(frontend_dir, "admin")
        # if os.path.isdir(admin_dir):
        #     app.mount("/admin", StaticFiles(directory=admin_dir), name="admin")
        
        # # Root route
        # @app.get("/")
        # def serve_index():
        #     return FileResponse(os.path.join(frontend_dir, "index.html"))
        
        # # Login routes
        # @app.get("/login.html")
        # def serve_login():
        #     return FileResponse(os.path.join(frontend_dir, "login.html"))
        
        # @app.get("/login")
        # def serve_login_no_ext():
        #     return FileResponse(os.path.join(frontend_dir, "login.html"))
        
        logger.info("Static file serving configured")
    else:
        logger.warning(f"Static directory not found: {frontend_dir}")


# Create the FastAPI app instance
app = create_app() 