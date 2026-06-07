from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
import secrets
import logging

from modules.auth import schemas
from modules.auth.service import auth_service
from shared.email_utils import send_password_reset_email
from shared.supertokens_auth import (
    create_session_for_local_user,
    get_session_from_request,
    is_email_already_exists,
    is_sign_in_ok,
    is_sign_up_ok,
    is_wrong_credentials,
    sign_in_email_password,
    sign_up_email_password,
    update_supertokens_password_for_app_user,
)
from redis_client import redis_client
from audit_logger import audit

router = APIRouter()
logger = logging.getLogger(__name__)


def _role_value(user: schemas.User) -> str:
    return getattr(user.role, "value", str(user.role))


def _find_login_user(identifier: str):
    return auth_service.get_user_by_username(identifier) or auth_service.get_user_by_email(identifier)


async def _login_with_supertokens(
    *,
    request: Request,
    username_or_email: str,
    password: str,
    client_ip: str | None = None,
):
    local_user = _find_login_user(username_or_email)
    login_email = local_user.email if local_user else username_or_email

    auth_result = await sign_in_email_password(login_email, password)

    if is_wrong_credentials(auth_result) and local_user:
        migrated_user = auth_service.authenticate_user(username_or_email, password)
        if migrated_user:
            signup_result = await sign_up_email_password(local_user.email, password)
            if is_email_already_exists(signup_result):
                auth_result = await sign_in_email_password(local_user.email, password)
            elif is_sign_up_ok(signup_result):
                auth_result = signup_result

    if not is_sign_in_ok(auth_result) and not is_sign_up_ok(auth_result):
        await audit(
            action="AUTH",
            detail="login_failure",
            ip_address=client_ip,
            metadata={"username": username_or_email},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    local_user = local_user or auth_service.get_user_by_email(login_email)
    if not local_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is not provisioned in ZeroQwait",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session = await create_session_for_local_user(
        request,
        auth_result,
        app_user_id=local_user.id,
        username=local_user.username,
        email=local_user.email,
        role=_role_value(local_user),
    )

    await audit(
        action="AUTH",
        detail="login_success",
        user_id=local_user.id,
        ip_address=client_ip,
        metadata={"username": local_user.username},
    )

    return {"access_token": session.get_access_token(), "token_type": "bearer"}

@router.post("/auth/token", response_model=schemas.Token)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    client_ip = request.client.host if request.client else None
    return await _login_with_supertokens(
        request=request,
        username_or_email=form_data.username,
        password=form_data.password,
        client_ip=client_ip,
    )


@router.post("/auth/login", response_model=schemas.Token)
async def login(request: Request):
    body = await request.json()
    username_or_email = body.get("username") or body.get("email")
    password = body.get("password")
    if not username_or_email or not password:
        raise HTTPException(status_code=400, detail="username/email and password are required")
    client_ip = request.client.host if request.client else None
    return await _login_with_supertokens(
        request=request,
        username_or_email=username_or_email,
        password=password,
        client_ip=client_ip,
    )


@router.post("/auth/register")
async def register(user: schemas.UserCreate, request: Request):
    if auth_service.get_user_by_email(user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if auth_service.get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    try:
        created_user = await auth_service.create_user_with_supertokens(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {exc}")

    auth_result = await sign_in_email_password(created_user.email, user.password)
    if not is_sign_in_ok(auth_result):
        raise HTTPException(status_code=500, detail="User created but session creation failed")

    session = await create_session_for_local_user(
        request,
        auth_result,
        app_user_id=created_user.id,
        username=created_user.username,
        email=created_user.email,
        role=_role_value(created_user),
    )
    return {
        "access_token": session.get_access_token(),
        "token_type": "bearer",
        "user": created_user.model_dump(mode="json"),
    }


@router.post("/auth/logout")
async def logout(response: Response, request: Request):
    current_session = await get_session_from_request(request, session_required=False)
    if current_session:
        await current_session.revoke_session()
    response.delete_cookie("access_token")
    return {"message": "Logged out"}

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
    if not password_updated:
        # Invalidate token regardless of update result to prevent token replay.
        redis_client.delete(token_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    try:
        supertokens_password_updated = await update_supertokens_password_for_app_user(
            app_user_id=user_id,
            new_password=new_password,
        )
    except Exception as exc:
        logger.exception("Failed to sync password reset to SuperTokens for user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed. Please retry.",
        ) from exc

    # Invalidate token after successful local + SuperTokens password updates.
    redis_client.delete(token_key)

    if not supertokens_password_updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed. Please contact support.",
        )

    await audit(
        action="AUTH",
        detail="password_reset_success",
        user_id=user_id,
    )

    return {"message": "Password has been reset successfully."}
