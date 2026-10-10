import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Server configuration for desktop and local deployments."""
    
    app_name: str = "USFDS Server"
    app_version: str = "0.1.0"
    
    # Database
    db_path: str = Field(
        default_factory=lambda: os.getenv("USFDS_DB_PATH", "usfds.db"),
        description="Path to SQLite database file",
    )
    db_echo: bool = Field(
        default_factory=lambda: os.getenv("USFDS_DB_ECHO", "false").lower() == "true",
        description="Enable SQLAlchemy query logging",
    )
    
    # Storage
    storage_dir: str = Field(
        default_factory=lambda: os.getenv("USFDS_STORAGE_DIR", "storage_output"),
        description="Path to local file storage directory for datasets, weights, and artifacts",
    )
    
    # Server host & port
    host: str = Field(
        default_factory=lambda: os.getenv("USFDS_HOST", "127.0.0.1"),
        description="Host address to bind to",
    )
    port: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_PORT", "8000")),
        description="Port number to bind to",
    )


settings = Settings()
