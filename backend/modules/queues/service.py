from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal
from modules.queues.models import Queue, QueueItem
from modules.queues import schemas
from modules.shops.models import ShopService, ShopOperatingHours
from typing import List, Optional, Dict
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

class QueueService:
    def get_db(self):
        return SessionLocal()

    def _current_shop_local_date(self, db: Session, shop_id: int):
        hours = db.query(ShopOperatingHours).filter(ShopOperatingHours.shop_id == shop_id).first()
        timezone_name = hours.timezone if hours and hours.timezone else "UTC"
        try:
            tz = ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, Exception):
            tz = ZoneInfo("UTC")
        return datetime.now(tz).date()

    def _normalize_active_queues(self, db: Session, shop_id: int) -> List[Queue]:
        queues = db.query(Queue).filter(Queue.shop_id == shop_id, Queue.is_active == True).all()
        if not queues:
            return []

        current_local_date = self._current_shop_local_date(db, shop_id)
        current_queues: List[Queue] = []
        stale_queues: List[Queue] = []

        for queue in queues:
            queue_date = queue.date.date() if queue.date else current_local_date
            if queue_date == current_local_date:
                current_queues.append(queue)
            else:
                stale_queues.append(queue)

        if stale_queues:
            for queue in stale_queues:
                queue.is_active = False
                queue.accepting_joins = False
                if not queue.lock_reason:
                    queue.lock_reason = "Auto-closed stale queue from a previous business day"
            db.commit()

        current_queues.sort(key=lambda queue: (queue.date or datetime.min, queue.id), reverse=True)
        return current_queues

    def get_queue(self, queue_id: int) -> Optional[schemas.Queue]:
        db = self.get_db()
        try:
            queue = db.query(Queue).filter(Queue.id == queue_id).first()
            if queue:
                return schemas.Queue.model_validate(queue)
            return None
        finally:
            db.close()

    def create_queue_item(self, item_create: schemas.QueueItemCreate, queue_id: int, user_id: Optional[int] = None) -> schemas.QueueItem:
        db = self.get_db()
        try:
            # Lock queue
            queue = db.query(Queue).filter(Queue.id == queue_id).with_for_update().first()
            if not queue:
                raise ValueError("Queue not found")
                
            max_pos = db.query(func.max(QueueItem.position)).filter(QueueItem.queue_id == queue_id).scalar()
            new_pos = (max_pos or 0) + 1
            
            item_data = item_create.model_dump(exclude_unset=True)

            # Auto-populate service_cost from the linked service
            service_id = item_data.get("service_id")
            if service_id and not item_data.get("service_cost"):
                svc = db.query(ShopService).filter(ShopService.id == service_id).first()
                if svc and svc.cost:
                    item_data["service_cost"] = svc.cost

            item = QueueItem(
                **item_data,
                queue_id=queue_id,
                user_id=user_id,
                position=new_pos
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            return schemas.QueueItem.model_validate(item)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_queue_items(self, queue_id: int) -> List[schemas.QueueItem]:
        db = self.get_db()
        try:
            items = db.query(QueueItem).filter(QueueItem.queue_id == queue_id).order_by(QueueItem.position).all()
            return [schemas.QueueItem.model_validate(i) for i in items]
        finally:
            db.close()

    def get_queue_item(self, item_id: int) -> Optional[schemas.QueueItem]:
        db = self.get_db()
        try:
            item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
            if item:
                return schemas.QueueItem.model_validate(item)
            return None
        finally:
            db.close()

    def get_queue_item_by_token(self, status_token: str) -> Optional[schemas.QueueItem]:
        db = self.get_db()
        try:
            item = db.query(QueueItem).filter(QueueItem.status_token == status_token).first()
            if item:
                return schemas.QueueItem.model_validate(item)
            return None
        finally:
            db.close()

    def update_queue_item(self, item_id: int, updates: Dict) -> Optional[schemas.QueueItem]:
        db = self.get_db()
        try:
            item = db.query(QueueItem).filter(QueueItem.id == item_id).first()
            if item:
                for key, value in updates.items():
                    setattr(item, key, value)
                db.commit()
                db.refresh(item)
                return schemas.QueueItem.model_validate(item)
            return None
        finally:
            db.close()

    def create_queue(self, queue_create: schemas.QueueCreate, shop_id: int) -> schemas.Queue:
        db = self.get_db()
        try:
            queue_data = queue_create.model_dump(exclude_unset=True)
            queue = Queue(**queue_data, shop_id=shop_id)
            db.add(queue)
            db.commit()
            db.refresh(queue)
            return schemas.Queue.model_validate(queue)
        finally:
            db.close()

    def get_active_queues(self, shop_id: int) -> List[schemas.Queue]:
        db = self.get_db()
        try:
            queues = self._normalize_active_queues(db, shop_id)
            return [schemas.Queue.model_validate(q) for q in queues]
        finally:
            db.close()

    def get_all_queues(self, shop_id: int) -> List[schemas.Queue]:
        db = self.get_db()
        try:
            queues = db.query(Queue).filter(Queue.shop_id == shop_id).all()
            return [schemas.Queue.model_validate(q) for q in queues]
        finally:
            db.close()


queue_service = QueueService()
