"""
Employee, shop-service, shift, and conversation-history operations.
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



class EmployeesMixin:
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

    def add_message_to_history(self, session_id: str, role: str, content, tool_call_id: str = None) -> Dict:
        db = self.get_session()
        try:
            # Coerce content to string — guards against pydantic model objects being passed directly
            if hasattr(content, 'response'):
                content_str = content.response
            elif hasattr(content, '__str__'):
                content_str = str(content)
            else:
                content_str = content
            msg = ConversationHistory(
                session_id=session_id,
                role=role,
                content=content_str,
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
    
