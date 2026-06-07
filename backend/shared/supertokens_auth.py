from __future__ import annotations

import logging
from urllib.parse import urlparse
from typing import Any

from fastapi import Request
from supertokens_python import InputAppInfo, SupertokensConfig, init as supertokens_init
from supertokens_python import asyncio as supertokens_asyncio
from supertokens_python.exceptions import GeneralError
from supertokens_python.recipe import emailpassword, session
from supertokens_python.recipe.emailpassword import asyncio as emailpassword_asyncio
from supertokens_python.recipe.emailpassword.interfaces import (
    EmailAlreadyExistsError,
    SignInOkResult,
    SignUpOkResult,
    WrongCredentialsError,
)
from supertokens_python.recipe.session import asyncio as session_asyncio
from supertokens_python.recipe.session.interfaces import SessionContainer

from shared.secrets import getenv, load_infisical_secrets

logger = logging.getLogger(__name__)

SUPERTOKENS_TENANT_ID = "public"

_initialized = False


def init_supertokens() -> None:
    global _initialized
    if _initialized:
        return

    load_infisical_secrets()

    connection_uri = getenv("SUPERTOKENS_CONNECTION_URI", "http://supertokens-svc:3567")
    api_key = getenv("SUPERTOKENS_API_KEY") or None
    frontend_url = getenv("FRONTEND_URL", "http://localhost:3000") or "http://localhost:3000"
    api_domain = getenv("SUPERTOKENS_API_DOMAIN", frontend_url) or frontend_url
    cookie_domain = getenv("COOKIE_DOMAIN") or None
    secure_cookie = (getenv("USE_HTTPS", "false") or "false").lower() == "true" or api_domain.startswith("https://")
    cookie_same_site = "none" if secure_cookie else "lax"

    api_host = (urlparse(api_domain).hostname or "").lower()
    frontend_host = (urlparse(frontend_url).hostname or "").lower()

    if cookie_same_site == "none" and not secure_cookie:
        logger.error("Invalid session cookie config: SameSite=None requires Secure cookies. Falling back to SameSite=lax.")
        cookie_same_site = "lax"

    if not cookie_domain and api_host and frontend_host and api_host != frontend_host:
        logger.warning(
            "COOKIE_DOMAIN is not set while API and frontend hosts differ (api=%s, frontend=%s). "
            "Set COOKIE_DOMAIN explicitly (for example: .zeroqwait.com).",
            api_host,
            frontend_host,
        )

    logger.info(
        "SuperTokens cookie config: api_domain=%s frontend_url=%s cookie_domain=%s secure_cookie=%s same_site=%s",
        api_domain,
        frontend_url,
        cookie_domain or "<default>",
        secure_cookie,
        cookie_same_site,
    )

    try:
        supertokens_init(
            app_info=InputAppInfo(
                app_name="ZeroQwait",
                api_domain=api_domain,
                website_domain=frontend_url,
                api_base_path="/api/auth",
                website_base_path="/auth",
            ),
            framework="fastapi",
            supertokens_config=SupertokensConfig(
                connection_uri=connection_uri,
                api_key=api_key,
            ),
            recipe_list=[
                emailpassword.init(),
                session.init(
                    cookie_domain=cookie_domain,
                    cookie_secure=secure_cookie,
                    cookie_same_site=cookie_same_site,
                ),
            ],
        )
    except GeneralError as exc:
        if "Initialisation already done" not in str(exc):
            raise

    _initialized = True
    logger.info("SuperTokens initialized with EmailPassword and Session recipes.")


async def sign_up_email_password(email: str, password: str) -> SignUpOkResult | EmailAlreadyExistsError:
    init_supertokens()
    return await emailpassword_asyncio.sign_up(SUPERTOKENS_TENANT_ID, email, password)


async def sign_in_email_password(email: str, password: str) -> SignInOkResult | WrongCredentialsError:
    init_supertokens()
    return await emailpassword_asyncio.sign_in(SUPERTOKENS_TENANT_ID, email, password)


async def create_app_user_id_mapping(supertokens_user_id: str, app_user_id: int) -> None:
    init_supertokens()
    try:
        await supertokens_asyncio.create_user_id_mapping(
            supertokens_user_id=supertokens_user_id,
            external_user_id=str(app_user_id),
            external_user_id_info="zeroqwait-platform-user-id",
            force=True,
        )
    except Exception as exc:
        message = str(exc)
        if "already" in message.lower() and str(app_user_id) in message:
            return
        raise


async def delete_supertokens_user(user_id: str) -> None:
    init_supertokens()
    await supertokens_asyncio.delete_user(user_id)


async def create_session_for_local_user(
    request: Request,
    auth_result: SignInOkResult | SignUpOkResult,
    *,
    app_user_id: int,
    username: str,
    email: str,
    role: str,
) -> SessionContainer:
    init_supertokens()
    await create_app_user_id_mapping(auth_result.recipe_user_id.get_as_string(), app_user_id)
    return await session_asyncio.create_new_session(
        request,
        SUPERTOKENS_TENANT_ID,
        auth_result.recipe_user_id,
        access_token_payload={
            "app_user_id": app_user_id,
            "username": username,
            "email": email,
            "role": role,
        },
        session_data_in_database={"app_user_id": app_user_id},
    )


async def get_session_from_request(request: Request, *, session_required: bool = False) -> SessionContainer | None:
    init_supertokens()
    auth_header = request.headers.get("authorization", "")
    has_bearer_header = auth_header.lower().startswith("bearer ")

    # For bearer-token clients (mobile/API), CSRF tokens are not required.
    anti_csrf_check: bool | None = False if has_bearer_header else None

    return await session_asyncio.get_session(
        request,
        session_required=session_required,
        anti_csrf_check=anti_csrf_check,
        check_database=False,
    )


async def update_supertokens_password_for_app_user(*, app_user_id: int, new_password: str) -> bool:
    init_supertokens()

    mapping = None
    try:
        mapping = await supertokens_asyncio.get_user_id_mapping(user_id=str(app_user_id), user_id_type="external")
    except TypeError:
        mapping = await supertokens_asyncio.get_user_id_mapping(str(app_user_id), "external")

    if mapping is None:
        logger.warning("No SuperTokens user mapping found for app_user_id=%s", app_user_id)
        return False

    supertokens_user_id = (
        getattr(mapping, "supertokens_user_id", None)
        or getattr(mapping, "super_tokens_user_id", None)
        or getattr(mapping, "user_id", None)
    )
    if not supertokens_user_id:
        logger.warning("SuperTokens mapping missing user id for app_user_id=%s", app_user_id)
        return False

    try:
        await emailpassword_asyncio.update_email_or_password(
            user_id=str(supertokens_user_id),
            password=new_password,
            tenant_id_for_password_policy=SUPERTOKENS_TENANT_ID,
        )
    except TypeError:
        await emailpassword_asyncio.update_email_or_password(
            recipe_user_id=str(supertokens_user_id),
            password=new_password,
            tenant_id_for_password_policy=SUPERTOKENS_TENANT_ID,
        )

    return True


def is_sign_in_ok(result: Any) -> bool:
    return isinstance(result, SignInOkResult)


def is_sign_up_ok(result: Any) -> bool:
    return isinstance(result, SignUpOkResult)


def is_wrong_credentials(result: Any) -> bool:
    return isinstance(result, WrongCredentialsError)


def is_email_already_exists(result: Any) -> bool:
    return isinstance(result, EmailAlreadyExistsError)