"""
SQLAlchemy database connection for direct SQL operations
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

Base = declarative_base()
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Construct from individual components if not provided
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "zeroqwait")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "password")
    
    DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

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