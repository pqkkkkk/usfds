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
    s3_public_endpoint_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("USFDS_S3_PUBLIC_ENDPOINT_URL") or None,
        description="Public/browser-reachable S3 endpoint URL used for signing presigned URLs (defaults to s3_endpoint_url)",
    )
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

    queue_wait_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("USFDS_QUEUE_WAIT_TIMEOUT_SECONDS", "300")),
        description="Max seconds a request waits for a queued request/reply job before answering 504",
    )
    analytics_wait_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("USFDS_ANALYTICS_WAIT_TIMEOUT_SECONDS", "120")),
        description="Same as queue_wait_timeout_seconds, for analytics (insight report) jobs",
    )

    # Server host & port
    host: str = Field(
        default_factory=lambda: os.getenv("USFDS_HOST", "127.0.0.1"),
        description="Host address to bind to",
    )
    port: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_PORT", "8200")),
        description="Port number to bind to",
    )

    # Authentication & RBAC
    auth_mode: str = Field(
        default_factory=lambda: os.getenv("USFDS_AUTH_MODE", "local_auto").lower(),
        description="'local_auto' (desktop auto-login) or 'required' (JWT bearer auth)",
    )
    jwt_secret: str = Field(
        default_factory=lambda: os.getenv("USFDS_JWT_SECRET", "dev-insecure-usfds-jwt-secret-change-in-prod"),
        description="Secret key for HS256 JWT signing",
    )
    access_token_expire_minutes: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        description="Access token lifetime in minutes",
    )
    refresh_token_expire_days: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_REFRESH_TOKEN_EXPIRE_DAYS", "7")),
        description="Refresh token lifetime in days",
    )
    bootstrap_admin_username: str = Field(
        default_factory=lambda: os.getenv("USFDS_BOOTSTRAP_ADMIN_USERNAME", "admin"),
        description="Default bootstrap system_admin username",
    )
    bootstrap_admin_password: str = Field(
        default_factory=lambda: os.getenv("USFDS_BOOTSTRAP_ADMIN_PASSWORD", "admin123"),
        description="Default bootstrap system_admin password",
    )
    cors_origins: str = Field(
        default_factory=lambda: os.getenv(
            "USFDS_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8200,http://127.0.0.1:8200",
        ),
        description="Comma-separated allowed CORS origins or '*'",
    )
    max_plugin_upload_mb: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_MAX_PLUGIN_UPLOAD_MB", "10")),
        description="Maximum allowed plugin archive upload size in MB",
    )
    graph_cache_max_entries: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_GRAPH_CACHE_MAX_ENTRIES", "4")),
        description="Maximum number of in-memory LadybugDB graph entries cached",
    )
    graph_cache_ttl_seconds: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_GRAPH_CACHE_TTL_SECONDS", "600")),
        description="TTL in seconds for cached in-memory LadybugDB graph entries",
    )
    graph_buffer_pool_mb: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_GRAPH_BUFFER_POOL_MB", "256")),
        description="Buffer pool limit in MB per LadybugDB in-memory graph database",
    )
    graph_super_node_degree: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_GRAPH_SUPER_NODE_DEGREE", "50")),
        description="Distinct user degree threshold above which a secondary entity is flagged as a super-node",
    )
    feature_duckdb_memory_mb: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_FEATURE_DUCKDB_MEMORY_MB", "512")),
        description="Memory cap in MB for DuckDB feature compiler execution",
    )
    feature_history_tail_rows: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_FEATURE_HISTORY_TAIL_ROWS", "200000")),
        description="Max historical rows retained in CompiledFeaturePipeline for causal rolling parity",
    )
    feature_preview_max_rows: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_FEATURE_PREVIEW_MAX_ROWS", "200")),
        description="Max rows sampled when previewing a feature",
    )
    feature_script_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_FEATURE_SCRIPT_TIMEOUT_SECONDS", "60")),
        description="Subprocess timeout in seconds for batched PYTHON_CODE features",
    )
    feature_script_max_bytes: int = Field(
        default_factory=lambda: int(os.getenv("USFDS_FEATURE_SCRIPT_MAX_BYTES", "65536")),
        description="Maximum UTF-8 byte length for PYTHON_CODE feature source_code",
    )
    feature_allowed_imports: str = Field(
        default_factory=lambda: os.getenv(
            "USFDS_FEATURE_ALLOWED_IMPORTS",
            "math,re,ipaddress,hashlib,datetime,collections,itertools,functools,statistics,json,numpy,pandas",
        ),
        description="Comma-separated Python module allowlist for PYTHON_CODE features",
    )


settings = Settings()
