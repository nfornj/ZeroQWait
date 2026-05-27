from __future__ import annotations

import logging
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
                    cookie_same_site="none" if secure_cookie else "lax",
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
        if isinstance(exc, KeyError) and exc.args == ("does_external_user_id_exist",):
            logger.warning("SuperTokens user-id mapping response omitted existence flags; continuing with session payload mapping.")
            return
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
    return await session_asyncio.get_session(
        request,
        session_required=session_required,
        anti_csrf_check=False,
        check_database=False,
    )


def is_sign_in_ok(result: Any) -> bool:
    return isinstance(result, SignInOkResult)


def is_sign_up_ok(result: Any) -> bool:
    return isinstance(result, SignUpOkResult)


def is_wrong_credentials(result: Any) -> bool:
    return isinstance(result, WrongCredentialsError)


def is_email_already_exists(result: Any) -> bool:
    return isinstance(result, EmailAlreadyExistsError)