"""
Supabase client initialization and helper functions for database operations.
"""
import os
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

# Explicitly load .env from the backend directory
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://yuxfpspyzyhesfuspjns.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY environment variable is required")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase() -> Client:
    """
    Dependency to get Supabase client instance.
    This replaces the old get_db() dependency.
    """
    return supabase


# Helper functions for common database operations

def execute_query(table: str, query_builder):
    """Execute a Supabase query and return the result."""
    try:
        response = query_builder.execute()
        return response.data
    except Exception as e:
        raise Exception(f"Database query failed: {str(e)}")


def insert_one(table: str, data: dict):
    """Insert a single record and return it."""
    try:
        response = supabase.table(table).insert(data).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        raise Exception(f"Insert failed: {str(e)}")


def update_one(table: str, id: int, data: dict):
    """Update a single record by id and return it."""
    try:
        response = supabase.table(table).update(data).eq("id", id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        raise Exception(f"Update failed: {str(e)}")


def delete_one(table: str, id: int):
    """Delete a single record by id."""
    try:
        response = supabase.table(table).delete().eq("id", id).execute()
        return response.data
    except Exception as e:
        raise Exception(f"Delete failed: {str(e)}")


def find_by_id(table: str, id: int):
    """Find a single record by id."""
    try:
        response = supabase.table(table).select("*").eq("id", id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        raise Exception(f"Query failed: {str(e)}")


def find_one(table: str, column: str, value):
    """Find a single record by column value."""
    try:
        response = supabase.table(table).select("*").eq(column, value).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        raise Exception(f"Query failed: {str(e)}")


def find_all(table: str, filters: Optional[dict] = None, limit: int = 100, offset: int = 0):
    """Find all records with optional filters."""
    try:
        query = supabase.table(table).select("*")
        
        if filters:
            for column, value in filters.items():
                query = query.eq(column, value)
        
        response = query.limit(limit).offset(offset).execute()
        return response.data
    except Exception as e:
        raise Exception(f"Query failed: {str(e)}")


# Storage helper functions for file uploads

def upload_file(bucket: str, file_path: str, file_data: bytes, content_type: str = None):
    """Upload a file to Supabase Storage."""
    try:
        options = {}
        if content_type:
            options["content-type"] = content_type
        
        response = supabase.storage.from_(bucket).upload(
            file_path, 
            file_data,
            file_options=options
        )
        return response
    except Exception as e:
        raise Exception(f"File upload failed: {str(e)}")


def get_public_url(bucket: str, file_path: str):
    """Get public URL for a file in Supabase Storage."""
    try:
        response = supabase.storage.from_(bucket).get_public_url(file_path)
        return response
    except Exception as e:
        raise Exception(f"Failed to get public URL: {str(e)}")


def delete_file(bucket: str, file_path: str):
    """Delete a file from Supabase Storage."""
    try:
        response = supabase.storage.from_(bucket).remove([file_path])
        return response
    except Exception as e:
        raise Exception(f"File deletion failed: {str(e)}")
