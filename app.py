"""
Main application entry point.

This file now simply imports the refactored FastAPI application from core.app.
The application logic has been split into:
- config/: Configuration and database setup
- services/: RAG and vector store services  
- core/: FastAPI application setup
- routers/: API route handlers
"""

from core.app import app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)