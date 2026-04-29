"""
Queue and queue-item operations.
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



class QueuesMixin:
    # --- Queue operations ---
    def get_queue_by_id(self, queue_id: int) -> Optional[Dict]:
        db = self.get_session()
        try:
            queue = db.query(Queue).filter(Queue.id == queue_id).first()
            return self._model_to_dict(queue) if queue else None
        finally:
            db.close()
    
    def get_queues(self, filters: Dict = None) -> List[Dict]:
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
        db = self.get_session()
        try:
            queue = Queue(**queue_data)
            db.add(queue)
            db.commit()
            db.refresh(queue)
            return self._model_to_dict(queue)
        finally:
            db.close()
    
    # --- Queue Item operations ---
    def get_queue_items(self, filters: Dict = None) -> List[Dict]:
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
        db = self.get_session()
        try:
            # Atomic transaction with row locking on the parent Queue
            # This ensures no two requests get the same position simultaneously
            queue_id = item_data.get("queue_id")
            
            # Lock the queue row to serialize inserts for this queue
            queue = db.query(Queue).filter(Queue.id == queue_id).with_for_update().first()
            if not queue:
                raise ValueError("Queue not found")
                
            # Calculate next position
            max_pos = db.query(func.max(QueueItem.position)).filter(QueueItem.queue_id == queue_id).scalar()
            new_pos = (max_pos or 0) + 1
            
            item_data["position"] = new_pos
            item = QueueItem(**item_data)
            db.add(item)
            db.commit()
            db.refresh(item)
            return self._model_to_dict(item)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    
    def update_queue_item(self, item_id: int, item_data: Dict) -> Dict:
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
    
