from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta, datetime
import secrets

import schemas
from db_interface import db_interface
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
    user = db_interface.get_user_by_email(email)
    
    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If that email exists, a password reset link has been sent."}
    
    # Generate secure random token
    reset_token = secrets.token_urlsafe(32)
    
    # Create reset token record (expires in 1 hour)
    # Note: Password reset functionality requires additional table - simplified for now
    # TODO: Implement password_reset_tokens table and logic
    
    # Send email with reset link
    try:
        send_password_reset_email(user["email"], reset_token)
    except Exception:
        pass  # Don't reveal if email sending failed
    
    return {"message": "If that email exists, a password reset link has been sent."}

@router.post("/auth/reset-password")
async def reset_password(token: str, new_password: str):
    """Reset password using token from email"""
    # TODO: Implement password reset with password_reset_tokens table
    # For now, return not implemented
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset feature not yet implemented with local PostgreSQL"
    )
