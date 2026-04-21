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
    """Add an employee via db_interface after owner approval."""
    try:
        result = db_interface.create_shop_employee({
            "shop_id": shop_id,
            "name": name,
            "email": email,
            "phone": phone,
            "role": role,
            "employee_code": employee_code,
            "is_active": True,
        })
        return {
            "message": f"Employee {name} added successfully",
            "employee": result,
            "shop_id": shop_id,
            "status": "added",
        }
    except Exception as e:
        return {"error": str(e)}


def remove_employee(shop_id: int, user_id: int) -> Dict[str, Any]:
    """Deactivate an employee after owner approval."""
    try:
        result = db_interface.update_shop_employee(shop_id, user_id, {"is_active": False})
        if result:
            return {
                "message": "Employee deactivated from shop",
                "shop_id": shop_id,
                "user_id": user_id,
                "status": "removed",
            }
        return {"error": "Employee not found", "shop_id": shop_id, "user_id": user_id}
    except Exception as e:
        return {"error": str(e)}


def get_shifts(shop_id: int, date: Optional[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Get shifts for a shop or employee."""
    try:
        if date:
            start_date = datetime.fromisoformat(date)
            end_date = start_date
            display_date = str(date)
        else:
            today = datetime.now()
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
            display_date = str(today.date())
        
        shifts = db_interface.get_employee_shifts(shop_id, start_date, end_date, user_id=user_id)
        
        shift_list = [
            {
                "id": s.get("id"),
                "user_id": s.get("user_id"),
                "start_time": str(s.get("start_time")),
                "end_time": str(s.get("end_time")),
                "date": display_date,
            }
            for s in (shifts or [])
        ]
        return {"shifts": shift_list, "shop_id": shop_id}
    except Exception as e:
        return {"error": str(e)}


def assign_shift(shop_id: int, user_id: int, start_time: str, end_time: str, date: str) -> Dict[str, Any]:
    """Assign a shift to an employee via db_interface after owner approval."""
    try:
        shift_data = {
            "shop_id": shop_id,
            "user_id": user_id,
            "clock_in": datetime.fromisoformat(f"{date}T{start_time}"),
            "clock_out": datetime.fromisoformat(f"{date}T{end_time}"),
        }
        result = db_interface.create_employee_shift(shift_data)
        return {
            "message": "Shift assigned to employee",
            "shift": result,
            "shop_id": shop_id,
            "user_id": user_id,
            "status": "assigned",
        }
    except Exception as e:
        return {"error": str(e)}


def clock_in_out(shop_id: int, user_id: int, action: str) -> Dict[str, Any]:
    """Clock in or out an employee via db_interface."""
    try:
        if action == "clock_in":
            shift_data = {
                "shop_id": shop_id,
                "user_id": user_id,
                "clock_in": datetime.now(),
            }
            result = db_interface.create_employee_shift(shift_data)
            return {
                "message": f"Employee clocked in",
                "shift": result,
                "shop_id": shop_id,
                "user_id": user_id,
                "action": action,
                "status": "recorded",
            }
        elif action == "clock_out":
            # Find the active (open) shift and close it
            from modules.employees.models import EmployeeShift
            session = db_interface.get_session()
            try:
                shift = session.query(EmployeeShift).filter(
                    EmployeeShift.shop_id == shop_id,
                    EmployeeShift.user_id == user_id,
                    EmployeeShift.clock_out == None,
                ).order_by(EmployeeShift.clock_in.desc()).first()
                if not shift:
                    return {"error": "No active shift found to clock out", "shop_id": shop_id}
                shift.clock_out = datetime.now()
                session.commit()
                session.refresh(shift)
                return {
                    "message": "Employee clocked out",
                    "shift": db_interface._model_to_dict(shift),
                    "shop_id": shop_id,
                    "user_id": user_id,
                    "action": action,
                    "status": "recorded",
                }
            finally:
                session.close()
        else:
            return {"error": f"Unknown action: {action}. Use 'clock_in' or 'clock_out'."}
    except Exception as e:
        return {"error": str(e)}
