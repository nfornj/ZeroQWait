"""
Database abstraction layer - Pure SQLAlchemy/PostgreSQL version.
This interface strictly uses the SQLAlchemy session defined in 'database.py'.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import or_, func, desc

# Import the single source of truth for database connections
from database import SessionLocal
from models import (
    User, Shop, Queue, QueueItem, ShopEmployee, EmployeeShift, 
    ShopService, ShopCustomer, ConversationHistory, CategoryAlias, 
    LearnedSynonym, AgentKnowledge
)
import schemas

class DatabaseInterface:
    """
    Unified interface for database operations using only SQLAlchemy.
    """
    
    def get_session(self):
        """Get a new database session from the connection pool."""
        return SessionLocal()
    
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

    # --- Shop operations ---
    def get_shop_by_id(self, shop_id: int) -> Optional[Dict]:
        db = self.get_session()
        try:
            shop = db.query(Shop).filter(Shop.id == shop_id).first()
            return self._model_to_dict(shop, schemas.Shop) if shop else None
        finally:
            db.close()
    
    def get_shop_by_slug(self, slug: str) -> Optional[Dict]:
        db = self.get_session()
        try:
            shop = db.query(Shop).filter(Shop.slug == slug).first()
            return self._model_to_dict(shop, schemas.Shop) if shop else None
        finally:
            db.close()
    
    def search_shops(self, query: str = None, shop_type: str = None, city: str = None, latitude: float = None, longitude: float = None, limit: int = 10) -> List[Dict]:
        """Fuzzy search for shops by name, type, and city using Postgres FTS if available."""
        db = self.get_session()
        try:
            q = db.query(Shop)
            
            # Check dialect
            is_postgres = db.get_bind().dialect.name == 'postgresql'
            
            # Priority 1: Exact category filter
            if shop_type:
                q = q.filter(Shop.shop_type.ilike(f"%{shop_type}%"))
            
            # Priority 2: Text search
            if query:
                if is_postgres:
                    # Postgres Full Text Search
                    # Combine fields into a document
                    # Using coalesce to handle NULLs
                    search_vector = func.to_tsvector('english', 
                        func.coalesce(Shop.name, '') + ' ' + 
                        func.coalesce(Shop.shop_type, '') + ' ' + 
                        func.coalesce(Shop.description, '')
                    )
                    search_query = func.plainto_tsquery('english', query)
                    q = q.filter(search_vector.op('@@')(search_query))
                    
                    # Optional: Order by rank
                    q = q.order_by(desc(func.ts_rank(search_vector, search_query)))
                else:
                    # Fallback to ILIKE (SQLite)
                    if shop_type:
                        search_filter = or_(
                            Shop.name.ilike(f"%{query}%"),
                            Shop.description.ilike(f"%{query}%"),
                            Shop.address.ilike(f"%{query}%")
                        )
                    else:
                        search_filter = or_(
                            Shop.name.ilike(f"%{query}%"),
                            Shop.shop_type.ilike(f"%{query}%"),
                            Shop.description.ilike(f"%{query}%"),
                            Shop.address.ilike(f"%{query}%")
                        )
                    q = q.filter(search_filter)
            
            # City filter
            if city:
                q = q.filter(Shop.city.ilike(f"%{city}%"))
            
            # Location-based sorting (if not ranked by FTS or if FTS absent)
            if latitude is not None and longitude is not None:
                distance = func.sqrt(
                    func.pow(Shop.latitude - latitude, 2) + 
                    func.pow(Shop.longitude - longitude, 2)
                ).label("distance")
                # If we already ordered by rank (Postgres), we might want to keep that primary
                # or mix them. For now, let's append distance sort or just sort by distance if no query
                if not (query and is_postgres):
                   q = q.order_by(distance)
            
            shops = q.limit(limit).all()
            return [self._model_to_dict(shop, schemas.Shop) for shop in shops]
        finally:
            db.close()

    def get_shops(self, filters: Dict = None, skip: int = 0, limit: int = 100) -> List[Dict]:
        db = self.get_session()
        try:
            query = db.query(Shop)
            if filters:
                for key, value in filters.items():
                    query = query.filter(getattr(Shop, key) == value)
            shops = query.offset(skip).limit(limit).all()
            return [self._model_to_dict(shop, schemas.Shop) for shop in shops]
        finally:
            db.close()
    
    def create_shop(self, shop_data: Dict) -> Dict:
        db = self.get_session()
        try:
            shop = Shop(**shop_data)
            db.add(shop)
            db.commit()
            db.refresh(shop)
            return self._model_to_dict(shop, schemas.Shop)
        finally:
            db.close()
    
    def update_shop(self, shop_id: int, shop_data: Dict) -> Dict:
        db = self.get_session()
        try:
            shop = db.query(Shop).filter(Shop.id == shop_id).first()
            if shop:
                for key, value in shop_data.items():
                    setattr(shop, key, value)
                db.commit()
                db.refresh(shop)
                return self._model_to_dict(shop, schemas.Shop)
            return None
        finally:
            db.close()
    
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
    
    # --- Employee operations ---
    def get_shop_employees(self, shop_id: int, is_active: Optional[bool] = True) -> List[Dict]:
        db = self.get_session()
        try:
            query = db.query(ShopEmployee).filter(ShopEmployee.shop_id == shop_id)
            if is_active is not None:
                query = query.filter(ShopEmployee.is_active == is_active)
            employees = query.all()
            result = []
            for emp in employees:
                emp_dict = self._model_to_dict(emp)
                if emp.user:
                    emp_dict['user'] = self._model_to_dict(emp.user)
                result.append(emp_dict)
            return result
        finally:
            db.close()
    
    def create_shop_employee(self, employee_data: Dict) -> Dict:
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

    # --- Shop Service operations ---
    def create_shop_service(self, service_data: Dict) -> Dict:
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
        db = self.get_session()
        try:
            service = db.query(ShopService).filter(ShopService.id == service_id).first()
            return self._model_to_dict(service) if service else None
        finally:
            db.close()

    def get_employee_shops(self, user_id: int) -> List[int]:
        db = self.get_session()
        try:
            employees = db.query(ShopEmployee).filter(
                ShopEmployee.user_id == user_id,
                ShopEmployee.is_active == True
            ).all()
            return [emp.shop_id for emp in employees]
        finally:
            db.close()

    # --- Shift operations ---
    def create_employee_shift(self, shift_data: Dict) -> Dict:
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

    def get_conversation_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        db = self.get_session()
        try:
            history = db.query(ConversationHistory)\
                .filter(ConversationHistory.session_id == session_id)\
                .order_by(ConversationHistory.created_at.asc())\
                .limit(limit)\
                .all()
            return [self._model_to_dict(msg) for msg in history]
        finally:
            db.close()

    def add_message_to_history(self, session_id: str, role: str, content: str, tool_call_id: str = None) -> Dict:
        db = self.get_session()
        try:
            msg = ConversationHistory(
                session_id=session_id,
                role=role,
                content=content,
                tool_call_id=tool_call_id,
                created_at=datetime.utcnow()
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)
            return self._model_to_dict(msg)
        finally:
            db.close()

    def get_active_shift(self, user_id: int) -> Optional[Dict]:
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
        db = self.get_session()
        try:
            query = db.query(EmployeeShift).filter(
                EmployeeShift.shop_id == shop_id,
                EmployeeShift.clock_in >= start_date,
                EmployeeShift.clock_in <= end_date
            )
            if user_id:
                query = query.filter(EmployeeShift.user_id == user_id)
            
            shifts = query.order_by(desc(EmployeeShift.clock_in)).all()
            return [self._model_to_dict(shift) for shift in shifts]
        finally:
            db.close()
    
    # --- Shop Customer Context (CRM) ---
    def get_shop_customer_by_phone(self, shop_id: int, phone: str) -> Optional[Dict]:
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
        phone = customer_data.get("phone")
        if not phone:
            return None
            
        existing = self.get_shop_customer_by_phone(shop_id, phone)
        
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

    # --- Agent / Category Support ---
    def get_all_shops(self) -> List[Dict]:
        return self.get_shops(limit=1000)

    def get_category_aliases(self) -> List[Dict]:
        db = self.get_session()
        try:
            aliases = db.query(CategoryAlias).all()
            return [self._model_to_dict(a) for a in aliases]
        except Exception as e:
            print(f"Error fetching aliases: {e}")
            return []
        finally:
            db.close()

    def add_category(self, category_key: str, display_name: str, aliases: List[str]):
        db = self.get_session()
        try:
            for alias in aliases:
                exists = db.query(CategoryAlias).filter(
                    CategoryAlias.category_key == category_key,
                    CategoryAlias.alias == alias
                ).first()
                
                if not exists:
                    obj = CategoryAlias(category_key=category_key, alias=alias)
                    db.add(obj)
            db.commit()
        except Exception as e:
            print(f"Error adding category: {e}")
        finally:
            db.close()

    def get_agent_knowledge(self, key: str) -> Optional[Dict]:
        db = self.get_session()
        try:
            item = db.query(AgentKnowledge).filter(AgentKnowledge.key == key).first()
            return self._model_to_dict(item) if item else None
        except Exception:
            return None
        finally:
            db.close()

    def get_all_agent_knowledge(self) -> List[Dict]:
        db = self.get_session()
        try:
            items = db.query(AgentKnowledge).all()
            return [self._model_to_dict(item) for item in items]
        except Exception:
            return []
        finally:
            db.close()

    def upsert_agent_knowledge(self, key: str, content: str, description: str = None) -> Dict:
        db = self.get_session()
        try:
            item = db.query(AgentKnowledge).filter(AgentKnowledge.key == key).first()
            if item:
                item.content = content
                if description:
                    item.description = description
                item.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(item)
            else:
                item = AgentKnowledge(
                    key=key,
                    content=content,
                    description=description
                )
                db.add(item)
                db.commit()
                db.refresh(item)
            return self._model_to_dict(item)
        finally:
            db.close()

    def get_learned_synonyms(self) -> List[Dict]:
        db = self.get_session()
        try:
            synonyms = db.query(LearnedSynonym).all()
            return [self._model_to_dict(s) for s in synonyms]
        except Exception:
            return []
        finally:
            db.close()

    def add_learned_synonym(self, query_term: str, category: str, full_query: str = None, timestamp: str = None):
        db = self.get_session()
        try:
            exists = db.query(LearnedSynonym).filter(
                LearnedSynonym.query_term == query_term,
                LearnedSynonym.category == category
            ).first()
            
            if not exists:
                created_at_val = datetime.utcnow()
                if isinstance(timestamp, str):
                    try:
                        created_at_val = datetime.fromisoformat(timestamp)
                    except:
                        pass
                        
                obj = LearnedSynonym(
                    query_term=query_term,
                    category=category,
                    full_query=full_query,
                    created_at=created_at_val
                )
                db.add(obj)
                db.commit()
        finally:
            db.close()

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

# Singleton instance
db_interface = DatabaseInterface()

def get_db_interface():
    """Dependency to get database interface instance"""
    return db_interface