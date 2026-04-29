"""
Database base: session factory and _model_to_dict helper.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import or_, func, desc

# Import the single source of truth for database connections
from database import SessionLocal
from models import (
    User, Shop, Queue, QueueItem, ShopEmployee, EmployeeShift, 
    ShopService, ShopCustomer, DailyAnalytics, ConversationHistory, CategoryAlias, 
    LearnedSynonym, AgentKnowledge, AgentMemory
)
import schemas



class DbBase:
    def get_session(self):
        """Get a new database session from the connection pool."""
        return SessionLocal()
    

    # --- Helpers ---
    def _model_to_dict(self, model, schema=None) -> Dict:
        if model is None:
            return None
        
        # If schema is provided, return Pydantic model
        # Our schemas now inherit from DictModel so they support dict-like access
        if schema:
            return schema.model_validate(model)
            
        result = {}
        for column in model.__table__.columns:
            value = getattr(model, column.name)
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            elif hasattr(value, 'value'):  # Enum
                result[column.name] = value.value
            else:
                result[column.name] = value
        return result
    
