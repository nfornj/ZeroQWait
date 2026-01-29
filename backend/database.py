"""
SQLAlchemy database connection for direct SQL operations
Used for analytics processing and complex queries
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Get database URL from environment
# Supabase provides a direct PostgreSQL connection string
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Construct from individual components if not provided
    db_host = os.getenv("DB_HOST", "db.yuxfpspyzyhesfuspjns.supabase.co")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "postgres")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD")
    
    if not db_password:
        print("WARNING: No DB_PASSWORD found, falling back to SQLite for local development.")
        DATABASE_URL = "sqlite:///./zeroqwait.db"
    else:
        DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

# Create engine
# Create engine
engine_args = {
    "pool_pre_ping": True,
    "pool_size": 5,
    "max_overflow": 10
}

if DATABASE_URL.startswith("sqlite"):
    engine_args = {
        "connect_args": {"check_same_thread": False} # Needed for SQLite + FastAPI
    }

engine = create_engine(
    DATABASE_URL,
    **engine_args
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
