"""
Database abstraction layer that supports both SQLAlchemy (local PostgreSQL) and Supabase
Toggle between them using USE_SUPABASE environment variable
"""
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

# Determine which database to use
USE_SUPABASE = os.getenv("USE_SUPABASE", "false").lower() == "true"

if USE_SUPABASE:
    # Supabase mode
    from supabase_client import supabase
    db_client = None
else:
    # SQLAlchemy mode
    from database import SessionLocal, engine
    from models import Base, User, Shop, Queue, QueueItem, ShopEmployee, EmployeeShift, DailyAnalytics
    import models
    supabase = None


class DatabaseInterface:
    """
    Unified interface for database operations
    Works with both SQLAlchemy (local PostgreSQL) and Supabase
    """
    
    def __init__(self):
        self.use_supabase = USE_SUPABASE
        self.db = None
    
    def get_session(self):
        """Get database session (SQLAlchemy only)"""
        if not self.use_supabase:
            return SessionLocal()
        return None
    
    def close_session(self):
        """Close database session (SQLAlchemy only)"""
        if self.db:
            self.db.close()
            self.db = None
    
    # User operations
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        if self.use_supabase:
            response = supabase.table("users").select("*").eq("email", email).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                user = db.query(User).filter(User.email == email).first()
                return self._model_to_dict(user) if user else None
            finally:
                db.close()
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        if self.use_supabase:
            response = supabase.table("users").select("*").eq("username", username).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                user = db.query(User).filter(User.username == username).first()
                return self._model_to_dict(user) if user else None
            finally:
                db.close()
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        if self.use_supabase:
            response = supabase.table("users").select("*").eq("id", user_id).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                return self._model_to_dict(user) if user else None
            finally:
                db.close()
    
    def create_user(self, user_data: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("users").insert(user_data).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                user = User(**user_data)
                db.add(user)
                db.commit()
                db.refresh(user)
                return self._model_to_dict(user)
            finally:
                db.close()
    
    # Shop operations
    def get_shop_by_id(self, shop_id: int) -> Optional[Dict]:
        if self.use_supabase:
            response = supabase.table("shops").select("*").eq("id", shop_id).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                shop = db.query(Shop).filter(Shop.id == shop_id).first()
                return self._model_to_dict(shop) if shop else None
            finally:
                db.close()
    
    def get_shop_by_slug(self, slug: str) -> Optional[Dict]:
        if self.use_supabase:
            response = supabase.table("shops").select("*").eq("slug", slug).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                shop = db.query(Shop).filter(Shop.slug == slug).first()
                return self._model_to_dict(shop) if shop else None
            finally:
                db.close()
    
    def get_shops(self, filters: Dict = None, skip: int = 0, limit: int = 100) -> List[Dict]:
        if self.use_supabase:
            query = supabase.table("shops").select("*")
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            response = query.range(skip, skip + limit - 1).execute()
            return response.data if response.data else []
        else:
            db = self.get_session()
            try:
                query = db.query(Shop)
                if filters:
                    for key, value in filters.items():
                        query = query.filter(getattr(Shop, key) == value)
                shops = query.offset(skip).limit(limit).all()
                return [self._model_to_dict(shop) for shop in shops]
            finally:
                db.close()
    
    def create_shop(self, shop_data: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("shops").insert(shop_data).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                shop = Shop(**shop_data)
                db.add(shop)
                db.commit()
                db.refresh(shop)
                return self._model_to_dict(shop)
            finally:
                db.close()
    
    def update_shop(self, shop_id: int, shop_data: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("shops").update(shop_data).eq("id", shop_id).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                shop = db.query(Shop).filter(Shop.id == shop_id).first()
                if shop:
                    for key, value in shop_data.items():
                        setattr(shop, key, value)
                    db.commit()
                    db.refresh(shop)
                    return self._model_to_dict(shop)
                return None
            finally:
                db.close()
    
    # Queue operations
    def get_queue_by_id(self, queue_id: int) -> Optional[Dict]:
        if self.use_supabase:
            response = supabase.table("queues").select("*").eq("id", queue_id).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                queue = db.query(Queue).filter(Queue.id == queue_id).first()
                return self._model_to_dict(queue) if queue else None
            finally:
                db.close()
    
    def get_queues(self, filters: Dict = None) -> List[Dict]:
        if self.use_supabase:
            query = supabase.table("queues").select("*")
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            response = query.execute()
            return response.data if response.data else []
        else:
            db = self.get_session()
            try:
                query = db.query(Queue)
                if filters:
                    for key, value in filters.items():
                        query = query.filter(getattr(Queue, key) == value)
                queues = query.all()
                return [self._model_to_dict(queue) for queue in queues]
            finally:
                db.close()
    
    def create_queue(self, queue_data: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("queues").insert(queue_data).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                queue = Queue(**queue_data)
                db.add(queue)
                db.commit()
                db.refresh(queue)
                return self._model_to_dict(queue)
            finally:
                db.close()
    
    # Queue Item operations
    def get_queue_items(self, filters: Dict = None) -> List[Dict]:
        if self.use_supabase:
            query = supabase.table("queue_items").select("*")
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            response = query.execute()
            return response.data if response.data else []
        else:
            db = self.get_session()
            try:
                query = db.query(QueueItem)
                if filters:
                    for key, value in filters.items():
                        query = query.filter(getattr(QueueItem, key) == value)
                items = query.order_by(QueueItem.position).all()
                return [self._model_to_dict(item) for item in items]
            finally:
                db.close()
    
    def create_queue_item(self, item_data: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("queue_items").insert(item_data).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                item = QueueItem(**item_data)
                db.add(item)
                db.commit()
                db.refresh(item)
                return self._model_to_dict(item)
            finally:
                db.close()
    
    def update_queue_item(self, item_id: int, item_data: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("queue_items").update(item_data).eq("id", item_id).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
                if item:
                    for key, value in item_data.items():
                        setattr(item, key, value)
                    db.commit()
                    db.refresh(item)
                    return self._model_to_dict(item)
                return None
            finally:
                db.close()
    
    # Employee operations
    def get_shop_employees(self, shop_id: int, is_active: bool = True) -> List[Dict]:
        if self.use_supabase:
            response = supabase.table("shop_employees").select("*, user:users(*)").eq("shop_id", shop_id).eq("is_active", is_active).execute()
            return response.data if response.data else []
        else:
            db = self.get_session()
            try:
                employees = db.query(ShopEmployee).filter(
                    ShopEmployee.shop_id == shop_id,
                    ShopEmployee.is_active == is_active
                ).all()
                result = []
                for emp in employees:
                    emp_dict = self._model_to_dict(emp)
                    emp_dict['user'] = self._model_to_dict(emp.user)
                    result.append(emp_dict)
                return result
            finally:
                db.close()
    
    def create_shop_employee(self, employee_data: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("shop_employees").insert(employee_data).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                employee = ShopEmployee(**employee_data)
                db.add(employee)
                db.commit()
                db.refresh(employee)
                return self._model_to_dict(employee)
            finally:
                db.close()
    
    # Helper method to convert SQLAlchemy model to dict
    def _model_to_dict(self, model) -> Dict:
        if model is None:
            return None
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


# Singleton instance
db_interface = DatabaseInterface()


# Dependency for FastAPI
def get_db_interface():
    """Dependency to get database interface instance"""
    return db_interface
