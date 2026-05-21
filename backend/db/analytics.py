"""
Analytics operations and active queue/wait-time tool helpers.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import or_, func, desc
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Import the single source of truth for database connections
from database import SessionLocal
from models import (
    User, Shop, Queue, QueueItem, ShopEmployee, EmployeeShift, 
    ShopService, ShopCustomer, DailyAnalytics, ConversationHistory, CategoryAlias, 
    LearnedSynonym, AgentKnowledge, AgentMemory
)
from modules.shops.models import ShopOperatingHours
import schemas



class AnalyticsMixin:
    def _current_shop_local_date(self, db, shop_id: int):
        hours = db.query(ShopOperatingHours).filter(ShopOperatingHours.shop_id == shop_id).first()
        timezone_name = hours.timezone if hours and hours.timezone else "UTC"
        try:
            tz = ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, Exception):
            tz = ZoneInfo("UTC")
        return datetime.now(tz).date()

    def _current_active_queues(self, db, shop_id: int) -> List[Queue]:
        queues = db.query(Queue).filter(
            Queue.shop_id == shop_id,
            Queue.is_active == True,
        ).all()
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

    # --- Analytics operations ---
    def get_analytics_queues(self, shop_id: int) -> List[Dict]:
        db = self.get_session()
        try:
            queues = db.query(Queue).filter(Queue.shop_id == shop_id).all()
            return [{"id": q.id} for q in queues]
        finally:
            db.close()
    
    def get_analytics_items(self, queue_ids: List[int], start_date: datetime) -> List[Dict]:
        if not queue_ids:
            return []
        
        db = self.get_session()
        try:
            items = db.query(QueueItem).filter(
                QueueItem.queue_id.in_(queue_ids),
                QueueItem.status == "completed",
                QueueItem.completed_at >= start_date
            ).all()
            return [self._model_to_dict(item) for item in items]
        finally:
            db.close()

    # --- Agent Active Tool Helpers ---
    
    def get_shop_wait_time(self, shop_id: int) -> Dict[str, Any]:
        """Calculate estimated wait time for a shop based on queue and average service time."""
        db = self.get_session()
        try:
            shop = db.query(Shop).filter(Shop.id == shop_id).first()
            if not shop:
                return {"error": "Shop not found", "wait_minutes": None}
            
            # Get active queue for this shop
            queue = next(iter(self._current_active_queues(db, shop_id)), None)
            
            if not queue:
                return {"shop_name": shop.name, "wait_minutes": 0, "queue_length": 0}
            
            # Count waiting customers
            waiting_count = db.query(QueueItem).filter(
                QueueItem.queue_id == queue.id,
                QueueItem.status == 'waiting'
            ).count()
            
            # Calculate estimated wait
            avg_service_time = shop.average_service_time or 15  # Default 15 min
            estimated_wait = waiting_count * avg_service_time
            
            return {
                "shop_name": shop.name,
                "shop_id": shop_id,
                "wait_minutes": estimated_wait,
                "queue_length": waiting_count,
                "average_service_time": avg_service_time
            }
        finally:
            db.close()

    def get_shop_live_wait_metrics(self, shop_id: int) -> Dict[str, Any]:
        """AI-enhanced live wait metrics using staffing, parallel queues, historical analytics, and real throughput."""
        db = self.get_session()
        try:
            shop = db.query(Shop).filter(Shop.id == shop_id).first()
            if not shop:
                return {"error": "Shop not found"}

            active_queues = self._current_active_queues(db, shop_id)
            queue_ids = [q.id for q in active_queues]

            if not queue_ids:
                return {
                    "shop_id": shop_id,
                    "shop_name": shop.name,
                    "estimated_wait_minutes": 0,
                    "queue_length": 0,
                    "people_waiting": 0,
                    "people_being_served": 0,
                    "active_employees": 1,
                    "parallel_queues": 1,
                    "effective_service_time_minutes": float(shop.average_service_time or 15),
                    "efficiency_factor": 1.0,
                    "confidence": "medium",
                    "generated_at": datetime.utcnow().isoformat(),
                }

            waiting_count = db.query(QueueItem).filter(
                QueueItem.queue_id.in_(queue_ids),
                QueueItem.status == 'waiting'
            ).count()

            serving_items = db.query(QueueItem).filter(
                QueueItem.queue_id.in_(queue_ids),
                QueueItem.status == 'being_served'
            ).all()
            serving_count = len(serving_items)

            # Active staffing signals
            employees_on_shift = db.query(EmployeeShift).filter(
                EmployeeShift.shop_id == shop_id,
                EmployeeShift.clock_out == None,
            ).count()

            assigned_serving_employee_ids = {
                s.assigned_employee_id for s in serving_items if s.assigned_employee_id
            }
            employees_serving_now = len(assigned_serving_employee_ids)

            active_employee_records = db.query(ShopEmployee).filter(
                ShopEmployee.shop_id == shop_id,
                ShopEmployee.is_active == True,
            ).count()

            active_employees = max(
                1,
                employees_on_shift,
                employees_serving_now,
                min(active_employee_records, 2) if active_employee_records else 0,
            )

            parallel_queues = max(1, len(active_queues))

            # Baseline + historical + realized service time model
            baseline_service_time = float(shop.average_service_time or 15)

            analytics_avg = db.query(func.avg(DailyAnalytics.avg_service_time_minutes)).filter(
                DailyAnalytics.shop_id == shop_id,
                DailyAnalytics.avg_service_time_minutes != None,
            ).scalar()

            recent_completed = db.query(QueueItem).join(Queue, Queue.id == QueueItem.queue_id).filter(
                Queue.shop_id == shop_id,
                QueueItem.status == 'completed',
                QueueItem.service_started_at != None,
                QueueItem.completed_at != None,
            ).order_by(desc(QueueItem.completed_at)).limit(160).all()

            if recent_completed:
                durations = []
                for item in recent_completed:
                    minutes = (item.completed_at - item.service_started_at).total_seconds() / 60.0
                    if 2 <= minutes <= 180:
                        durations.append(minutes)
                realized_avg = (sum(durations) / len(durations)) if durations else None
            else:
                realized_avg = None

            weighted_parts = [baseline_service_time * 0.45]
            if analytics_avg:
                weighted_parts.append(float(analytics_avg) * 0.35)
            if realized_avg:
                weighted_parts.append(float(realized_avg) * 0.20)

            effective_service_time = sum(weighted_parts)
            effective_service_time = max(6.0, min(90.0, effective_service_time))

            # Throughput efficiency over last ~2 hours
            now = datetime.utcnow()
            completed_last_2h = db.query(QueueItem).join(Queue, Queue.id == QueueItem.queue_id).filter(
                Queue.shop_id == shop_id,
                QueueItem.status == 'completed',
                QueueItem.completed_at != None,
                QueueItem.completed_at >= now.replace(minute=0, second=0, microsecond=0),
            ).count()

            expected_per_hour = max(0.1, active_employees * (60.0 / effective_service_time))
            observed_per_hour = max(0.1, completed_last_2h / 2.0)
            efficiency_factor = observed_per_hour / expected_per_hour
            efficiency_factor = max(0.75, min(1.35, efficiency_factor))

            adjusted_service_time = effective_service_time / efficiency_factor
            service_channels = max(1.0, float(active_employees), float(parallel_queues) * 0.8)

            estimated_wait_minutes = int(round((waiting_count * adjusted_service_time) / service_channels))
            estimated_wait_minutes = max(0, estimated_wait_minutes)

            if waiting_count == 0 and serving_count == 0:
                confidence = "high"
            elif realized_avg and analytics_avg:
                confidence = "high"
            elif realized_avg or analytics_avg:
                confidence = "medium"
            else:
                confidence = "low"

            return {
                "shop_id": shop_id,
                "shop_name": shop.name,
                "estimated_wait_minutes": estimated_wait_minutes,
                "queue_length": waiting_count + serving_count,
                "people_waiting": waiting_count,
                "people_being_served": serving_count,
                "active_employees": int(active_employees),
                "parallel_queues": int(parallel_queues),
                "effective_service_time_minutes": round(adjusted_service_time, 1),
                "efficiency_factor": round(efficiency_factor, 2),
                "confidence": confidence,
                "generated_at": datetime.utcnow().isoformat(),
            }
        finally:
            db.close()
    
    def get_queue_position(self, queue_item_id: int) -> Dict[str, Any]:
        """Get a customer's current position in queue and estimated wait."""
        db = self.get_session()
        try:
            item = db.query(QueueItem).filter(QueueItem.id == queue_item_id).first()
            if not item:
                return {"error": "Queue item not found"}
            
            # Get the queue
            queue = db.query(Queue).filter(Queue.id == item.queue_id).first()
            if not queue:
                return {"error": "Queue not found"}
            
            # Get shop for service time
            shop = db.query(Shop).filter(Shop.id == queue.shop_id).first()
            avg_service_time = shop.average_service_time if shop else 15

            active_statuses = ['waiting', 'being_served', 'WAITING', 'BEING_SERVED']
            active_items = (
                db.query(QueueItem)
                .filter(
                    QueueItem.queue_id == item.queue_id,
                    QueueItem.status.in_(active_statuses),
                )
                .order_by(QueueItem.position)
                .all()
            )

            live_position = item.position
            ahead_count = 0
            if item.status in active_statuses:
                for idx, active_item in enumerate(active_items, start=1):
                    if active_item.id == item.id:
                        live_position = idx
                        ahead_count = idx - 1
                        break
            
            return {
                "queue_item_id": queue_item_id,
                "customer_name": item.customer_name,
                "status": item.status,
                "position": live_position,
                "people_ahead": ahead_count,
                "estimated_wait_minutes": ahead_count * avg_service_time,
                "shop_name": shop.name if shop else "Unknown"
            }
        finally:
            db.close()
    
    def join_queue_for_shop(self, shop_id: int, customer_name: str, phone: str = None, service_name: str = None) -> Dict[str, Any]:
        """Add a customer to a shop's active queue."""
        db = self.get_session()
        try:
            # Get shop
            shop = db.query(Shop).filter(Shop.id == shop_id).first()
            if not shop:
                return {"error": "Shop not found"}
            
            # Get active queue
            queue = db.query(Queue).filter(
                Queue.shop_id == shop_id,
                Queue.is_active == True
            ).with_for_update().first()
            
            if not queue:
                return {"error": "No active queue for this shop"}
            
            # Resolve service if provided
            service_id = None
            service_cost = 0.0
            resolved_service_name = None
            if service_name:
                # Try exact match first (case-insensitive), then fuzzy
                service = db.query(ShopService).filter(
                    ShopService.shop_id == shop_id,
                    ShopService.is_active == True,
                    func.lower(ShopService.name) == service_name.lower()
                ).first()
                if not service:
                    # Fuzzy: substring match
                    services = db.query(ShopService).filter(
                        ShopService.shop_id == shop_id,
                        ShopService.is_active == True,
                    ).all()
                    svc_lower = service_name.lower()
                    for s in services:
                        if svc_lower in (s.name or "").lower() or (s.name or "").lower() in svc_lower:
                            service = s
                            break
                if service:
                    service_id = service.id
                    service_cost = service.cost or 0.0
                    resolved_service_name = service.name

            # Calculate position
            max_pos = db.query(func.max(QueueItem.position)).filter(
                QueueItem.queue_id == queue.id
            ).scalar()
            new_pos = (max_pos or 0) + 1
            
            # Create queue item
            item = QueueItem(
                queue_id=queue.id,
                customer_name=customer_name,
                customer_phone=phone,
                position=new_pos,
                status='waiting',
                service_id=service_id,
                service_cost=service_cost,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            
            # Calculate wait time
            avg_service_time = shop.average_service_time or 15
            wait_minutes = (new_pos - 1) * avg_service_time
            
            result = {
                "success": True,
                "queue_item_id": item.id,
                "position": new_pos,
                "estimated_wait_minutes": wait_minutes,
                "shop_name": shop.name,
                "customer_name": customer_name,
                "service_cost": service_cost,
            }
            if resolved_service_name:
                result["service_name"] = resolved_service_name
            return result
        except Exception as e:
            db.rollback()
            return {"error": str(e)}
        finally:
            db.close()

