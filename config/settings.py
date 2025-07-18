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
    is_local: bool = False
    
    # Embedding Configuration
    # embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # use mutlilang model
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    
    # Database Configuration
    database_url: str = "sqlite:///app.db"
    
    # RAG Configuration
    chunk_size: int = 500
    chunk_overlap: int = 0
    similarity_search_k: int = 1
    
    # API Configuration
    api_title: str = "RAG Chat API "
    cors_origins: List[str] = ["http://localhost:4200"]
    
    # File Configuration
    data_directory: str = "data"
    logs_directory: str = "logs"
    
    # Chat Configuration
    max_question_length: int = 1000
    
    # Security Configuration
    secret_key: str = "CHANGE_ME"  # Override in production via env var
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    
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