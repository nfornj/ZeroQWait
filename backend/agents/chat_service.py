"""
Chat session helpers — approval tracking, work-context persistence, memory writes.

Extracted from backend/routers/agent_v2.py to keep the HTTP boundary file focused
on FastAPI routing concerns.
"""

import json
import logging
from typing import Any, Dict, List, Optional, cast

from langchain_core.messages import AIMessage

from agents.briefings import enrich_pending_approval_payload
from agents.checkpoints import build_checkpoint_config
from agents.state import AgentState
from database import SessionLocal
from db_interface import DatabaseInterface
from modules.agent.models import ApprovalStatus, GoalSource, GoalStatus, RunStatus
from modules.agent.work_repository import AgentWorkRepository

logger = logging.getLogger(__name__)
db_interface = DatabaseInterface()


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------

def _thread_id(shop_id: int, user_id: int) -> str:
    """Canonical LangGraph checkpoint thread ID for a tenant."""
    return f"tenant_{shop_id}_{user_id}"


def _state_last_text(state_values: Dict[str, Any]) -> str:
    messages = state_values.get("messages") or []
    if not messages:
        return ""
    final_message = messages[-1]
    return getattr(final_message, "content", str(final_message))


# ---------------------------------------------------------------------------
# Approval fingerprinting
# ---------------------------------------------------------------------------

def _pending_approval_fingerprint(payload: Optional[Dict[str, Any]]) -> Optional[str]:
    if not payload:
        return None

    action = str(payload.get("action") or "").strip().lower()
    if not action:
        return None

    details = payload.get("details") or {}
    if not isinstance(details, dict):
        details = {"value": details}

    try:
        details_key = json.dumps(details, sort_keys=True, default=str)
    except TypeError:
        details_key = json.dumps({key: str(value) for key, value in details.items()}, sort_keys=True)

    return f"{action}::{details_key}"


def _find_matching_pending_approval_request(
    repo: AgentWorkRepository,
    *,
    shop_id: int,
    action_id: Optional[str] = None,
    pending_action: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    normalized_action_id = str(action_id or "").strip()
    if normalized_action_id:
        approval = repo.get_pending_approval_by_action_id(shop_id, normalized_action_id)
        if approval is not None:
            return approval
        if normalized_action_id.startswith("approval-request-"):
            request_id = normalized_action_id.removeprefix("approval-request-")
            for pending_approval in repo.list_pending_approval_requests(shop_id):
                if str(getattr(pending_approval, "id", "")) == request_id:
                    return pending_approval

    pending_fingerprint = _pending_approval_fingerprint(pending_action)
    if not pending_fingerprint:
        return None

    for approval in repo.list_pending_approval_requests(shop_id):
        request_payload = dict(getattr(approval, "request_payload", None) or {})
        if _pending_approval_fingerprint(request_payload) == pending_fingerprint:
            return approval

    return None


# ---------------------------------------------------------------------------
# Pending-approval payload helpers
# ---------------------------------------------------------------------------

def _pending_payload_from_request(
    approval_request: Any,
    *,
    metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    request_payload = dict(getattr(approval_request, "request_payload", None) or {})
    action_id = str(
        request_payload.get("action_id")
        or getattr(approval_request, "external_action_id", None)
        or f"approval-request-{getattr(approval_request, 'id', 'unknown')}"
    )
    payload = enrich_pending_approval_payload(
        {
            **request_payload,
            "action_id": action_id,
            "action": request_payload.get("action") or getattr(approval_request, "action_type", "approval_required"),
            "details": dict(request_payload.get("details") or {}),
            "shop_id": int(request_payload.get("shop_id") or getattr(approval_request, "shop_id")),
        },
        metrics=metrics,
    )
    payload["approval_request_id"] = getattr(approval_request, "id", None)
    requested_at = getattr(approval_request, "requested_at", None)
    if requested_at is not None:
        payload["created_at"] = requested_at.isoformat()
    return payload


def _get_pending_approval_payload(
    shop_id: int,
    user_id: int,
    metrics: Optional[Dict[str, Any]] = None,
    *,
    runnable: Any = None,
) -> list[Dict[str, Any]]:
    """Return current pending approval payloads for a tenant thread.

    ``runnable`` must be passed by the caller when a checkpoint snapshot is
    needed (agent_v2 passes ``_SUPERVISOR_RUNNABLE``). Without it the
    in-flight checkpoint state is skipped and only persisted DB requests are
    returned.
    """
    pending: list[Dict[str, Any]] = []
    seen_action_ids: set[str] = set()
    seen_fingerprints: set[str] = set()

    if runnable is not None:
        checkpoint_config = build_checkpoint_config(shop_id, user_id)
        snapshot = runnable.get_state(checkpoint_config)
        if snapshot and snapshot.interrupts:
            values = cast(Dict[str, Any], snapshot.values or {})
            pending_approval = values.get("pending_approval")
            interrupt_id = getattr(snapshot.interrupts[0], "id", None)
            if pending_approval:
                checkpoint_payload = enrich_pending_approval_payload(
                    {
                        **pending_approval,
                        "action_id": interrupt_id,
                        "action": pending_approval.get("action"),
                        "details": pending_approval.get("details", {}),
                        "shop_id": pending_approval.get("shop_id", shop_id),
                    },
                    metrics=metrics,
                )
                pending.append(checkpoint_payload)
                if checkpoint_payload.get("action_id"):
                    seen_action_ids.add(str(checkpoint_payload["action_id"]))
                checkpoint_fingerprint = _pending_approval_fingerprint(checkpoint_payload)
                if checkpoint_fingerprint:
                    seen_fingerprints.add(checkpoint_fingerprint)

    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        for approval_request in repo.list_pending_approval_requests(shop_id):
            repo_payload = _pending_payload_from_request(approval_request, metrics=metrics)
            repo_action_id = str(repo_payload.get("action_id") or "")
            if repo_action_id and repo_action_id in seen_action_ids:
                continue
            repo_fingerprint = _pending_approval_fingerprint(repo_payload)
            if repo_fingerprint and repo_fingerprint in seen_fingerprints:
                continue
            pending.append(repo_payload)
            if repo_action_id:
                seen_action_ids.add(repo_action_id)
            if repo_fingerprint:
                seen_fingerprints.add(repo_fingerprint)
    except Exception as exc:
        logger.warning("Unable to load persisted approval requests for shop %s: %s", shop_id, exc)
    finally:
        db.close()

    return pending


def _get_current_pending_approval(
    shop_id: int,
    user_id: int,
    *,
    runnable: Any = None,
) -> Optional[Dict[str, Any]]:
    metrics = db_interface.get_shop_live_wait_metrics(shop_id) or {}
    pending = _get_pending_approval_payload(shop_id, user_id, metrics, runnable=runnable)
    return pending[0] if pending else None


def _build_pending_approval_block_message(pending_action: Dict[str, Any]) -> str:
    action_title = str(
        pending_action.get("title")
        or pending_action.get("action")
        or "this action"
    ).strip()
    return (
        f"You already have a pending approval for '{action_title}'. "
        "Approve or reject it before sending another request."
    )


# ---------------------------------------------------------------------------
# Chat turn memory
# ---------------------------------------------------------------------------

def _persist_chat_turn_memory(
    *,
    shop_id: int,
    user_id: int,
    user_message: str,
    assistant_response: str,
    route: str,
) -> None:
    """Best-effort persistence for tenant-scoped owner chat memory."""
    try:
        db_interface.add_agent_memory(
            shop_id=shop_id,
            user_id=user_id,
            memory_type="chat_user",
            content=user_message,
            source=route,
            importance_score=0.6,
            memory_meta={"role": "user"},
        )
        db_interface.add_agent_memory(
            shop_id=shop_id,
            user_id=user_id,
            memory_type="chat_assistant",
            content=assistant_response,
            source=route,
            importance_score=0.7,
            memory_meta={"role": "assistant"},
        )
    except Exception as e:
        logger.warning("Agent memory persistence failed (non-fatal): %s", str(e))


# ---------------------------------------------------------------------------
# Work-context tracking (goals + runs)
# ---------------------------------------------------------------------------

def _build_work_title(message: str, fallback: str = "Owner request") -> str:
    normalized = " ".join((message or "").split())
    if not normalized:
        return fallback
    return normalized if len(normalized) <= 120 else f"{normalized[:117]}..."


def _create_chat_work_context(shop_id: int, user_id: int, message: str, *, is_voice: bool = False) -> Dict[str, Any]:
    trigger_source = "voice_chat" if is_voice else "chat"
    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        goal = repo.create_goal(
            shop_id=shop_id,
            created_by_user_id=user_id,
            source=GoalSource.CHAT,
            goal_type="owner_request",
            title=_build_work_title(message),
            description=message,
            autonomy_policy="interactive",
            context={"message": message, "trigger_source": trigger_source},
        )
        goal_id = cast(int, getattr(goal, "id"))
        run = repo.create_run(
            shop_id=shop_id,
            goal_id=goal_id,
            triggered_by_user_id=user_id,
            run_type="chat",
            trigger_source=trigger_source,
            execution_mode="interactive",
            graph_thread_id=_thread_id(shop_id, user_id),
            current_agent="supervisor",
            input_payload={"message": message},
            event_context={"trigger_source": trigger_source},
        )
        run_id = cast(int, getattr(run, "id"))
        return {
            "goal_id": goal_id,
            "run_id": run_id,
            "execution_mode": "interactive",
            "trigger_source": trigger_source,
            "event_context": {"trigger_source": trigger_source, "goal_id": goal_id, "run_id": run_id},
        }
    finally:
        db.close()


def _persist_approval_request(
    *,
    shop_id: int,
    user_id: int,
    goal_id: int,
    run_id: int,
    routed_agent: str,
    pending_action: Dict[str, Any],
) -> Dict[str, Any]:
    action_id = str(pending_action.get("action_id") or "").strip()
    details = pending_action.get("details") or {}
    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        approval = _find_matching_pending_approval_request(
            repo,
            shop_id=shop_id,
            action_id=action_id or None,
            pending_action=pending_action,
        )
        if approval is not None and action_id and not getattr(approval, "external_action_id", None):
            approval.external_action_id = action_id
            db.commit()
            db.refresh(approval)
        if approval is None:
            approval = repo.create_approval_request(
                external_action_id=action_id or None,
                shop_id=shop_id,
                goal_id=goal_id,
                run_id=run_id,
                requested_by_user_id=user_id,
                requested_by_agent=routed_agent or "supervisor",
                action_type=str(pending_action.get("action") or "approval_required"),
                title=_build_work_title(
                    str(pending_action.get("title") or details.get("title") or pending_action.get("action") or "Approval required"),
                    fallback="Approval required",
                ),
                rationale=str(pending_action.get("rationale") or details.get("reason") or details.get("rationale") or "") or None,
                expected_impact=str(pending_action.get("expected_impact") or details.get("impact") or details.get("expected_impact") or "") or None,
                urgency=str(details.get("urgency") or pending_action.get("urgency") or "normal"),
                request_payload=pending_action,
            )
        enriched = dict(pending_action)
        enriched["approval_request_id"] = approval.id
        return enriched
    finally:
        db.close()


def _finalize_chat_work_context(
    *,
    shop_id: int,
    user_id: int,
    goal_id: int,
    run_id: int,
    routed_agent: str,
    response_text: str,
    tool_results: Optional[Dict[str, Any]],
    approval_required: bool,
    pending_action: Optional[Dict[str, Any]],
    conversation_messages: Optional[list] = None,
) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        output_payload = {
            "response": response_text,
            "agent": routed_agent,
            "tool_results": tool_results or {},
        }
        if approval_required:
            repo.update_goal_status(goal_id, GoalStatus.WAITING_APPROVAL, summary=response_text or "Waiting for owner approval")
            repo.update_run_status(
                run_id,
                RunStatus.WAITING_APPROVAL,
                output_payload=output_payload,
                current_agent=routed_agent or "supervisor",
            )
            if pending_action:
                return _persist_approval_request(
                    shop_id=shop_id,
                    user_id=user_id,
                    goal_id=goal_id,
                    run_id=run_id,
                    routed_agent=routed_agent or "supervisor",
                    pending_action=pending_action,
                )
            return pending_action

        repo.update_goal_status(goal_id, GoalStatus.COMPLETED, summary=response_text)
        repo.update_run_status(
            run_id,
            RunStatus.COMPLETED,
            output_payload=output_payload,
            current_agent=routed_agent or "supervisor",
        )

        # Fire-and-forget commitment scan on the conversation tail.
        if conversation_messages:
            try:
                from .commitment_scanner import schedule_commitment_scan
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        schedule_commitment_scan(
                            shop_id=shop_id,
                            run_id=run_id,
                            messages=conversation_messages,
                        )
                    )
                except RuntimeError:
                    # No running loop — invoke the sync fallback directly
                    from .commitment_scanner import scan_and_persist_commitments_sync
                    scan_and_persist_commitments_sync(
                        shop_id=shop_id,
                        run_id=run_id,
                        messages=conversation_messages,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("commitment scan dispatch failed: %s", exc)

        return pending_action
    finally:
        db.close()


def _record_approval_decision(
    *,
    shop_id: int,
    action_id: Optional[str],
    pending_action: Optional[Dict[str, Any]],
    approved: bool,
    reason: Optional[str],
    user_id: int,
    resumed: Dict[str, Any],
) -> None:
    if not action_id and not pending_action:
        return
    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        approval = _find_matching_pending_approval_request(
            repo,
            shop_id=shop_id,
            action_id=action_id,
            pending_action=pending_action,
        )
        if approval is None:
            return
        normalized_action_id = str(action_id or "").strip()
        if normalized_action_id and not getattr(approval, "external_action_id", None):
            approval.external_action_id = normalized_action_id
            db.commit()
            db.refresh(approval)
        approval_id = cast(int, getattr(approval, "id"))
        repo.decide_approval_request(
            approval_id,
            status=ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED,
            decided_by_user_id=user_id,
            decision_reason=reason,
            decision_payload={
                "message": _state_last_text(resumed),
                "agent": resumed.get("current_agent", "supervisor"),
                "tool_results": resumed.get("tool_results"),
            },
        )
        goal_id = getattr(approval, "goal_id", None)
        if goal_id is not None:
            repo.update_goal_status(
                int(goal_id),
                GoalStatus.COMPLETED if approved else GoalStatus.CANCELLED,
                summary=_state_last_text(resumed),
            )
        run_id = getattr(approval, "run_id", None)
        if run_id is not None:
            repo.update_run_status(
                int(run_id),
                RunStatus.COMPLETED if approved else RunStatus.CANCELLED,
                output_payload={
                    "message": _state_last_text(resumed),
                    "agent": resumed.get("current_agent", "supervisor"),
                    "tool_results": resumed.get("tool_results"),
                },
                current_agent=resumed.get("current_agent", "supervisor"),
            )
        logger.info(
            "approval_decision shop_id=%s user_id=%s action_id=%s approved=%s",
            shop_id,
            user_id,
            action_id or getattr(approval, "external_action_id", None),
            approved,
        )
    finally:
        db.close()


def _resume_persisted_approval(
    *,
    shop_id: int,
    action_id: Optional[str],
    approved: bool,
    reason: Optional[str],
    user_id: int,
) -> Optional[Dict[str, Any]]:
    if not action_id:
        return None

    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        approval = _find_matching_pending_approval_request(
            repo,
            shop_id=shop_id,
            action_id=action_id,
            pending_action=None,
        )
        if approval is None:
            return None

        pending = dict(getattr(approval, "request_payload", None) or {})
        pending.setdefault("action", getattr(approval, "action_type", None) or "approval_required")
        pending.setdefault("shop_id", shop_id)
        pending.setdefault("details", {})
        routed_agent = str(getattr(approval, "requested_by_agent", None) or "supervisor")
    finally:
        db.close()

    if not approved:
        rejection_text = f"Action '{pending.get('action')}' was rejected. No changes were made."
        return {
            "messages": [AIMessage(content=rejection_text)],
            "current_agent": routed_agent,
            "tool_results": {
                "status": "rejected",
                "action": pending.get("action"),
                "reason": reason,
            },
        }

    from agents.supervisor import _execute_approved_action

    approval_state: AgentState = {
        "messages": [],
        "tenant_id": shop_id,
        "user_id": user_id,
        "current_agent": routed_agent,
        "active_goal_id": None,
        "active_task_id": None,
        "execution_mode": "interactive",
        "autonomy_policy": None,
        "event_context": None,
        "proposed_actions": [],
        "run_summary": None,
        "pending_approval": None,
        "needs_human_input": False,
        "tool_results": None,
        "metadata": {"shop_id": shop_id, "user_id": user_id, "approval_action_id": action_id},
    }

    execution_result = _execute_approved_action(
        approval_state,
        pending,
    )
    if execution_result.get("error"):
        message_text = f"Approval received, but the action failed: {execution_result.get('error')}"
    else:
        result_message = execution_result.get("message") or f"Action '{pending.get('action')}' was executed successfully."
        message_text = f"Approval received. {result_message}"

    return {
        "messages": [AIMessage(content=message_text)],
        "current_agent": routed_agent,
        "tool_results": execution_result,
    }
