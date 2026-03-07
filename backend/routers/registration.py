"""
Registration Router — API endpoints for the interactive registration flow.

Endpoints:
  POST /api/agent/registration/start       — Start a new registration session
  POST /api/agent/registration/step        — Submit a form step
  GET  /api/agent/registration/state       — Get current registration state
  POST /api/agent/registration/validate/{field} — Real-time field validation
  POST /api/agent/registration/cancel      — Cancel registration
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from registration_agent import registration_agent

logger = logging.getLogger("registration_router")

router = APIRouter()


class RegistrationStartRequest(BaseModel):
    session_id: str
    account_type: Optional[str] = None


class RegistrationStepRequest(BaseModel):
    session_id: str
    data: Dict[str, Any]


class FieldValidateRequest(BaseModel):
    value: str


@router.post("/start")
async def start_registration(request: RegistrationStartRequest):
    """Start a new registration session. Returns the first form_step event."""
    try:
        event = registration_agent.start(
            session_id=request.session_id,
            account_type=request.account_type
        )
        return event
    except Exception as e:
        logger.error(f"Registration start failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/step")
async def process_step(request: RegistrationStepRequest):
    """
    Submit form data for the current step.
    Returns:
      - form_step: next step's form schema (continue)
      - form_done: registration complete {success, message, ...}
      - form_error: session-level error
    """
    try:
        event = registration_agent.process_step(
            session_id=request.session_id,
            field_data=request.data
        )
        return event
    except Exception as e:
        logger.error(f"Registration step failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/state")
async def get_registration_state(session_id: str):
    """Get the current registration state (which step, collected data summary).
    Also returns a form_step payload so frontend can restore the form on refresh."""
    state = registration_agent.get_session(session_id)
    if not state:
        return {"active": False}
    
    # Don't return password in state queries
    safe_data = {k: v for k, v in state.get("data", {}).items() if k != "password"}
    
    # Build the full form_step event so the frontend can restore the form
    form_step = registration_agent._build_form_event(state)
    
    return {
        "active": True,
        "step": state["step"],
        "account_type": state.get("account_type"),
        "data": safe_data,
        "started_at": state.get("started_at"),
        "form_step": form_step
    }


@router.post("/validate/{field}")
async def validate_field(field: str, request: FieldValidateRequest):
    """Real-time field validation (email, username, shop_name availability)."""
    if field not in ("email", "username", "shop_name"):
        raise HTTPException(status_code=400, detail=f"Unsupported field: {field}")
    
    result = registration_agent.validate_field(field, request.value)
    return result


@router.post("/cancel")
async def cancel_registration(request: RegistrationStartRequest):
    """Cancel an active registration session."""
    registration_agent._clear_session(request.session_id)
    return {"message": "Registration cancelled"}
