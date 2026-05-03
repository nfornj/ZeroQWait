from typing import Any, Dict, Optional
from datetime import datetime
import re
import secrets

from database import SessionLocal
from db_interface import db_interface
from integrations.hr_mcp_client import HRMCPClient
from modules.auth.models import User, UserRole
from modules.employees.models import ShopEmployee
from shared.auth_utils import get_password_hash


_hr_mcp_client: Optional[HRMCPClient] = None


def _get_hr_client() -> HRMCPClient:
    global _hr_mcp_client
    if _hr_mcp_client is None:
        _hr_mcp_client = HRMCPClient()
    return _hr_mcp_client


def _candidate_username(name: str, email: str) -> str:
    email_local = (email or "").split("@", 1)[0].strip().lower()
    if email_local:
        base = re.sub(r"[^a-z0-9._-]+", "", email_local)
    else:
        base = re.sub(r"[^a-z0-9]+", "", name.strip().lower().replace(" ", "_"))
    return base or "employee"


def _build_unique_username(session, name: str, email: str) -> str:
    seed = _candidate_username(name, email)
    candidate = seed
    suffix = 1
    while session.query(User).filter(User.username == candidate).first():
        suffix += 1
        candidate = f"{seed}{suffix}"
    return candidate


def _build_employee_email(username: str, shop_id: int, provided_email: Optional[str] = None) -> str:
    normalized = (provided_email or "").strip().lower()
    if normalized:
        return normalized
    return f"{username}.shop{shop_id}@staff.zeroqwait.local"


def _local_list_employees(shop_id: int, include_inactive: bool = False) -> Dict[str, Any]:
    """List employees for a shop."""
    try:
        employees = db_interface.get_shop_employees(shop_id, is_active=None if include_inactive else True)
        
        employee_list = [
            {
                "id": e.get("user_id") or e.get("id"),
                "name": (e.get("user") or {}).get("username") or e.get("name"),
                "email": (e.get("user") or {}).get("email") or e.get("email"),
                "phone": e.get("phone"),
                "role": (e.get("user") or {}).get("role") or e.get("role", "employee"),
                "is_active": e.get("is_active", True)
            }
            for e in (employees or [])
        ]
        return {"employees": employee_list, "shop_id": shop_id}
    except Exception as e:
        return {"error": str(e)}


def _local_add_employee(
    shop_id: int,
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    role: str = "employee",
    employee_code: Optional[str] = None,
    created_by: Optional[int] = None,
) -> Dict[str, Any]:
    """Add an employee via db_interface after owner approval."""
    session = SessionLocal()
    try:
        username = _build_unique_username(session, name, email)
        resolved_email = _build_employee_email(username, shop_id, email)

        if session.query(User).filter(User.email == resolved_email).first():
            return {"error": f"Email {resolved_email} is already registered"}

        temporary_password = secrets.token_urlsafe(9)
        user = User(
            email=resolved_email,
            username=username,
            hashed_password=get_password_hash(temporary_password),
            role=UserRole(role) if role in UserRole._value2member_map_ else UserRole.EMPLOYEE,
            is_active=True,
        )
        session.add(user)
        session.flush()

        employee_link = ShopEmployee(
            shop_id=shop_id,
            user_id=user.id,
            created_by=created_by,
            is_active=True,
            employee_code=employee_code,
        )
        session.add(employee_link)
        session.commit()
        session.refresh(user)
        session.refresh(employee_link)

        return {
            "message": (
                f"Employee {name} added successfully. Username: {username}. "
                f"Staff email: {resolved_email}. Temporary password: {temporary_password}"
            ),
            "employee": {
                "id": employee_link.id,
                "shop_id": employee_link.shop_id,
                "user_id": user.id,
                "is_active": employee_link.is_active,
                "employee_code": employee_link.employee_code,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "role": user.role.value,
                    "is_active": user.is_active,
                },
            },
            "shop_id": shop_id,
            "user_id": user.id,
            "username": username,
            "email": resolved_email,
            "temporary_password": temporary_password,
            "status": "added",
        }
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


def _local_remove_employee(shop_id: int, user_id: int) -> Dict[str, Any]:
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


def _local_get_shifts(shop_id: int, date: Optional[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
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
                "name": s.get("username") or s.get("name") or f"Employee {s.get('user_id')}",
                "start_time": str(s.get("start_time") or s.get("clock_in")),
                "end_time": str(s.get("end_time") or s.get("clock_out")),
                "date": display_date,
            }
            for s in (shifts or [])
        ]
        return {"shifts": shift_list, "shop_id": shop_id}
    except Exception as e:
        return {"error": str(e)}


def _local_current_staffing_status(shop_id: int) -> Dict[str, Any]:
    """Return who is actively clocked in plus a simple staffing-gap signal."""
    session = SessionLocal()
    try:
        active_shifts = db_interface.get_shop_active_shifts(shop_id) or []
        metrics = db_interface.get_shop_live_wait_metrics(shop_id) or {}
        active_employees = db_interface.get_shop_employees(shop_id, is_active=True) or []

        active_roster_ids = {
            int(employee.get("user_id"))
            for employee in active_employees
            if employee.get("user_id") is not None
        }

        user_ids = {
            int(shift.get("user_id"))
            for shift in active_shifts
            if shift.get("user_id") is not None
        }
        users = {
            user.id: user
            for user in session.query(User).filter(User.id.in_(user_ids)).all()
        } if user_ids else {}

        on_shift = []
        for shift in sorted(active_shifts, key=lambda item: str(item.get("clock_in") or "")):
            user_id = shift.get("user_id")
            user = users.get(user_id)
            name = None
            if user is not None:
                name = user.username or user.email or f"Employee {user_id}"
            if not name:
                name = f"Employee {user_id}"
            on_shift.append(
                {
                    "id": shift.get("id"),
                    "user_id": user_id,
                    "name": name,
                    "clock_in": shift.get("clock_in"),
                    "clock_out": shift.get("clock_out"),
                    "in_active_roster": bool(user_id in active_roster_ids),
                }
            )

        queue_length = int(metrics.get("queue_length", 0) or 0)
        people_waiting = int(metrics.get("people_waiting", 0) or 0)
        people_being_served = int(metrics.get("people_being_served", 0) or 0)
        wait_minutes = int(metrics.get("estimated_wait_minutes", 0) or 0)
        active_count = len(on_shift)

        recommended_staff = 1
        if queue_length >= 10 or wait_minutes >= 60:
            recommended_staff = 3
        elif queue_length >= 5 or wait_minutes >= 30:
            recommended_staff = 2

        staffing_gap_count = max(0, recommended_staff - active_count)
        roster_mismatch_count = sum(1 for shift in on_shift if not shift["in_active_roster"])

        return {
            "shop_id": shop_id,
            "current_staffing": True,
            "on_shift": on_shift,
            "active_shift_count": active_count,
            "queue_length": queue_length,
            "people_waiting": people_waiting,
            "people_being_served": people_being_served,
            "estimated_wait_minutes": wait_minutes,
            "recommended_staff": recommended_staff,
            "staffing_gap_count": staffing_gap_count,
            "coverage_status": "understaffed" if staffing_gap_count > 0 else "covered",
            "roster_mismatch_count": roster_mismatch_count,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        session.close()


def _local_assign_shift(shop_id: int, user_id: int, start_time: str, end_time: str, date: str) -> Dict[str, Any]:
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


def _local_clock_in_out(shop_id: int, user_id: int, action: str) -> Dict[str, Any]:
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


def list_employees(shop_id: int, include_inactive: bool = False) -> Dict[str, Any]:
    return _get_hr_client().list_employees(shop_id, include_inactive=include_inactive)


def add_employee(
    shop_id: int,
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    role: str = "employee",
    employee_code: Optional[str] = None,
    created_by: Optional[int] = None,
) -> Dict[str, Any]:
    return _get_hr_client().add_employee(
        shop_id,
        name,
        email=email,
        phone=phone,
        role=role,
        employee_code=employee_code,
        created_by=created_by,
    )


def remove_employee(shop_id: int, user_id: int) -> Dict[str, Any]:
    return _get_hr_client().remove_employee(shop_id, user_id)


def get_shifts(shop_id: int, date: Optional[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
    return _get_hr_client().get_shifts(shop_id, date=date, user_id=user_id)


def assign_shift(shop_id: int, user_id: int, start_time: str, end_time: str, date: str) -> Dict[str, Any]:
    return _get_hr_client().assign_shift(shop_id, user_id, start_time, end_time, date)


def clock_in_out(shop_id: int, user_id: int, action: str) -> Dict[str, Any]:
    return _get_hr_client().clock_in_out(shop_id, user_id, action)
