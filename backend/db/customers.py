"""
Shop customer CRM operations.
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



class CustomersMixin:
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

