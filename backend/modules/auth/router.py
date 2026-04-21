from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
import secrets
import os
import logging

from modules.auth import schemas
from modules.auth.service import auth_service
from shared.auth_utils import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from shared.email_utils import send_password_reset_email
from redis_client import redis_client
from audit_logger import audit

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/auth/token", response_model=schemas.Token)
async def login_for_access_token(
    response: Response,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    client_ip = request.client.host if request.client else None
    # Use service for authentication
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        await audit(
            action="AUTH",
            detail="login_failure",
            ip_address=client_ip,
            metadata={"username": form_data.username},
        )
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

    await audit(
        action="AUTH",
        detail="login_success",
        user_id=user.id,
        ip_address=client_ip,
        metadata={"username": user.username},
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
    token_key = f"password_reset:{reset_token}"

    # Persist one-time token for 1 hour.
    token_saved = redis_client.set(token_key, {"user_id": user.id}, ttl=3600)
    if not token_saved:
        logger.warning("Unable to persist password reset token for user_id=%s", user.id)
        return {"message": "If that email exists, a password reset link has been sent."}
    
    # Send email with reset link
    try:
        send_password_reset_email(user.email, reset_token)
    except Exception:
        pass  # Don't reveal if email sending failed

    await audit(
        action="AUTH",
        detail="password_reset_request",
        user_id=user.id,
        metadata={"email": user.email},
    )
    
    return {"message": "If that email exists, a password reset link has been sent."}

@router.post("/auth/reset-password")
async def reset_password(token: str, new_password: str):
    """Reset password using token from email"""
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long",
        )

    token_key = f"password_reset:{token}"
    token_payload = redis_client.get(token_key)
    if not token_payload or not isinstance(token_payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user_id = token_payload.get("user_id")
    if not isinstance(user_id, int):
        redis_client.delete(token_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    password_updated = auth_service.update_user_password(user_id=user_id, new_password=new_password)
    # Invalidate token regardless of update result to prevent token replay.
    redis_client.delete(token_key)

    if not password_updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    await audit(
        action="AUTH",
        detail="password_reset_success",
        user_id=user_id,
    )

    return {"message": "Password has been reset successfully."}
