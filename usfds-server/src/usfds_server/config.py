import os
from typing import Optional
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
    
    db_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("USFDS_DB_URL") or None,
        description="SQLAlchemy URL of PostgreSQL (client-server mode). When unset, SQLite at db_path is used",
    )
    bullmq_schema: str = Field(
        default_factory=lambda: os.getenv("USFDS_BULLMQ_SCHEMA", "bullmq"),
        description="PostgreSQL schema holding BullMQ queue tables",
    )

    # Storage
    storage_backend: str = Field(
        default_factory=lambda: os.getenv("USFDS_STORAGE_BACKEND", "local").lower(),
        description="'local' (filesystem) or 's3' (S3-compatible object storage, e.g. RustFS)",
    )
    s3_endpoint_url: Optional[str] = Field(default_factory=lambda: os.getenv("USFDS_S3_ENDPOINT_URL") or None)
    s3_bucket: str = Field(default_factory=lambda: os.getenv("USFDS_S3_BUCKET", "usfds"))
    s3_access_key: Optional[str] = Field(default_factory=lambda: os.getenv("USFDS_S3_ACCESS_KEY") or None)
    s3_secret_key: Optional[str] = Field(default_factory=lambda: os.getenv("USFDS_S3_SECRET_KEY") or None)
    s3_region: str = Field(default_factory=lambda: os.getenv("USFDS_S3_REGION", "us-east-1"))
    storage_dir: str = Field(
        default_factory=lambda: os.getenv("USFDS_STORAGE_DIR", "storage_output"),
        description="Path to local file storage directory for datasets, weights, and artifacts",
    )
    
    # Job dispatch
    dispatch_backend: str = Field(
        default_factory=lambda: os.getenv("USFDS_DISPATCH_BACKEND", "sync").lower(),
        description="'sync' (in-process execution) or 'queue' (BullMQ on PostgreSQL, executed by usfds-worker)",
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
