"""
DatabaseInterface — composes all domain mixins. Singleton at bottom.
"""
from db.base import DbBase
from db.users import UsersMixin
from db.shops import ShopsMixin
from db.queues import QueuesMixin
from db.employees import EmployeesMixin
from db.customers import CustomersMixin
from db.knowledge import KnowledgeMixin
from db.analytics import AnalyticsMixin


class DatabaseInterface(
    DbBase,
    UsersMixin,
    ShopsMixin,
    QueuesMixin,
    EmployeesMixin,
    CustomersMixin,
    KnowledgeMixin,
    AnalyticsMixin,
):
    """Unified database interface — all domain operations in one object."""
    pass


# Singleton instance
db_interface = DatabaseInterface()

def get_db_interface():
    """Dependency to get database interface instance"""
    return db_interface