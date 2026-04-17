from sqlalchemy.orm import Session
from database import SessionLocal
from modules.employees.models import ShopEmployee, EmployeeShift
from modules.employees import schemas
from modules.employees import schemas
from typing import List, Optional, Dict
from datetime import datetime

class EmployeeService:
    def get_db(self):
        return SessionLocal()

    def get_shop_employees(self, shop_id: int, include_inactive: bool = False) -> List[schemas.ShopEmployee]:
        db = self.get_db()
        try:
            query = db.query(ShopEmployee).filter(ShopEmployee.shop_id == shop_id)
            if not include_inactive:
                query = query.filter(ShopEmployee.is_active == True)
            employees = query.all()
            return [schemas.ShopEmployee.model_validate(e) for e in employees]
        finally:
            db.close()

    def create_shop_employee(self, data: Dict) -> schemas.ShopEmployee:
        db = self.get_db()
        try:
            emp = ShopEmployee(**data)
            db.add(emp)
            db.commit()
            db.refresh(emp)
            return schemas.ShopEmployee.model_validate(emp)
        finally:
            db.close()


employee_service = EmployeeService()
