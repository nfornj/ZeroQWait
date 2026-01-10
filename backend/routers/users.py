from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from supabase_client import supabase
import schemas
from auth_utils import get_password_hash, get_current_active_user

router = APIRouter()

@router.post("/users", response_model=schemas.User)
def create_user(user: schemas.UserCreate):
    # Check if email already exists
    try:
        email_check = supabase.table("users").select("id").eq("email", user.email).execute()
        if email_check.data:
            raise HTTPException(status_code=400, detail="Email already registered")
    except HTTPException:
        raise
    except Exception:
        pass
    
    # Check if username already exists
    try:
        username_check = supabase.table("users").select("id").eq("username", user.username).execute()
        if username_check.data:
            raise HTTPException(status_code=400, detail="Username already taken")
    except HTTPException:
        raise
    except Exception:
        pass
    
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
        response = supabase.table("users").insert(user_data).execute()
        if response.data:
            return response.data[0]
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
        response = supabase.table("users").select("id").eq("username", username).execute()
        return {"available": len(response.data) == 0}
    except Exception:
        return {"available": True}

@router.get("/users/check-email/{email}")
def check_email_availability(email: str):
    """Check if an email is available"""
    try:
        response = supabase.table("users").select("id").eq("email", email).execute()
        return {"available": len(response.data) == 0}
    except Exception:
        return {"available": True}

