"""
PostgreSQL checkpoint persistence setup for LangGraph.

Provides PostgresSaver for storing graph state to PostgreSQL.
Each tenant's checkpoints are isolated via thread_id:
f"tenant_{shop_id}_{user_id}".

Note: PostgreSQL imports are lazy-loaded to allow testing without
installing libpq system dependencies. Production should have PostgreSQL
fully installed via docker/k8s.

Usage:
    from backend.agents.checkpoints import get_checkpoint_saver
    saver_cm = get_checkpoint_saver(db_url)
    with saver_cm as saver:
        runnable = graph.compile(checkpointer=saver)
        result = runnable.invoke(state, config)
"""

import os
from importlib import import_module
from typing import Optional
from langchain_core.runnables.config import RunnableConfig
from pathlib import Path
from dotenv import load_dotenv
from shared.runtime_hosts import resolve_runtime_host

# Load backend/.env for local host-run contexts.
_env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


def _build_db_url(db_url: Optional[str] = None) -> str:
    """Build PostgreSQL connection URL from explicit value or environment."""
    if db_url:
        return db_url

    db_host = resolve_runtime_host(os.getenv("DB_HOST", "localhost"))
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "fastcuts_db")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "password")

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


def get_checkpoint_saver(
    db_url: Optional[str] = None,
    setup: bool = True
):
    """
    Create a PostgresSaver context manager for LangGraph checkpoints.
    
    Args:
        db_url: PostgreSQL connection URL. Defaults to env var DB_URL or constructed from DB_HOST, etc.
        setup: If True, create tables automatically (safe to call multiple times)
    
    Returns:
        Context manager from PostgresSaver.from_conn_string(...)
    
    Raises:
        ImportError: If PostgreSQL driver not available
    
    Example:
        saver = get_checkpoint_saver()
        config = RunnableConfig(
            configurable={"thread_id": f"tenant_{shop_id}_{user_id}"}
        )
        state = await graph.ainvoke(initial_state, config, saver_setup=saver)
    """
    
    try:
        pg_module = import_module("langgraph.checkpoint.postgres")
        PostgresSaver = getattr(pg_module, "PostgresSaver")
    except ImportError as e:
        raise ImportError(
            "PostgreSQL driver not available. Install with: "
            "apt-get install libpq-dev (or brew install libpq on Mac), "
            "then: pip install psycopg[binary]"
        ) from e
    
    # Build PostgreSQL connection URL
    db_url = _build_db_url(db_url)
    
    # Current langgraph-checkpoint-postgres exposes from_conn_string context manager.
    return PostgresSaver.from_conn_string(db_url)


def get_sync_checkpoint_saver(db_url: Optional[str] = None):
    """Create sync PostgresSaver for sync graph invocation paths."""
    try:
        pg_module = import_module("langgraph.checkpoint.postgres")
        PostgresSaver = getattr(pg_module, "PostgresSaver")
    except ImportError as e:
        raise ImportError(
            "PostgreSQL sync checkpoint driver not available. "
            "Install psycopg[binary] and ensure libpq compatibility."
        ) from e

    db_url = _build_db_url(db_url)
    return PostgresSaver.from_conn_string(db_url)


def get_pooled_checkpoint_saver(db_url: Optional[str] = None):
    """Create a PostgresSaver backed by a connection pool.

    Uses psycopg_pool.ConnectionPool so that each checkpoint operation
    draws a fresh connection from the pool. This prevents stale-connection
    failures (psycopg.OperationalError: the connection is closed) that
    occur when a single long-lived connection is held across idle periods.

    Returns a ready-to-use PostgresSaver (setup() already called).
    """
    try:
        from psycopg_pool import ConnectionPool
        pg_module = import_module("langgraph.checkpoint.postgres")
        PostgresSaver = getattr(pg_module, "PostgresSaver")
    except ImportError as e:
        raise ImportError(
            "Pooled checkpoint driver not available. "
            "Install psycopg[binary] and psycopg_pool."
        ) from e

    db_url = _build_db_url(db_url)
    pool = ConnectionPool(
        conninfo=db_url,
        max_size=5,
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    return checkpointer


async def setup_checkpoint_tables(db_url: Optional[str] = None):
    """
    Ensure PostgreSQL tables exist for LangGraph checkpoints.
    
    Safe to call multiple times (idempotent).
    Should be called once during backend startup.
    
    Args:
        db_url: PostgreSQL connection URL (defaults to env vars)
    
    Raises:
        ImportError: If PostgreSQL driver not available
    """
    saver_cm = get_checkpoint_saver(db_url, setup=False)

    # PostgresSaver creates checkpoint tables on first use/enter.
    try:
        with saver_cm as saver:
            if hasattr(saver, "setup"):
                saver.setup()
    except Exception as e:
        print(f"Note: {e}")


def build_checkpoint_config(
    shop_id: int,
    user_id: int,
    metadata: Optional[dict] = None
) -> RunnableConfig:
    """
    Build a RunnableConfig for a specific tenant's checkpoint thread.
    
    Thread ID format: tenant_{shop_id}_{user_id}
    This ensures checkpoint isolation per shop owner.
    
    Args:
        shop_id: The shop (tenant) ID
        user_id: The authenticated owner's user ID
        metadata: Optional extra context to pass through graph
    
    Returns:
        RunnableConfig configured for this tenant + owner
    """
    thread_id = f"tenant_{shop_id}_{user_id}"
    
    config = RunnableConfig(
        configurable={"thread_id": thread_id},
        tags=["agent_graph", f"shop_{shop_id}"],
        metadata=metadata or {}
    )
    
    return config


__all__ = [
    "get_checkpoint_saver",
    "get_sync_checkpoint_saver",
    "setup_checkpoint_tables",
    "build_checkpoint_config"
]
