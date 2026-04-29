"""
SQLAlchemy database connection for direct SQL operations
"""
import os
import re as _re
from contextvars import ContextVar
from typing import Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv
from shared.runtime_hosts import resolve_runtime_host

Base = declarative_base()
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent / '.env'
# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=False)

# Get database connection details
db_host = resolve_runtime_host(os.getenv("DB_HOST", "localhost"))
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "zeroqwait")
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "password")

# Prefer constructing from components to ensure K8s ConfigMap/Secrets are used
# even if .env defines DATABASE_URL with a hardcoded host (like 'db')
DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

# Fallback to provided DATABASE_URL if explicitly set in environment (not .env) 
# and components seem default/empty, but here we prioritize components.
if os.getenv("DATABASE_URL") and not os.getenv("DB_HOST"):
     DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine
engine_args = {
    "pool_pre_ping": True,
    "pool_size": 5,
    "max_overflow": 10
}

# Handle SQLite for testing/local dev if specified in env
if DATABASE_URL.startswith("sqlite"):
    engine_args = {
        "connect_args": {"check_same_thread": False} 
    }

engine = create_engine(
    DATABASE_URL,
    **engine_args
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Tenant-aware session routing ────────────────────────────────────
# A ContextVar tracks the active tenant schema per-request.
# SQLAlchemy event listeners automatically SET search_path on every
# new session and RESET it when connections return to the pool.

_tenant_schema: ContextVar[Optional[str]] = ContextVar('_tenant_schema', default=None)
_TENANT_RE = _re.compile(r'^tenant_\d+$')

# ── RLS user context ────────────────────────────────────────────────
# Tracks the authenticated user_id for the current request so PostgreSQL
# Row Level Security policies can use current_setting('app.current_user_id').
_current_user_id: ContextVar[Optional[int]] = ContextVar('_current_user_id', default=None)


def set_tenant_for_request(schema: Optional[str]) -> None:
    """Set (or clear) the tenant schema for the current request context."""
    _tenant_schema.set(schema)


def set_current_user_for_request(user_id: Optional[int]) -> None:
    """Set the authenticated user_id for PostgreSQL RLS in the current request context."""
    _current_user_id.set(user_id)


@event.listens_for(SessionLocal, "after_begin")
def _on_session_begin(session, transaction, connection):
    """Set search_path + RLS user when a session begins a transaction."""
    schema = _tenant_schema.get()
    if schema and _TENANT_RE.match(schema):
        connection.execute(text(f"SET search_path TO {schema}, public"))
    else:
        connection.execute(text("SET search_path TO public"))
    # Propagate current user_id into PostgreSQL session for RLS policies.
    uid = _current_user_id.get()
    if uid is not None:
        connection.execute(
            text("SELECT set_config('app.current_user_id', :uid, true)"),
            {"uid": str(uid)},
        )
    else:
        connection.execute(
            text("SELECT set_config('app.current_user_id', '', true)")
        )


def get_db() -> Session:
    """
    Dependency for getting database session
    Use this in FastAPI endpoints
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_sync() -> Session:
    """
    Get database session for synchronous usage
    Use this in background tasks or standalone scripts
    """
    return SessionLocal()