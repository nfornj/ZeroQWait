from typing import Any, Dict, Optional
from datetime import datetime
from db_interface import db_interface


def list_employees(shop_id: int, include_inactive: bool = False) -> Dict[str, Any]:
    """List employees for a shop."""
    try:
        employees = db_interface.get_shop_employees(shop_id, is_active=None if include_inactive else True)
        
        employee_list = [
            {
                "id": e.get("id"),
                "name": e.get("name"),
                "email": e.get("email"),
                "phone": e.get("phone"),
                "role": e.get("role", "employee"),
                "is_active": e.get("is_active", True)
            }
            for e in (employees or [])
        ]
        return {"employees": employee_list, "shop_id": shop_id}
    except Exception as e:
        return {"error": str(e)}


def add_employee(
    shop_id: int,
    name: str,
    email: str,
    phone: Optional[str] = None,
    role: str = "employee",
    employee_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Add an employee (Phase 2 placeholder)."""
    try:
        return {
            "message": f"Employee {name} added successfully",
            "shop_id": shop_id,
            "status": "added",
            "requires_approval": True
        }
    except Exception as e:
        return {"error": str(e)}


def remove_employee(shop_id: int, user_id: int) -> Dict[str, Any]:
    """Remove an employee (Phase 2 placeholder)."""
    try:
        return {
            "message": f"Employee removed from shop",
            "shop_id": shop_id,
            "user_id": user_id,
            "status": "removed",
            "requires_approval": True
        }
    except Exception as e:
        return {"error": str(e)}


def get_shifts(shop_id: int, date: Optional[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Get shifts for a shop or employee."""
    try:
        if date:
            start_date = datetime.fromisoformat(date)
            end_date = start_date
        else:
            today = datetime.now()
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        shifts = db_interface.get_employee_shifts(shop_id, start_date, end_date, user_id=user_id)
        
        shift_list = [
            {
                "id": s.get("id"),
                "user_id": s.get("user_id"),
                "start_time": str(s.get("start_time")),
                "end_time": str(s.get("end_time")),
                "date": str(date) if date else str(today.date())
            }
            for s in (shifts or [])
        ]
        return {"shifts": shift_list, "shop_id": shop_id}
    except Exception as e:
        return {"error": str(e)}


def assign_shift(shop_id: int, user_id: int, start_time: str, end_time: str, date: str) -> Dict[str, Any]:
    """Assign a shift to an employee (Phase 2 placeholder)."""
    try:
        return {
            "message": f"Shift assigned to employee",
            "shop_id": shop_id,
            "user_id": user_id,
            "status": "assigned",
            "requires_approval": True
        }
    except Exception as e:
        return {"error": str(e)}


def clock_in_out(shop_id: int, user_id: int, action: str) -> Dict[str, Any]:
    """Clock in or out (Phase 2 placeholder)."""
    try:
        return {
            "message": f"Employee {action} recorded",
            "shop_id": shop_id,
            "user_id": user_id,
            "action": action,
            "status": "recorded"
        }
    except Exception as e:
        return {"error": str(e)}
