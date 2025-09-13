"""
Configuration management for the RAG Chat Application.
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # API Configuration
    google_api_key: Optional[str] = None
    
    # Model Configuration
    local_model: str = "llama3.2:latest"
    api_model: str = "gemma-3n-e4b-it" 
    # api_model: str = "gemini-2.5-pro"  
    is_local: bool = False
    discord_bot_token: str

    CLIENT_ID: str = os.getenv("CLIENT_ID")
    CLIENT_SECRET: str = os.getenv("CLIENT_SECRET")
    REDIRECT_URI: str = os.getenv("REDIRECT_URI")
    AUTHORIZE_URL: str = os.getenv("AUTHORIZE_URL")
    TOKEN_URL: str = os.getenv("TOKEN_URL")

    # Embedding Configuration
    # embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # use mutlilang model
    embedding_model: str = "sentence-transformers/all-mpnet-base-v2"
    
    # Database Configuration
    database_url: str = "sqlite:///app.db"
    
    # RAG Configuration
    chunk_size: int = 500
    chunk_overlap: int = 0
    similarity_search_k: int = 3
    qdrant_collection: str = "Aidly"
    qdrant_url: str = "http://localhost:6333"

    # API Configuration
    api_title: str = "RAG Chat API "
    cors_origins: List[str] = ["http://localhost:4200"]
    
    # File Configuration
    data_directory: str = "data"
    logs_directory: str = "logs"
    
    # Chat Configuration
    max_question_length: int = 1000
    
    # Security Configuration
    # TODO: chnage this in productin using env
    secret_key: str = "CHANGE_ME"  
    access_token_expire_minutes: int = 60  # 60 minutes (short-lived)
    refresh_token_expire_days: int = 30  # 30 days (long-lived)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the current settings instance."""
    return settings


def validate_settings():
    """Validate critical settings and raise errors if missing."""
    if not settings.is_local and not settings.google_api_key:
        raise ValueError(
            "GOOGLE_API_KEY environment variable is required when not using local models"
        )
    
    # Ensure directories exist
    os.makedirs(settings.data_directory, exist_ok=True)
    os.makedirs(settings.logs_directory, exist_ok=True)


# Validate settings on module import
validate_settings() 