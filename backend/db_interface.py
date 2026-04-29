"""
db_interface.py — backward-compatible facade.

DatabaseInterface and db_interface have been moved to backend/db/.
This file re-exports them so all existing imports continue to work.
"""
from db.interface import DatabaseInterface, db_interface, get_db_interface  # noqa: F401

__all__ = ["DatabaseInterface", "db_interface", "get_db_interface"]
