from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc
from database import SessionLocal
from modules.shops.models import Shop, ShopService, ShopCloseDay
from modules.shops import schemas
from typing import List, Optional, Dict, Union, Any
from datetime import date, datetime

class ShopService:
    def get_db(self):
        return SessionLocal()

    def get_shop(self, shop_id: int) -> Optional[schemas.Shop]:
        db = self.get_db()
        try:
            shop = db.query(Shop).filter(Shop.id == shop_id).first()
            if shop:
                return schemas.Shop.model_validate(shop)
            return None
        finally:
            db.close()

    def get_shop_by_slug(self, slug: str) -> Optional[schemas.Shop]:
        db = self.get_db()
        try:
            shop = db.query(Shop).filter(Shop.slug == slug).first()
            if shop:
                return schemas.Shop.model_validate(shop)
            return None
        finally:
            db.close()


    def create_shop(self, shop_create: Union[schemas.ShopCreate, Dict[str, Any]]) -> schemas.Shop:
        db = self.get_db()
        try:
            if isinstance(shop_create, dict):
                shop_data = shop_create
            else:
                shop_data = shop_create.model_dump(exclude_unset=True)
            
            shop = Shop(**shop_data)
            db.add(shop)
            db.commit()
            db.refresh(shop)
            return schemas.Shop.model_validate(shop)
        finally:
            db.close()

    def search_shops(self, query: str = None, shop_type: str = None, city: str = None, 
                     latitude: float = None, longitude: float = None, limit: int = 10) -> List[schemas.Shop]:
        db = self.get_db()
        try:
            q = db.query(Shop)
            is_postgres = db.get_bind().dialect.name == 'postgresql'
            
            if shop_type:
                q = q.filter(Shop.shop_type.ilike(f"%{shop_type}%"))
            
            if query:
                if is_postgres:
                    search_vector = func.to_tsvector('english', 
                        func.coalesce(Shop.name, '') + ' ' + 
                        func.coalesce(Shop.shop_type, '') + ' ' + 
                        func.coalesce(Shop.description, '')
                    )
                    search_query = func.plainto_tsquery('english', query)
                    q = q.filter(search_vector.op('@@')(search_query))
                    q = q.order_by(desc(func.ts_rank(search_vector, search_query)))
                else:
                    search_filter = or_(
                        Shop.name.ilike(f"%{query}%"),
                        Shop.description.ilike(f"%{query}%"),
                        Shop.address.ilike(f"%{query}%")
                    )
                    q = q.filter(search_filter)
            
            if city:
                q = q.filter(Shop.city.ilike(f"%{city}%"))
            
            if latitude is not None and longitude is not None:
                distance = func.sqrt(
                    func.pow(Shop.latitude - latitude, 2) + 
                    func.pow(Shop.longitude - longitude, 2)
                ).label("distance")
                if not (query and is_postgres):
                   q = q.order_by(distance)
    
            shops = q.limit(limit).all()
            return [schemas.Shop.model_validate(s) for s in shops]
        finally:
            db.close()

    def update_shop(self, shop_id: int, shop_update: Dict) -> Optional[schemas.Shop]:
        db = self.get_db()
        try:
            shop = db.query(Shop).filter(Shop.id == shop_id).first()
            if shop:
                for key, value in shop_update.items():
                    setattr(shop, key, value)
                db.commit()
                db.refresh(shop)
                return schemas.Shop.model_validate(shop)
            return None
        finally:
            db.close()

    def get_close_days(self, shop_id: int) -> List[Dict]:
        db = self.get_db()
        try:
            days = db.query(ShopCloseDay).filter(
                ShopCloseDay.shop_id == shop_id,
                ShopCloseDay.date >= date.today()
            ).order_by(ShopCloseDay.date).all()
            # Return simple dict or schema? Router expects dict/schema.
            # We don't have schema for CloseDay yet in modules.shops.schemas? 
            # I defined DictModel. Let's return dict for now or add schema.
            return [{"id": d.id, "date": d.date, "reason": d.reason} for d in days]
        finally:
            db.close()

    def add_close_day(self, shop_id: int, date_val: date, reason: str = None) -> Dict:
        db = self.get_db()
        try:
            # Check existing
            existing = db.query(ShopCloseDay).filter(
                ShopCloseDay.shop_id == shop_id,
                ShopCloseDay.date == date_val
            ).first()
            
            if existing:
                return {"id": existing.id, "date": existing.date, "reason": existing.reason}
                
            new_day = ShopCloseDay(
                shop_id=shop_id,
                date=date_val,
                reason=reason
            )
            db.add(new_day)
            db.commit()
            db.refresh(new_day)
            return {"id": new_day.id, "date": new_day.date, "reason": new_day.reason}
        finally:
            db.close()

    def delete_close_day(self, shop_id: int, day_id: int):
        db = self.get_db()
        try:
            day = db.query(ShopCloseDay).filter(
                ShopCloseDay.id == day_id,
                ShopCloseDay.shop_id == shop_id
            ).first()
            if day:
                db.delete(day)
                db.commit()
        finally:
            db.close()


shop_service = ShopService()
