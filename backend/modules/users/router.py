from fastapi import APIRouter, Depends, HTTPException, status
from modules.auth import schemas
from modules.auth.service import auth_service
from shared.auth_utils import get_password_hash, get_current_active_user

router = APIRouter()

@router.post("/users", response_model=schemas.User)
def create_user(user: schemas.UserCreate):
    # Check if email already exists
    existing_user = auth_service.get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username already exists
    existing_user = auth_service.get_user_by_username(user.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    try:
        # Create new user
        created_user = auth_service.create_user(user)
        if created_user:
            return created_user
        raise HTTPException(status_code=500, detail="Failed to create user")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")

@router.get("/users/me", response_model=schemas.User)
def read_users_me(current_user: schemas.User = Depends(get_current_active_user)):
    return current_user

@router.get("/users/check-username/{username}")
def check_username_availability(username: str):
    """Check if a username is available"""
    try:
        user = auth_service.get_user_by_username(username)
        return {"available": user is None}
    except Exception:
        return {"available": True}

@router.get("/users/check-email/{email}")
def check_email_availability(email: str):
    """Check if an email is available"""
    try:
        user = auth_service.get_user_by_email(email)
        return {"available": user is None}
    except Exception:
        return {"available": True}
