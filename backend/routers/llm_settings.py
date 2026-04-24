from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.llm_factory import (
    load_shop_llm_config,
    resolve_shop_llm_environment,
)
from database import get_db
from modules.agent.models import ShopLLMConfig
from permissions import check_shop_access
from shared.auth_utils import get_current_user


router = APIRouter()


class ShopAIEnvironmentResponse(BaseModel):
    shop_id: int
    subscription_tier: str
    environment_name: str
    environment_summary: str
    operating_mode: str
    status_label: str
    uses_default: bool
    can_customize: bool
    capabilities: list[str]
    experience_notes: list[str]


OWNER_AI_SETTINGS_LOCKED_MESSAGE = (
    "ZeroQwait manages the AI environment for shop owners. Technical model and provider customization "
    "is not available in owner settings."
)


def _build_response(shop_id: int, record: Optional[ShopLLMConfig]) -> ShopAIEnvironmentResponse:
    effective = resolve_shop_llm_environment(shop_id)

    runtime_uses_default = record is None
    if record is not None and record.provider:
        normalized_record_provider = str(record.provider).strip().lower()
        if normalized_record_provider != effective.provider:
            runtime_uses_default = True

    if effective.subscription_tier in {"premium", "enterprise"}:
        environment_name = "Premium AI Agent Environment"
        environment_summary = (
            "Your shop runs on ZeroQwait's managed AI environment for faster owner assistance, "
            "agent orchestration, and approval-driven operations."
        )
        operating_mode = "Managed premium environment"
        status_label = "Premium managed AI"
        capabilities = [
            "Faster managed responses for owner workflows",
            "Receptionist, finance, and HR agent coordination behind the scenes",
            "Approval-driven actions for higher impact operational changes",
        ]
        experience_notes = [
            "ZeroQwait handles model selection, routing, and upgrades automatically.",
            "Your team works in a simple AI operations workspace instead of model settings.",
            "Improvements roll out centrally without requiring shop-level reconfiguration.",
        ]
    else:
        environment_name = "Local AI Environment"
        environment_summary = (
            "Your shop uses the included local AI environment for day-to-day assistance, queue guidance, "
            "and owner support without extra technical setup."
        )
        operating_mode = "Local environment"
        status_label = "Included local AI"
        capabilities = [
            "Local AI support for owner and receptionist workflows",
            "Built-in queue and service guidance for daily operations",
            "Simple shop experience with ZeroQwait managing the AI stack in the background",
        ]
        experience_notes = [
            "ZeroQwait manages the underlying AI setup automatically.",
            "Premium upgrades move your shop into the managed high-speed AI environment.",
            "Owner settings stay focused on operations instead of infrastructure controls.",
        ]

    return ShopAIEnvironmentResponse(
        shop_id=shop_id,
        subscription_tier=effective.subscription_tier,
        environment_name=environment_name,
        environment_summary=environment_summary,
        operating_mode=operating_mode,
        status_label=status_label,
        uses_default=runtime_uses_default,
        can_customize=False,
        capabilities=capabilities,
        experience_notes=experience_notes,
    )


def _get_record(db: Session, shop_id: int) -> Optional[ShopLLMConfig]:
    return db.query(ShopLLMConfig).filter(ShopLLMConfig.shop_id == shop_id).first()


@router.get("/shops/{shop_id}/llm-settings", response_model=ShopAIEnvironmentResponse)
def get_shop_llm_settings(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_shop_access(shop_id, current_user, require_owner=True)
    record = _get_record(db, shop_id)
    return _build_response(shop_id, record)


@router.put("/shops/{shop_id}/llm-settings")
def upsert_shop_llm_settings(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
):
    check_shop_access(shop_id, current_user, require_owner=True)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=OWNER_AI_SETTINGS_LOCKED_MESSAGE)


@router.delete("/shops/{shop_id}/llm-settings")
def delete_shop_llm_settings(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
):
    check_shop_access(shop_id, current_user, require_owner=True)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=OWNER_AI_SETTINGS_LOCKED_MESSAGE)