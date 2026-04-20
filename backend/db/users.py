"""
User table operations.
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



class UsersMixin:
    # --- User operations ---
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        db = self.get_session()
        try:
            user = db.query(User).filter(User.email == email).first()
            return self._model_to_dict(user, schemas.User) if user else None
        finally:
            db.close()
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        db = self.get_session()
        try:
            user = db.query(User).filter(User.username == username).first()
            return self._model_to_dict(user, schemas.User) if user else None
        finally:
            db.close()
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        db = self.get_session()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            return self._model_to_dict(user, schemas.User) if user else None
        finally:
            db.close()
    
    def create_user(self, user_data: Dict) -> Dict:
        db = self.get_session()
        try:
            user = User(**user_data)
            db.add(user)
            db.commit()
            db.refresh(user)
            return self._model_to_dict(user, schemas.User)
        finally:
            db.close()

    def update_user(self, user_id: int, user_data: Dict) -> Dict:
        db = self.get_session()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                for key, value in user_data.items():
                    setattr(user, key, value)
                db.commit()
                db.refresh(user)
                return self._model_to_dict(user, schemas.User)
            return None
        finally:
            db.close()

    def check_username_exists(self, username: str) -> bool:
        db = self.get_session()
        try:
            user = db.query(User).filter(User.username == username).first()
            return user is not None
        finally:
            db.close()

    def check_email_exists(self, email: str) -> bool:
        db = self.get_session()
        try:
            user = db.query(User).filter(User.email == email).first()
            return user is not None
        finally:
            db.close()

