from pathlib import Path
from typing import Union
from sqlalchemy import Engine, create_engine, event


def _apply_sqlite_pragmas(dbapi_connection, connection_record):
    """Apply high-performance and concurrency pragmas to SQLite connection.
    
    - WAL (Write-Ahead Logging): Readers do not block writers, and writers do not block readers.
    - busy_timeout=5000: Auto-wait up to 5 seconds before raising 'database is locked'.
    - foreign_keys=ON: Enforce foreign key constraints.
    - synchronous=NORMAL: Safe durability with significantly reduced disk I/O in WAL mode.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.close()


def create_sqlite_engine(
    db_path: Union[str, Path] = "usfds.db",
    echo: bool = False,
    pool_pre_ping: bool = True,
) -> Engine:
    """Create a configured SQLite SQLAlchemy engine optimized for desktop applications.
    
    Args:
        db_path: Path to the SQLite .db file or ':memory:' for in-memory testing.
        echo: If True, log generated SQL queries.
        pool_pre_ping: Test connection liveness before checking out from pool.
        
    Returns:
        SQLAlchemy Engine instance.
    """
    if str(db_path) == ":memory:":
        connection_url = "sqlite:///:memory:"
    else:
        file_path = Path(db_path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # SQLite URL requires forward slashes on Windows
        posix_path = file_path.as_posix()
        connection_url = f"sqlite:///{posix_path}"

    engine = create_engine(
        connection_url,
        echo=echo,
        connect_args={
            "check_same_thread": False,
            "timeout": 30.0,
        },
        pool_pre_ping=pool_pre_ping,
    )

    # Attach pragmas only for SQLite
    if "sqlite" in engine.url.drivername:
        event.listen(engine, "connect", _apply_sqlite_pragmas)

    return engine


__all__ = ["create_sqlite_engine"]
