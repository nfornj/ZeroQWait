from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc
from database import SessionLocal
from modules.shops.models import (
    Shop,
    ShopBookingSettings,
    ShopBusinessHour,
    ShopCloseDay,
    ShopOperatingHours,
    ShopService,
)
from modules.shops import schemas
from typing import List, Optional, Dict, Union, Any
from datetime import date, datetime, time

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_INDEX_BY_NAME = {day.lower(): idx for idx, day in enumerate(DAYS_OF_WEEK)}
DEFAULT_BUSINESS_HOURS = [
    {
        "day": day,
        "isOpen": day != "Sunday",
        "openTime": "09:00",
        "closeTime": "18:00",
    }
    for day in DAYS_OF_WEEK
]


def _parse_time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid time value: {value}") from exc


def _format_time(value: time) -> str:
    return value.strftime("%H:%M")


def _day_index(day: str) -> int:
    idx = DAY_INDEX_BY_NAME.get(day.lower())
    if idx is None:
        raise ValueError(f"Invalid day value: {day}")
    return idx

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
        from slugify import slugify
        import random
        import string
        
        db = self.get_db()
        try:
            if isinstance(shop_create, dict):
                shop_data = shop_create
            else:
                shop_data = shop_create.model_dump(exclude_unset=True)
            
            # Generate slug if not present
            if not shop_data.get('slug'):
                base_slug = slugify(shop_data['name'])
                slug = base_slug
                # Ensure uniqueness
                counter = 1
                while db.query(Shop).filter(Shop.slug == slug).first():
                    # If long name, truncate base to avoid overflow
                    if len(base_slug) > 40:
                        base_slug = base_slug[:40]
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                shop_data['slug'] = slug

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

    def get_user_shops(self, owner_id: int) -> List[schemas.Shop]:
        db = self.get_db()
        try:
            shops = db.query(Shop).filter(Shop.owner_id == owner_id).all()
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
                if "timezone" in shop_update and shop_update.get("timezone"):
                    operating_hours = db.query(ShopOperatingHours).filter(
                        ShopOperatingHours.shop_id == shop_id
                    ).first()
                    if operating_hours:
                        operating_hours.timezone = shop_update["timezone"]
                db.commit()
                db.refresh(shop)
                return schemas.Shop.model_validate(shop)
            return None
        finally:
            db.close()

    def _close_day_to_dict(self, close_day: ShopCloseDay) -> Dict:
        close_date = close_day.date.date() if hasattr(close_day.date, "date") else close_day.date
        return {
            "id": close_day.id,
            "date": close_date,
            "name": close_day.name,
            "reason": close_day.reason,
            "notes": close_day.notes,
            "repeatYearly": bool(close_day.repeat_yearly),
        }

    def get_close_days(self, shop_id: int) -> List[Dict]:
        db = self.get_db()
        try:
            days = db.query(ShopCloseDay).filter(
                ShopCloseDay.shop_id == shop_id,
                ShopCloseDay.date >= date.today()
            ).order_by(ShopCloseDay.date).all()
            return [self._close_day_to_dict(d) for d in days]
        finally:
            db.close()

    def add_close_day(
        self,
        shop_id: int,
        date_val: date,
        reason: str = None,
        name: str = None,
        notes: str = None,
        repeat_yearly: bool = False,
    ) -> Dict:
        db = self.get_db()
        try:
            # Check existing
            existing = db.query(ShopCloseDay).filter(
                ShopCloseDay.shop_id == shop_id,
                ShopCloseDay.date == date_val
            ).first()
            
            if existing:
                existing.reason = reason
                existing.name = name
                existing.notes = notes
                existing.repeat_yearly = repeat_yearly
                db.commit()
                db.refresh(existing)
                return self._close_day_to_dict(existing)
                
            new_day = ShopCloseDay(
                shop_id=shop_id,
                date=date_val,
                name=name,
                reason=reason,
                notes=notes,
                repeat_yearly=repeat_yearly,
            )
            db.add(new_day)
            db.commit()
            db.refresh(new_day)
            return self._close_day_to_dict(new_day)
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

    def _business_hour_to_dict(self, row: ShopBusinessHour) -> Dict:
        return {
            "day": DAYS_OF_WEEK[row.day_of_week],
            "isOpen": row.is_open,
            "openTime": _format_time(row.open_time),
            "closeTime": _format_time(row.close_time),
        }

    def _ensure_business_hours(self, db: Session, shop_id: int) -> List[ShopBusinessHour]:
        rows = db.query(ShopBusinessHour).filter(
            ShopBusinessHour.shop_id == shop_id
        ).order_by(ShopBusinessHour.day_of_week).all()

        if len(rows) == 7:
            return rows

        existing_by_day = {row.day_of_week: row for row in rows}
        for idx, defaults in enumerate(DEFAULT_BUSINESS_HOURS):
            if idx in existing_by_day:
                continue
            row = ShopBusinessHour(
                shop_id=shop_id,
                day_of_week=idx,
                is_open=defaults["isOpen"],
                open_time=_parse_time(defaults["openTime"]),
                close_time=_parse_time(defaults["closeTime"]),
            )
            db.add(row)
        db.commit()

        return db.query(ShopBusinessHour).filter(
            ShopBusinessHour.shop_id == shop_id
        ).order_by(ShopBusinessHour.day_of_week).all()

    def _sync_operating_hours(self, db: Session, shop_id: int, rows: List[ShopBusinessHour]):
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            return

        open_rows = [row for row in rows if row.is_open]
        first_open = open_rows[0] if open_rows else None
        operating_hours = db.query(ShopOperatingHours).filter(
            ShopOperatingHours.shop_id == shop_id
        ).first()

        if not operating_hours:
            operating_hours = ShopOperatingHours(
                shop_id=shop_id,
                timezone=shop.timezone or "UTC",
            )
            db.add(operating_hours)

        operating_hours.operating_days = [row.day_of_week for row in open_rows]
        if first_open:
            operating_hours.open_time = first_open.open_time
            operating_hours.close_time = first_open.close_time
        if shop.timezone:
            operating_hours.timezone = shop.timezone

    def get_business_hours(self, shop_id: int) -> List[Dict]:
        db = self.get_db()
        try:
            rows = self._ensure_business_hours(db, shop_id)
            return [self._business_hour_to_dict(row) for row in rows]
        finally:
            db.close()

    def update_business_hours(self, shop_id: int, hours: List[schemas.ShopBusinessHourUpdate]) -> List[Dict]:
        db = self.get_db()
        try:
            rows = self._ensure_business_hours(db, shop_id)
            rows_by_day = {row.day_of_week: row for row in rows}
            seen_days: set[int] = set()

            for item in hours:
                day_idx = _day_index(item.day)
                if day_idx in seen_days:
                    raise ValueError(f"Duplicate day value: {item.day}")
                seen_days.add(day_idx)

                row = rows_by_day[day_idx]
                row.is_open = item.isOpen
                row.open_time = _parse_time(item.openTime)
                row.close_time = _parse_time(item.closeTime)

            self._sync_operating_hours(db, shop_id, list(rows_by_day.values()))
            db.commit()

            rows = db.query(ShopBusinessHour).filter(
                ShopBusinessHour.shop_id == shop_id
            ).order_by(ShopBusinessHour.day_of_week).all()
            return [self._business_hour_to_dict(row) for row in rows]
        finally:
            db.close()

    def _booking_settings_to_dict(self, settings: ShopBookingSettings) -> Dict:
        return {
            "bookingEnabled": settings.booking_enabled,
            "requireConfirmation": settings.require_confirmation,
            "allowRescheduling": settings.allow_rescheduling,
            "allowCancellations": settings.allow_cancellations,
            "bookingNotice": str(settings.booking_notice_hours),
            "reminderPreferences": settings.reminder_channel,
            "reminderTime": str(settings.reminder_time_hours),
            "followUp": settings.follow_up_enabled,
            "waitingList": settings.waiting_list_enabled,
            "autoConfirm": settings.auto_confirm,
        }

    def _ensure_booking_settings(self, db: Session, shop_id: int) -> ShopBookingSettings:
        settings = db.query(ShopBookingSettings).filter(
            ShopBookingSettings.shop_id == shop_id
        ).first()

        if settings:
            return settings

        settings = ShopBookingSettings(shop_id=shop_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return settings

    def get_booking_settings(self, shop_id: int) -> Dict:
        db = self.get_db()
        try:
            settings = self._ensure_booking_settings(db, shop_id)
            return self._booking_settings_to_dict(settings)
        finally:
            db.close()

    def update_booking_settings(self, shop_id: int, update: schemas.ShopBookingSettingsUpdate) -> Dict:
        db = self.get_db()
        try:
            settings = self._ensure_booking_settings(db, shop_id)
            data = update.model_dump(exclude_unset=True)

            field_map = {
                "bookingEnabled": "booking_enabled",
                "requireConfirmation": "require_confirmation",
                "allowRescheduling": "allow_rescheduling",
                "allowCancellations": "allow_cancellations",
                "bookingNotice": "booking_notice_hours",
                "reminderPreferences": "reminder_channel",
                "reminderTime": "reminder_time_hours",
                "followUp": "follow_up_enabled",
                "waitingList": "waiting_list_enabled",
                "autoConfirm": "auto_confirm",
            }

            for incoming_key, model_key in field_map.items():
                if incoming_key not in data:
                    continue
                value = data[incoming_key]
                if incoming_key in {"bookingNotice", "reminderTime"}:
                    value = int(value)
                setattr(settings, model_key, value)

            db.commit()
            db.refresh(settings)
            return self._booking_settings_to_dict(settings)
        finally:
            db.close()


shop_service = ShopService()
