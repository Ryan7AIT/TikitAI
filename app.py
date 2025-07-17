"""
Main application entry point.

This file now simply imports the refactored FastAPI application from core.app.
The application logic has been split into:
- config/: Configuration and database setup
- services/: RAG and vector store services  
- core/: FastAPI application setup
- routers/: API route handlers
"""

# Import the configured FastAPI app from the core module
from core.app import app

# The app instance is now available for uvicorn to use:
# uvicorn app:app --reload

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
