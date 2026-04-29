"""
Shop table operations.
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



class ShopsMixin:
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
    
