from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import text

from database import SessionLocal
from modules.agent.models import ShopLLMConfig
from shared.crypto import decrypt_text


SUPPORTED_LLM_PROVIDERS = frozenset({"ollama", "openai", "anthropic", "groq", "google_genai", "nvidia"})
PREMIUM_SUBSCRIPTION_TIERS = frozenset({"premium", "enterprise"})
HOSTED_LLM_PROVIDERS = SUPPORTED_LLM_PROVIDERS.difference({"ollama"})


def _env_flag_enabled(name: str, *, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def provider_runtime_enabled(provider: str) -> bool:
    if provider == "groq":
        return _env_flag_enabled("ENABLE_GROQ_PROVIDER", default=False)
    if provider == "nvidia":
        return bool(os.getenv("NVIDIA_API_KEY"))
    return True


def _fallback_to_ollama(subscription_tier: Optional[str], *, include_api_key: bool) -> tuple[str, str, Optional[str], Optional[str], dict[str, Any]]:
    provider = "ollama"
    model_name = default_model_name_for_provider(provider)
    api_base_url = default_api_base_url_for_provider(provider)
    if normalize_subscription_tier(subscription_tier) not in PREMIUM_SUBSCRIPTION_TIERS:
        api_base_url = _free_tier_ollama_base_url()
    api_key = _default_api_key(provider) if include_api_key else None
    return provider, model_name, api_base_url, api_key, {}


def normalize_subscription_tier(subscription_tier: Optional[str]) -> str:
    if hasattr(subscription_tier, "value"):
        subscription_tier = subscription_tier.value
    return str(subscription_tier or "free").strip().lower()


def provider_allowed_for_tier(provider: str, subscription_tier: Optional[str]) -> bool:
    normalized_tier = normalize_subscription_tier(subscription_tier)
    # Platform-level providers are available to all tiers
    if provider in {"ollama", "nvidia"}:
        return True
    return normalized_tier in PREMIUM_SUBSCRIPTION_TIERS


def provider_catalog(subscription_tier: Optional[str] = None) -> list[dict[str, Any]]:
    available = [
        {
            "key": "ollama",
            "label": "Ollama",
            "default_model": default_model_name_for_provider("ollama"),
            "supports_api_key": False,
            "supports_api_base_url": True,
        },
        {
            "key": "openai",
            "label": "OpenAI",
            "default_model": default_model_name_for_provider("openai"),
            "supports_api_key": True,
            "supports_api_base_url": True,
        },
        {
            "key": "anthropic",
            "label": "Anthropic",
            "default_model": default_model_name_for_provider("anthropic"),
            "supports_api_key": True,
            "supports_api_base_url": False,
        },
        {
            "key": "groq",
            "label": "Groq",
            "default_model": default_model_name_for_provider("groq"),
            "supports_api_key": True,
            "supports_api_base_url": False,
        },
        {
            "key": "google_genai",
            "label": "Google Gemini",
            "default_model": default_model_name_for_provider("google_genai"),
            "supports_api_key": True,
            "supports_api_base_url": False,
        },
        {
            "key": "nvidia",
            "label": "NVIDIA NIM",
            "default_model": default_model_name_for_provider("nvidia"),
            "supports_api_key": True,
            "supports_api_base_url": False,
        },
    ]
    return [
        provider
        for provider in available
        if provider_runtime_enabled(provider["key"])
        and provider_allowed_for_tier(provider["key"], subscription_tier)
    ]


@dataclass(frozen=True)
class ResolvedLLMConfig:
    provider: str
    model_name: str
    api_base_url: Optional[str]
    api_key: Optional[str]
    settings: dict[str, Any]
    subscription_tier: str


def normalize_provider(provider: Optional[str]) -> str:
    normalized = str(provider or "ollama").strip().lower()
    aliases = {
        "google": "google_genai",
        "google-genai": "google_genai",
        "gemini": "google_genai",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_LLM_PROVIDERS:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return normalized


def default_model_name_for_provider(provider: str) -> str:
    defaults = {
        "ollama": os.getenv("MODEL_NAME", "qwen3:14b-q4_K_M"),
        "openai": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
        "groq": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        "google_genai": os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.0-flash"),
        "nvidia": os.getenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct"),
    }
    return defaults[provider]


def default_api_base_url_for_provider(provider: str) -> Optional[str]:
    if provider == "ollama":
        return os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
    if provider == "openai":
        return os.getenv("OPENAI_BASE_URL")
    return None


def _default_api_key(provider: str) -> Optional[str]:
    env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "groq": "GROQ_API_KEY",
        "google_genai": "GOOGLE_API_KEY",
        "nvidia": "NVIDIA_API_KEY",
    }
    env_name = env_map.get(provider)
    return os.getenv(env_name) if env_name else None


def _normalize_ollama_base_url(base_url: Optional[str]) -> str:
    resolved = str(base_url or default_api_base_url_for_provider("ollama") or "http://localhost:11434/v1").rstrip("/")
    if resolved.endswith("/v1"):
        return resolved[:-3]
    return resolved


def _free_tier_ollama_base_url() -> str:
    return os.getenv(
        "FREE_TIER_OLLAMA_URL",
        default_api_base_url_for_provider("ollama") or "http://localhost:30002/v1",
    )


def _shop_subscription_tier(db, shop_id: int) -> str:
    row = db.execute(
        text(
            """
            SELECT users.subscription_tier
            FROM shops
            JOIN users ON users.id = shops.owner_id
            WHERE shops.id = :shop_id
            LIMIT 1
            """
        ),
        {"shop_id": int(shop_id)},
    ).first()
    if row is None:
        return "free"
    return normalize_subscription_tier(row[0])


def load_shop_subscription_tier(shop_id: Optional[int]) -> str:
    if not shop_id:
        return "free"

    db = SessionLocal()
    try:
        return _shop_subscription_tier(db, int(shop_id))
    finally:
        db.close()


def load_shop_llm_config(shop_id: Optional[int]) -> ResolvedLLMConfig:
    provider = normalize_provider(os.getenv("LLM_PROVIDER", "ollama"))
    model_name = default_model_name_for_provider(provider)
    api_base_url = default_api_base_url_for_provider(provider)
    api_key = _default_api_key(provider)
    settings: dict[str, Any] = {}
    subscription_tier = normalize_subscription_tier(os.getenv("DEFAULT_SUBSCRIPTION_TIER", "free"))

    if shop_id:
        db = SessionLocal()
        try:
            subscription_tier = _shop_subscription_tier(db, int(shop_id))
            record = (
                db.query(ShopLLMConfig)
                .filter(ShopLLMConfig.shop_id == int(shop_id))
                .first()
            )
            if record is not None:
                provider = normalize_provider(record.provider)
                model_name = record.model_name or default_model_name_for_provider(provider)
                api_base_url = record.api_base_url or default_api_base_url_for_provider(provider)
                api_key = decrypt_text(record.api_key_encrypted) if record.api_key_encrypted else _default_api_key(provider)
                settings = dict(record.settings or {})
        finally:
            db.close()

    if not provider_runtime_enabled(provider):
        provider, model_name, api_base_url, api_key, settings = _fallback_to_ollama(
            subscription_tier,
            include_api_key=True,
        )

    if not provider_allowed_for_tier(provider, subscription_tier):
        provider, model_name, api_base_url, api_key, settings = _fallback_to_ollama(
            subscription_tier,
            include_api_key=True,
        )

    if provider == "ollama" and subscription_tier not in PREMIUM_SUBSCRIPTION_TIERS:
        api_base_url = _free_tier_ollama_base_url()

    return ResolvedLLMConfig(
        provider=provider,
        model_name=model_name,
        api_base_url=api_base_url,
        api_key=api_key,
        settings=settings,
        subscription_tier=subscription_tier,
    )


def resolve_shop_llm_environment(shop_id: Optional[int]) -> ResolvedLLMConfig:
    """Resolve the effective shop LLM environment without decrypting secrets.

    Owner settings only need environment metadata. Avoiding secret decryption here
    prevents stale encrypted API keys from breaking the read-only settings view.
    """

    provider = normalize_provider(os.getenv("LLM_PROVIDER", "ollama"))
    model_name = default_model_name_for_provider(provider)
    api_base_url = default_api_base_url_for_provider(provider)
    settings: dict[str, Any] = {}
    subscription_tier = normalize_subscription_tier(os.getenv("DEFAULT_SUBSCRIPTION_TIER", "free"))

    if shop_id:
        db = SessionLocal()
        try:
            subscription_tier = _shop_subscription_tier(db, int(shop_id))
            record = (
                db.query(ShopLLMConfig)
                .filter(ShopLLMConfig.shop_id == int(shop_id))
                .first()
            )
            if record is not None:
                provider = normalize_provider(record.provider)
                model_name = record.model_name or default_model_name_for_provider(provider)
                api_base_url = record.api_base_url or default_api_base_url_for_provider(provider)
                settings = dict(record.settings or {})
        finally:
            db.close()

    if not provider_runtime_enabled(provider):
        provider, model_name, api_base_url, _, settings = _fallback_to_ollama(
            subscription_tier,
            include_api_key=False,
        )

    if not provider_allowed_for_tier(provider, subscription_tier):
        provider, model_name, api_base_url, _, settings = _fallback_to_ollama(
            subscription_tier,
            include_api_key=False,
        )

    if provider == "ollama" and subscription_tier not in PREMIUM_SUBSCRIPTION_TIERS:
        api_base_url = _free_tier_ollama_base_url()

    return ResolvedLLMConfig(
        provider=provider,
        model_name=model_name,
        api_base_url=api_base_url,
        api_key=None,
        settings=settings,
        subscription_tier=subscription_tier,
    )


def _import_attr(module_name: str, attr_name: str):
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def _build_model_from_config(config: ResolvedLLMConfig, *, temperature: float):
    """Low-level builder. Accepts a fully-resolved config and returns an LLM instance."""
    settings = dict(config.settings or {})

    if config.provider == "ollama":
        ChatOllama = _import_attr("langchain_ollama", "ChatOllama")
        return ChatOllama(
            model=config.model_name,
            base_url=_normalize_ollama_base_url(config.api_base_url),
            temperature=temperature,
            top_p=float(settings.get("top_p", 0.9)),
            num_gpu=int(settings.get("num_gpu", -1)),
            timeout=120,
        )

    if config.provider == "openai":
        ChatOpenAI = _import_attr("langchain_openai", "ChatOpenAI")
        return ChatOpenAI(
            model=config.model_name,
            api_key=config.api_key,
            base_url=config.api_base_url,
            temperature=temperature,
        )

    if config.provider == "anthropic":
        ChatAnthropic = _import_attr("langchain_anthropic", "ChatAnthropic")
        return ChatAnthropic(
            model=config.model_name,
            api_key=config.api_key,
            temperature=temperature,
        )

    if config.provider == "groq":
        ChatGroq = _import_attr("langchain_groq", "ChatGroq")
        return ChatGroq(
            model=config.model_name,
            api_key=config.api_key,
            temperature=temperature,
        )

    if config.provider == "google_genai":
        ChatGoogleGenerativeAI = _import_attr("langchain_google_genai", "ChatGoogleGenerativeAI")
        return ChatGoogleGenerativeAI(
            model=config.model_name,
            google_api_key=config.api_key,
            temperature=temperature,
        )

    if config.provider == "nvidia":
        ChatNVIDIA = _import_attr("langchain_nvidia_ai_endpoints", "ChatNVIDIA")
        return ChatNVIDIA(
            model=config.model_name,
            api_key=config.api_key,
            temperature=temperature,
            max_completion_tokens=int(settings.get("max_tokens", 16384)),
            top_p=float(settings.get("top_p", 1.0)),
            timeout=120,
        )

    raise ValueError(f"Unsupported LLM provider: {config.provider}")


def create_chat_model(shop_id: Optional[int], *, temperature: float):
    return _build_model_from_config(load_shop_llm_config(shop_id), temperature=temperature)


# Providers that call external APIs (subject to rate-limits / network failures)
# Ollama is always local so it is NOT in this set.
_HOSTED_PROVIDERS: frozenset[str] = frozenset({"nvidia", "openai", "anthropic", "groq", "google_genai"})


def create_ollama_fallback_planner(*, temperature: float = 0.1):
    """
    Return a ChatOllama instance pointing at the platform-level local Ollama.
    Used as a secondary LLM when a hosted provider (NVIDIA, OpenAI, etc.) fails
    or times out.  Always ignores per-shop DB overrides — the fallback is always
    the local instance.
    """
    ChatOllama = _import_attr("langchain_ollama", "ChatOllama")
    return ChatOllama(
        model=default_model_name_for_provider("ollama"),
        base_url=_normalize_ollama_base_url(default_api_base_url_for_provider("ollama")),
        temperature=temperature,
        timeout=120,
    )


# ---------------------------------------------------------------------------
# Models that stream thinking tokens and do NOT support JSON/tool-call schemas
# ---------------------------------------------------------------------------
THINKING_MODELS: frozenset[str] = frozenset({
    "z-ai/glm4.7",
    "z-ai/glm4.7-thinking",
    "deepseek-ai/deepseek-r1",
    "deepseek-r1",
    "qwq-32b",
    "qwq-32b-preview",
    "qwq-32b-q8_0",
})

# Per-provider safe fallback for the planner slot when user picks a thinking model
_PLANNER_SAFE_FALLBACK: dict[str, str] = {
    "nvidia":       "meta/llama-3.1-8b-instruct",
    "ollama":       "qwen3:8b",
    "groq":         "llama-3.1-8b-instant",
    "openai":       "gpt-4.1-mini",
    "anthropic":    "claude-3-5-haiku-20241022",
    "google_genai": "gemini-2.0-flash",
}


def create_planner_model(shop_id: Optional[int], *, temperature: float = 0.1):
    """
    For classify_intent and plan_request nodes only.
    Guarantees with_structured_output() compatibility.
    If the shop has configured a thinking model, silently swaps to the
    safe fallback for that provider without touching the DB record.
    """
    config = load_shop_llm_config(shop_id)
    if config.model_name in THINKING_MODELS:
        safe_model = _PLANNER_SAFE_FALLBACK.get(config.provider, config.model_name)
        config = ResolvedLLMConfig(
            provider=config.provider,
            model_name=safe_model,
            api_base_url=config.api_base_url,
            api_key=config.api_key,
            settings=config.settings,
            subscription_tier=config.subscription_tier,
        )
    return _build_model_from_config(config, temperature=temperature)


def create_formatter_model(shop_id: Optional[int], *, temperature: float = 0.7):
    """
    For synthesize_response node only.
    No schema constraints — thinking models are fine and produce better prose.
    If the primary model is a hosted provider, Ollama is registered as a fallback
    so response synthesis never silently fails on API errors.
    """
    config = load_shop_llm_config(shop_id)
    primary = _build_model_from_config(config, temperature=temperature)
    if config.provider in _HOSTED_PROVIDERS:
        fallback = create_ollama_fallback_planner(temperature=temperature)
        return primary.with_fallbacks([fallback])
    return primary