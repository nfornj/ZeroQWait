"""Database sub-package — exposes the db_interface singleton."""
from db.interface import DatabaseInterface, db_interface, get_db_interface

__all__ = ["DatabaseInterface", "db_interface", "get_db_interface"]
