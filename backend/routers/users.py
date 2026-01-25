from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from db_interface import db_interface
import schemas
from auth_utils import get_password_hash, get_current_active_user

router = APIRouter()

@router.post("/users", response_model=schemas.User)
def create_user(user: schemas.UserCreate):
    # Check if email already exists
    existing_user = db_interface.get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username already exists
    existing_user = db_interface.get_user_by_username(user.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    user_data = {
        "email": user.email,
        "username": user.username,
        "hashed_password": hashed_password,
        "role": user.role.value,
        "is_active": True,
        "subscription_tier": "free"
    }
    
    try:
        created_user = db_interface.create_user(user_data)
        if created_user:
            return created_user
        raise HTTPException(status_code=500, detail="Failed to create user")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")

@router.get("/users/me", response_model=schemas.User)
def read_users_me(current_user: dict = Depends(get_current_active_user)):
    return current_user

@router.get("/users/check-username/{username}")
def check_username_availability(username: str):
    """Check if a username is available"""
    try:
        user = db_interface.get_user_by_username(username)
        return {"available": user is None}
    except Exception:
        return {"available": True}

@router.get("/users/check-email/{email}")
def check_email_availability(email: str):
    """Check if an email is available"""
    try:
        user = db_interface.get_user_by_email(email)
        return {"available": user is None}
    except Exception:
        return {"available": True}

