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
    from models import Base, User, Shop, Queue, QueueItem, ShopEmployee, EmployeeShift, DailyAnalytics, ShopService, ShopCustomer
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
    def update_user(self, user_id: int, user_data: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("users").update(user_data).eq("id", user_id).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    for key, value in user_data.items():
                        setattr(user, key, value)
                    db.commit()
                    db.refresh(user)
                    return self._model_to_dict(user)
                return None
            finally:
                db.close()

    def check_username_exists(self, username: str) -> bool:
        if self.use_supabase:
            response = supabase.table("users").select("id").eq("username", username).execute()
            return len(response.data) > 0
        else:
            db = self.get_session()
            try:
                user = db.query(User).filter(User.username == username).first()
                return user is not None
            finally:
                db.close()

    def check_email_exists(self, email: str) -> bool:
        if self.use_supabase:
            response = supabase.table("users").select("id").eq("email", email).execute()
            return len(response.data) > 0
        else:
            db = self.get_session()
            try:
                user = db.query(User).filter(User.email == email).first()
                return user is not None
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
    
    def search_shops(self, query: str = None, shop_type: str = None, city: str = None, limit: int = 10) -> List[Dict]:
        """Fuzzy search for shops by name, type, and city."""
        if self.use_supabase:
            builder = supabase.table("shops").select("*")
            if query:
                builder = builder.ilike("name", f"%{query}%")
            if shop_type:
                builder = builder.ilike("shop_type", f"%{shop_type}%")
            if city:
                builder = builder.ilike("city", f"%{city}%")
            response = builder.limit(limit).execute()
            return response.data if response.data else []
        else:
            db = self.get_session()
            try:
                from sqlalchemy import or_
                q = db.query(Shop)
                if query:
                    search_filter = or_(
                        Shop.name.ilike(f"%{query}%"),
                        Shop.shop_type.ilike(f"%{query}%"),
                        Shop.description.ilike(f"%{query}%")
                    )
                    q = q.filter(search_filter)
                
                # Apply explicit filters if provided
                if shop_type:
                    q = q.filter(Shop.shop_type.ilike(f"%{shop_type}%"))
                if city:
                    q = q.filter(Shop.city.ilike(f"%{city}%"))
                
                shops = q.limit(limit).all()
                return [self._model_to_dict(shop) for shop in shops]
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
    def get_shop_employees(self, shop_id: int, is_active: Optional[bool] = True) -> List[Dict]:
        if self.use_supabase:
            query = supabase.table("shop_employees").select("*, user:users(*)").eq("shop_id", shop_id)
            if is_active is not None:
                query = query.eq("is_active", is_active)
            response = query.execute()
            return response.data if response.data else []
        else:
            db = self.get_session()
            try:
                query = db.query(ShopEmployee).filter(ShopEmployee.shop_id == shop_id)
                if is_active is not None:
                    query = query.filter(ShopEmployee.is_active == is_active)
                employees = query.all()
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

    def get_shop_employee(self, shop_id: int, user_id: int) -> Optional[Dict]:
        if self.use_supabase:
            response = supabase.table("shop_employees").select("*").eq("shop_id", shop_id).eq("user_id", user_id).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                employee = db.query(ShopEmployee).filter(
                    ShopEmployee.shop_id == shop_id,
                    ShopEmployee.user_id == user_id
                ).first()
                return self._model_to_dict(employee) if employee else None
            finally:
                db.close()

    def update_shop_employee(self, shop_id: int, user_id: int, updates: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("shop_employees").update(updates).eq("shop_id", shop_id).eq("user_id", user_id).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                employee = db.query(ShopEmployee).filter(
                    ShopEmployee.shop_id == shop_id,
                    ShopEmployee.user_id == user_id
                ).first()
                if employee:
                    for key, value in updates.items():
                        setattr(employee, key, value)
                    db.commit()
                    db.refresh(employee)
                    return self._model_to_dict(employee)
                return None
            finally:
                db.close()

    # Shop Service operations
    def create_shop_service(self, service_data: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("shop_services").insert(service_data).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                service = ShopService(**service_data)
                db.add(service)
                db.commit()
                db.refresh(service)
                return self._model_to_dict(service)
            finally:
                db.close()

    def get_shop_services(self, shop_id: int, include_inactive: bool = False) -> List[Dict]:
        if self.use_supabase:
            query = supabase.table("shop_services").select("*").eq("shop_id", shop_id)
            if not include_inactive:
                query = query.eq("is_active", True)
            response = query.execute()
            return response.data if response.data else []
        else:
            db = self.get_session()
            try:
                query = db.query(ShopService).filter(ShopService.shop_id == shop_id)
                if not include_inactive:
                    query = query.filter(ShopService.is_active == True)
                services = query.all()
                return [self._model_to_dict(s) for s in services]
            finally:
                db.close()

    def update_shop_service(self, shop_id: int, service_id: int, updates: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("shop_services").update(updates).eq("id", service_id).eq("shop_id", shop_id).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                service = db.query(ShopService).filter(
                    ShopService.id == service_id,
                    ShopService.shop_id == shop_id
                ).first()
                if service:
                    for key, value in updates.items():
                        setattr(service, key, value)
                    db.commit()
                    db.refresh(service)
                    return self._model_to_dict(service)
                return None
            finally:
                db.close()

    def get_shop_service_by_id(self, service_id: int) -> Optional[Dict]:
        if self.use_supabase:
            response = supabase.table("shop_services").select("*").eq("id", service_id).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                service = db.query(ShopService).filter(ShopService.id == service_id).first()
                return self._model_to_dict(service) if service else None
            finally:
                db.close()

    def get_employee_shops(self, user_id: int) -> List[int]:
        if self.use_supabase:
            response = supabase.table("shop_employees").select("shop_id").eq("user_id", user_id).eq("is_active", True).execute()
            return [item["shop_id"] for item in response.data] if response.data else []
        else:
            db = self.get_session()
            try:
                employees = db.query(ShopEmployee).filter(
                    ShopEmployee.user_id == user_id,
                    ShopEmployee.is_active == True
                ).all()
                return [emp.shop_id for emp in employees]
            finally:
                db.close()

    # Shift operations
    def create_employee_shift(self, shift_data: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("employee_shifts").insert(shift_data).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                shift = EmployeeShift(**shift_data)
                db.add(shift)
                db.commit()
                db.refresh(shift)
                return self._model_to_dict(shift)
            finally:
                db.close()

    def update_employee_shift(self, shift_id: int, updates: Dict) -> Dict:
        if self.use_supabase:
            response = supabase.table("employee_shifts").update(updates).eq("id", shift_id).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                shift = db.query(EmployeeShift).filter(EmployeeShift.id == shift_id).first()
                if shift:
                    for key, value in updates.items():
                        setattr(shift, key, value)
                    db.commit()
                    db.refresh(shift)
                    return self._model_to_dict(shift)
                return None
            finally:
                db.close()

    def get_active_shift(self, user_id: int) -> Optional[Dict]:
        if self.use_supabase:
            response = supabase.table("employee_shifts").select("*").eq("user_id", user_id).is_("clock_out", "null").execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                shift = db.query(EmployeeShift).filter(
                    EmployeeShift.user_id == user_id,
                    EmployeeShift.clock_out == None
                ).first()
                return self._model_to_dict(shift) if shift else None
            finally:
                db.close()

    def get_shop_active_shifts(self, shop_id: int) -> List[Dict]:
        if self.use_supabase:
            response = supabase.table("employee_shifts").select("*").eq("shop_id", shop_id).is_("clock_out", "null").execute()
            return response.data if response.data else []
        else:
            db = self.get_session()
            try:
                shifts = db.query(EmployeeShift).filter(
                    EmployeeShift.shop_id == shop_id,
                    EmployeeShift.clock_out == None
                ).all()
                return [self._model_to_dict(shift) for shift in shifts]
            finally:
                db.close()

    def get_employee_shifts(self, shop_id: int, start_date: datetime, end_date: datetime, user_id: Optional[int] = None) -> List[Dict]:
        if self.use_supabase:
            query = supabase.table("employee_shifts").select("*").eq("shop_id", shop_id)
            query = query.gte("clock_in", start_date.isoformat())
            query = query.lte("clock_in", end_date.isoformat())
            if user_id:
                query = query.eq("user_id", user_id)
            query = query.order("clock_in", desc=True)
            response = query.execute()
            return response.data if response.data else []
        else:
            db = self.get_session()
            try:
                query = db.query(EmployeeShift).filter(
                    EmployeeShift.shop_id == shop_id,
                    EmployeeShift.clock_in >= start_date,
                    EmployeeShift.clock_in <= end_date
                )
                if user_id:
                    query = query.filter(EmployeeShift.user_id == user_id)
                
                shifts = query.order_by(EmployeeShift.clock_in.desc()).all()
                return [self._model_to_dict(shift) for shift in shifts]
            finally:
                db.close()
    
    # Shop Customer Context (CRM)
    def get_shop_customer_by_phone(self, shop_id: int, phone: str) -> Optional[Dict]:
        if self.use_supabase:
            response = supabase.table("shop_customers").select("*").eq("shop_id", shop_id).eq("phone", phone).execute()
            return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                customer = db.query(ShopCustomer).filter(
                    ShopCustomer.shop_id == shop_id,
                    ShopCustomer.phone == phone
                ).first()
                return self._model_to_dict(customer) if customer else None
            finally:
                db.close()

    def upsert_shop_customer(self, shop_id: int, customer_data: Dict) -> Dict:
        """Create or update a customer record for a specific shop."""
        phone = customer_data.get("phone")
        if not phone:
            return None
            
        existing = self.get_shop_customer_by_phone(shop_id, phone)
        
        if self.use_supabase:
            if existing:
                # Update
                updates = {
                    "visit_count": existing.get("visit_count", 0) + 1,
                    "last_visit": datetime.utcnow().isoformat(),
                    "name": customer_data.get("name", existing.get("name"))
                }
                response = supabase.table("shop_customers").update(updates).eq("id", existing["id"]).execute()
                return response.data[0] if response.data else None
            else:
                # Insert
                customer_data["shop_id"] = shop_id
                customer_data["visit_count"] = 1
                customer_data["last_visit"] = datetime.utcnow().isoformat()
                response = supabase.table("shop_customers").insert(customer_data).execute()
                return response.data[0] if response.data else None
        else:
            db = self.get_session()
            try:
                if existing:
                    customer = db.query(ShopCustomer).filter(ShopCustomer.id == existing["id"]).first()
                    customer.visit_count += 1
                    customer.last_visit = datetime.utcnow()
                    if "name" in customer_data:
                        customer.name = customer_data["name"]
                    db.commit()
                    db.refresh(customer)
                else:
                    customer = ShopCustomer(
                        shop_id=shop_id,
                        phone=phone,
                        name=customer_data.get("name"),
                        visit_count=1,
                        last_visit=datetime.utcnow()
                    )
                    db.add(customer)
                    db.commit()
                    db.refresh(customer)
                return self._model_to_dict(customer)
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


    # Analytics operations
    def get_analytics_queues(self, shop_id: int) -> List[Dict]:
        """Get all queues for a shop (active or not) for analytics"""
        if self.use_supabase:
            response = supabase.table("queues").select("id").eq("shop_id", shop_id).execute()
            return response.data if response.data else []
        else:
            db = self.get_session()
            try:
                queues = db.query(Queue).filter(Queue.shop_id == shop_id).all()
                return [{"id": q.id} for q in queues]
            finally:
                db.close()
    
    def get_analytics_items(self, queue_ids: List[int], start_date: datetime) -> List[Dict]:
        """Get completed queue items for specified queues since start_date"""
        if not queue_ids:
            return []
            
        if self.use_supabase:
            response = supabase.table("queue_items").select("*").in_(
                "queue_id", queue_ids
            ).eq("status", "completed").gte(
                "completed_at", start_date.isoformat()
            ).execute()
            return response.data if response.data else []
        else:
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


# Singleton instance
db_interface = DatabaseInterface()


# Dependency for FastAPI
def get_db_interface():
    """Dependency to get database interface instance"""
    return db_interface
