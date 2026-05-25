from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Mapping

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

ENV_EXAMPLE_SECRET_NAMES: tuple[str, ...] = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "REDIS_HOST",
    "REDIS_PORT",
    "OLLAMA_URL",
    "MODEL_NAME",
    "LLM_PROVIDER",
    "NVIDIA_MODEL",
    "NVIDIA_API_KEY",
    "GROQ_API_KEY",
    "TTS_SERVICE_URL",
    "SECRET_KEY",
    "SUPERTOKENS_CONNECTION_URI",
    "SUPERTOKENS_API_KEY",
    "REACT_APP_API_URL",
    "FRONTEND_URL",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "STRIPE_SECRET_KEY",
    "STRIPE_PUBLISHABLE_KEY",
    "B2_ENDPOINT",
    "B2_KEY_ID",
    "B2_APP_KEY",
    "B2_BUCKET_NAME",
    "BOOKING_MCP_URL",
    "FINANCE_MCP_URL",
    "HR_MCP_URL",
    "ODOO_MCP_URL",
    "POSTGRES_MCP_URL",
    "FINANCE_DYNAMIC_READS_MODE",
    "ODOO_URL",
    "ODOO_DB",
    "ODOO_USER",
    "ODOO_PASSWORD",
)

_loaded = False


def _load_local_env() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    repo_root = backend_dir.parent
    load_dotenv(dotenv_path=repo_root / ".env", override=False)
    load_dotenv(dotenv_path=backend_dir / ".env", override=False)

    env_slug = (os.getenv("INFISICAL_ENV") or os.getenv("INFISICAL_ENVIRONMENT") or "").strip()
    if env_slug:
        load_dotenv(dotenv_path=repo_root / f".env.{env_slug}", override=False)
        load_dotenv(dotenv_path=backend_dir / f".env.{env_slug}", override=False)
        return

    if not os.getenv("INFISICAL_CLIENT_ID") and (repo_root / ".env.test").exists():
        load_dotenv(dotenv_path=repo_root / ".env.test", override=False)
        load_dotenv(dotenv_path=backend_dir / ".env.test", override=False)


def _is_enabled() -> bool:
    raw_value = os.getenv("INFISICAL_ENABLED", "auto").strip().lower()
    if raw_value in {"0", "false", "no", "off", "disabled"}:
        return False
    if raw_value in {"1", "true", "yes", "on", "enabled"}:
        return True
    return bool(os.getenv("INFISICAL_CLIENT_ID") and os.getenv("INFISICAL_CLIENT_SECRET"))


def _extract_access_token(payload: Mapping[str, object]) -> str | None:
    token = payload.get("accessToken") or payload.get("access_token")
    if isinstance(token, str):
        return token

    nested = payload.get("token")
    if isinstance(nested, Mapping):
        nested_token = nested.get("accessToken") or nested.get("access_token")
        if isinstance(nested_token, str):
            return nested_token

    return None


def _fetch_infisical_secret_values() -> dict[str, str]:
    base_url = os.getenv("INFISICAL_URL", "https://app.infisical.com").rstrip("/")
    client_id = os.getenv("INFISICAL_CLIENT_ID", "").strip()
    client_secret = os.getenv("INFISICAL_CLIENT_SECRET", "").strip()
    project_id = (
        os.getenv("INFISICAL_PROJECT_ID")
        or os.getenv("INFISICAL_WORKSPACE_ID")
        or ""
    ).strip()
    environment = (os.getenv("INFISICAL_ENV") or os.getenv("INFISICAL_ENVIRONMENT") or "prod").strip()
    secret_path = os.getenv("INFISICAL_SECRET_PATH", "/").strip() or "/"
    timeout_seconds = float(os.getenv("INFISICAL_TIMEOUT_SECONDS", "10"))

    if not client_id or not client_secret:
        raise RuntimeError("INFISICAL_CLIENT_ID and INFISICAL_CLIENT_SECRET are required")
    if not project_id:
        raise RuntimeError("INFISICAL_PROJECT_ID or INFISICAL_WORKSPACE_ID is required")

    with httpx.Client(base_url=base_url, timeout=timeout_seconds) as client:
        auth_response = client.post(
            "/api/v1/auth/universal-auth/login",
            json={"clientId": client_id, "clientSecret": client_secret},
        )
        auth_response.raise_for_status()
        access_token = _extract_access_token(auth_response.json())
        if not access_token:
            raise RuntimeError("Infisical Universal Auth response did not include an access token")

        secrets_response = client.get(
            "/api/v3/secrets/raw",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "workspaceId": project_id,
                "environment": environment,
                "secretPath": secret_path,
                "include_imports": "true",
            },
        )
        secrets_response.raise_for_status()

    payload = secrets_response.json()
    raw_secrets = payload.get("secrets", []) if isinstance(payload, Mapping) else []
    values: dict[str, str] = {}
    for item in raw_secrets:
        if not isinstance(item, Mapping):
            continue
        key = item.get("secretKey") or item.get("key") or item.get("secretName")
        value = item.get("secretValue") or item.get("value")
        if isinstance(key, str) and key in ENV_EXAMPLE_SECRET_NAMES and value is not None:
            values[key] = str(value)
    return values


def load_infisical_secrets() -> None:
    global _loaded
    if _loaded:
        return

    _load_local_env()

    if not _is_enabled():
        _loaded = True
        logger.info("Infisical secret loading skipped; using local process environment.")
        return

    try:
        values = _fetch_infisical_secret_values()
    except Exception as exc:
        _loaded = True
        logger.warning("Infisical secret loading failed; using local process environment fallback: %s", exc)
        return

    for key, value in values.items():
        os.environ[key] = value

    _loaded = True
    logger.info("Loaded %s backend secrets from Infisical.", len(values))


def getenv(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)
