from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta, datetime
import secrets

import schemas
from supabase_client import supabase
from auth_utils import authenticate_user, create_access_token, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES
from email_utils import send_password_reset_email

router = APIRouter()

@router.post("/auth/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/auth/forgot-password")
async def request_password_reset(email: str):
    """Request a password reset email"""
    # Find user by email
    try:
        response = supabase.table("users").select("*").eq("email", email).execute()
        user = response.data[0] if response.data else None
    except Exception:
        user = None
    
    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If that email exists, a password reset link has been sent."}
    
    # Generate secure random token
    reset_token = secrets.token_urlsafe(32)
    
    # Create reset token record (expires in 1 hour)
    token_data = {
        "user_id": user["id"],
        "token": reset_token,
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
    }
    supabase.table("password_reset_tokens").insert(token_data).execute()
    
    # Send email with reset link
    send_password_reset_email(user["email"], reset_token)
    
    return {"message": "If that email exists, a password reset link has been sent."}

@router.post("/auth/reset-password")
async def reset_password(token: str, new_password: str):
    """Reset password using token from email"""
    # Find token
    try:
        response = supabase.table("password_reset_tokens").select("*").eq("token", token).execute()
        token_record = response.data[0] if response.data else None
    except Exception:
        token_record = None
    
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Check if token is expired
    expires_at = datetime.fromisoformat(token_record["expires_at"].replace("Z", "+00:00"))
    if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired"
        )
    
    # Check if token was already used
    if token_record["used"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has already been used"
        )
    
    # Get user
    try:
        user_response = supabase.table("users").select("*").eq("id", token_record["user_id"]).execute()
        user = user_response.data[0] if user_response.data else None
    except Exception:
        user = None
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    supabase.table("users").update(
        {"hashed_password": get_password_hash(new_password)}
    ).eq("id", user["id"]).execute()
    
    # Mark token as used
    supabase.table("password_reset_tokens").update(
        {"used": True}
    ).eq("id", token_record["id"]).execute()
    
    return {"message": "Password has been reset successfully"}
