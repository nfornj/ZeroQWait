from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
import secrets
import os

from modules.auth import schemas
from modules.auth.service import auth_service
from shared.auth_utils import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from shared.email_utils import send_password_reset_email

router = APIRouter()

@router.post("/auth/token", response_model=schemas.Token)
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    # Use service for authentication
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # user is Pydantic model but supports dict access if using DictModel, 
    # OR we can use attribute access. Let's use attribute access for better style,
    # but dict access is supported for legacy code.
    # Safe to use user.username here.
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Set cookie for subdomain persistence
    cookie_domain = os.getenv("COOKIE_DOMAIN") 
    secure_cookie = os.getenv("USE_HTTPS", "false").lower() == "true"
    
    response.set_cookie(
        key="access_token",
        value=access_token, 
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=secure_cookie,
        domain=cookie_domain
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/auth/forgot-password")
async def request_password_reset(email: str):
    """Request a password reset email"""
    # Find user by email using service
    user = auth_service.get_user_by_email(email)
    
    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If that email exists, a password reset link has been sent."}
    
    # Generate secure random token
    reset_token = secrets.token_urlsafe(32)
    
    # Send email with reset link
    try:
        send_password_reset_email(user.email, reset_token)
    except Exception:
        pass  # Don't reveal if email sending failed
    
    return {"message": "If that email exists, a password reset link has been sent."}

@router.post("/auth/reset-password")
async def reset_password(token: str, new_password: str):
    """Reset password using token from email"""
    # TODO: Implement password reset with password_reset_tokens table
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset feature not yet implemented with local PostgreSQL"
    )
