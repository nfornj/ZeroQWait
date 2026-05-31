import importlib
import asyncio
import os
import sys
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.specialist_graph import SpecialistPlan  # noqa: E402
from agents.supervisor import RoutingDecision, create_supervisor_runnable  # noqa: E402


class _NoopCheckpointerContextManager:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStructuredLLM:
    def __init__(self, payload):
        self._payload = payload

    def invoke(self, _messages):
        return self._payload


class _FakeLLM:
    def __init__(self, payload):
        self._payload = payload

    def with_structured_output(self, _schema):
        return _FakeStructuredLLM(self._payload)


def _load_agent_v2_module():
    sys.modules.pop("routers.agent_v2", None)
    with (
        patch("agents.checkpoints.get_sync_checkpoint_saver", return_value=_NoopCheckpointerContextManager()),
        patch("agents.checkpoints.get_pooled_checkpoint_saver", return_value=InMemorySaver()),
    ):
        return importlib.import_module("routers.agent_v2")


@pytest.fixture(autouse=True)
def _stub_tenant_module_skills():
    with patch("modules.registry.ModuleRegistry.get_combined_agent_skills", return_value=[]):
        yield


def _build_test_app_with_real_graph():
    agent_v2 = _load_agent_v2_module()
    saver = InMemorySaver()
    setattr(agent_v2, "_SUPERVISOR_RUNNABLE", create_supervisor_runnable(checkpointer=saver))
    setattr(agent_v2, "_set_tenant_context_for_shop", lambda _shop_id: None)

    app = FastAPI()
    app.include_router(agent_v2.router)
    app.dependency_overrides[agent_v2.get_current_user] = lambda: {"user_id": 17, "shops": [41]}
    client = TestClient(app)
    return agent_v2, client


def _pending_policy_payload(action, details, *, shop_id=41, mode="require_approval"):
    return {
        "action": action,
        "details": details,
        "shop_id": shop_id,
        "policy_key": f"approval.{action}",
        "policy_mode": mode,
        "category": "finance" if action in {"create_invoice", "record_payment", "process_refund"} else "operations",
        "title": action.replace("_", " ").title(),
        "risk_level": "high" if action == "close_queue" else "medium",
        "urgency": "high" if action == "close_queue" else "normal",
        "summary": "A policy-controlled action is pending.",
        "rationale": "The agent proposed a high-impact operation.",
        "expected_impact": "Shop operations will change after execution.",
    }


def test_reset_checkpoint_thread_if_idle_clears_completed_thread_state():
    agent_v2 = _load_agent_v2_module()
    fake_snapshot = SimpleNamespace(interrupts=(), values={})
    fake_db = Mock()

    with (
        patch.object(agent_v2, "_SUPERVISOR_RUNNABLE", SimpleNamespace(get_state=lambda _config: fake_snapshot)),
        patch.object(agent_v2, "SessionLocal", return_value=fake_db),
    ):
        agent_v2._reset_checkpoint_thread_if_idle(41, 17)

    executed_sql = [str(call.args[0]) for call in fake_db.execute.call_args_list]
    assert any("DELETE FROM checkpoint_writes" in stmt for stmt in executed_sql)
    assert any("DELETE FROM checkpoints" in stmt for stmt in executed_sql)
    assert fake_db.commit.called
    assert fake_db.close.called


def test_reset_checkpoint_thread_if_idle_preserves_pending_interrupt():
    agent_v2 = _load_agent_v2_module()
    fake_snapshot = SimpleNamespace(interrupts=[SimpleNamespace(id="approval_1")], values={})

    with (
        patch.object(agent_v2, "_SUPERVISOR_RUNNABLE", SimpleNamespace(get_state=lambda _config: fake_snapshot)),
        patch.object(agent_v2, "SessionLocal") as session_local,
    ):
        agent_v2._reset_checkpoint_thread_if_idle(41, 17)

    session_local.assert_not_called()


def test_chat_stream_route_resets_idle_checkpoint_thread_before_new_turn():
    agent_v2, client = _build_test_app_with_real_graph()

    def _stream(*_args, **_kwargs):
        yield {"route_to_agent": {"current_agent": "finance"}}
        yield {
            "synthesize_response": {
                "messages": [AIMessage(content="Fresh finance reply")],
                "current_agent": "finance",
                "tool_results": {"status": "ok"},
            }
        }

    fake_snapshot = SimpleNamespace(
        values={
            "messages": [AIMessage(content="Fresh finance reply")],
            "tool_results": {"status": "ok"},
        },
        next=(),
        interrupts=(),
    )
    fake_runnable = SimpleNamespace(
        stream=lambda *_args, **_kwargs: _stream(),
        get_state=lambda _config: fake_snapshot,
    )

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 711,
                "run_id": 811,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 711, "run_id": 811},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(agent_v2, "_finalize_chat_work_context", return_value=None),
        patch.object(agent_v2, "_SUPERVISOR_RUNNABLE", fake_runnable),
        patch.object(agent_v2, "_reset_checkpoint_thread_if_idle", return_value=None) as reset_mock,
    ):
        with client.stream(
            "POST",
            "/api/v2/agent/chat/stream",
            json={"message": "Show this week's revenue trend", "shop_id": 41},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    reset_mock.assert_called_once_with(41, 17)
    assert '"type": "agent_switch", "agent": "finance"' in body
    assert "[DONE]" in body


def test_chat_route_allows_new_message_when_existing_approval_is_pending():
    agent_v2, client = _build_test_app_with_real_graph()
    existing_pending = {
        **_pending_policy_payload("close_queue", {"reason": "Owner requested closure"}),
        "action_id": "interrupt-123",
    }

    def _stream(*_args, **_kwargs):
        yield {
            "synthesize_response": {
                "messages": [AIMessage(content="Here is the finance answer.")],
                "current_agent": "finance",
            }
        }

    fake_snapshot = SimpleNamespace(
        values={"messages": [AIMessage(content="Here is the finance answer.")]},
        next=(),
        interrupts=(),
    )
    fake_runnable = SimpleNamespace(stream=Mock(side_effect=_stream), get_state=Mock(return_value=fake_snapshot))

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(agent_v2, "_get_current_pending_approval", return_value=existing_pending),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 501,
                "run_id": 601,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 501, "run_id": 601},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_finalize_chat_work_context", return_value=None),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(agent_v2, "_SUPERVISOR_RUNNABLE", fake_runnable),
    ):
        response = client.post(
            "/api/v2/agent/chat",
            json={"message": "What was today's revenue?", "shop_id": 41},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["approval_required"] is False
    assert payload["pending_action"] is None
    assert payload["response"] == "Here is the finance answer."
    assert payload["metadata"]["goal_id"] == 501
    fake_runnable.stream.assert_called_once()


def test_chat_stream_route_allows_new_message_when_existing_approval_is_pending():
    agent_v2, client = _build_test_app_with_real_graph()
    existing_pending = {
        **_pending_policy_payload("close_queue", {"reason": "Owner requested closure"}),
        "action_id": "interrupt-123",
    }

    def _stream(*_args, **_kwargs):
        yield {
            "synthesize_response": {
                "messages": [AIMessage(content="Fresh finance stream reply")],
                "current_agent": "finance",
            }
        }

    fake_snapshot = SimpleNamespace(
        values={"messages": [AIMessage(content="Fresh finance stream reply")]},
        next=(),
        interrupts=(),
    )
    fake_runnable = SimpleNamespace(stream=Mock(side_effect=_stream), get_state=Mock(return_value=fake_snapshot))

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(agent_v2, "_get_current_pending_approval", return_value=existing_pending),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 502,
                "run_id": 602,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 502, "run_id": 602},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_finalize_chat_work_context", return_value=None),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(agent_v2, "_SUPERVISOR_RUNNABLE", fake_runnable),
    ):
        with client.stream(
            "POST",
            "/api/v2/agent/chat/stream",
            json={"message": "Please review the shop performance dashboard", "shop_id": 41},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "approval_required"' not in body
    assert '"has_text": true' in body
    assert "[DONE]" in body
    fake_runnable.stream.assert_called_once()


def test_chat_route_answers_service_customer_counts_without_graph():
    agent_v2, client = _build_test_app_with_real_graph()
    fake_runnable = SimpleNamespace(stream=Mock(side_effect=AssertionError("direct finance fastpath should not run graph")))

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2.finance_tools,
            "_local_service_customer_counts",
            return_value={
                "window_display": "today",
                "total_customers": 6,
                "services": [
                    {"service_name": "Haircut", "customer_count": 4, "revenue": 140.0},
                    {"service_name": "Beard Trim", "customer_count": 2, "revenue": 50.0},
                ],
            },
        ) as service_counts,
        patch.object(agent_v2, "_SUPERVISOR_RUNNABLE", fake_runnable),
    ):
        response = client.post(
            "/api/v2/agent/chat",
            json={"message": "can you show me number of customers attended for each services?", "shop_id": 41},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"] == "finance"
    assert payload["approval_required"] is False
    assert "Haircut: 4 customers" in payload["response"]
    assert payload["metadata"]["direct_fastpath"] == "service_customer_counts"
    service_counts.assert_called_once_with(
        41,
        query="can you show me number of customers attended for each services?",
        limit=20,
    )
    fake_runnable.stream.assert_not_called()


def test_chat_stream_route_answers_service_customer_counts_without_graph():
    agent_v2, client = _build_test_app_with_real_graph()
    fake_runnable = SimpleNamespace(stream=Mock(side_effect=AssertionError("direct finance fastpath should not run graph")))

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2.finance_tools,
            "_local_service_customer_counts",
            return_value={
                "window_display": "today",
                "total_customers": 3,
                "services": [{"service_name": "Haircut", "customer_count": 3, "revenue": 105.0}],
            },
        ) as service_counts,
        patch.object(agent_v2, "_SUPERVISOR_RUNNABLE", fake_runnable),
    ):
        with client.stream(
            "POST",
            "/api/v2/agent/chat/stream",
            json={"message": "customers attended by service", "shop_id": 41},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "service_customer_counts" in body
    assert "Haircut" in body
    assert "[DONE]" in body
    service_counts.assert_called_once_with(41, query="customers attended by service", limit=20)
    fake_runnable.stream.assert_not_called()


def test_chat_stream_route_answers_service_count_window_followup_without_graph():
    agent_v2, client = _build_test_app_with_real_graph()
    fake_runnable = SimpleNamespace(stream=Mock(side_effect=AssertionError("direct finance follow-up should not run graph")))

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2._redis,
            "tenant_get",
            return_value={"operation": "service_customer_counts", "last_message": "customers attended by service"},
        ),
        patch.object(agent_v2._redis, "tenant_set", return_value=True),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(
            agent_v2.finance_tools,
            "_local_service_customer_counts",
            return_value={
                "window_display": "last 70 days",
                "total_customers": 12,
                "services": [{"service_name": "Haircut", "customer_count": 12, "revenue": 420.0}],
            },
        ) as service_counts,
        patch.object(agent_v2, "_SUPERVISOR_RUNNABLE", fake_runnable),
    ):
        with client.stream(
            "POST",
            "/api/v2/agent/chat/stream",
            json={"message": "what about last 70 days?", "shop_id": 41},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "service_customer_counts" in body
    assert "last 70 days" in body
    assert "Haircut" in body
    assert "[DONE]" in body
    service_counts.assert_called_once_with(41, query="what about last 70 days?", limit=20)
    fake_runnable.stream.assert_not_called()


def test_chat_stream_route_answers_bare_days_followup_without_graph():
    agent_v2, client = _build_test_app_with_real_graph()
    fake_runnable = SimpleNamespace(stream=Mock(side_effect=AssertionError("direct finance follow-up should not run graph")))

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2._redis,
            "tenant_get",
            return_value={"operation": "service_customer_counts", "last_message": "customers attended by service"},
        ),
        patch.object(agent_v2._redis, "tenant_set", return_value=True),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(
            agent_v2.finance_tools,
            "_local_service_customer_counts",
            return_value={
                "window_display": "last 90 days",
                "total_customers": 12,
                "services": [{"service_name": "Haircut", "customer_count": 12, "revenue": 420.0}],
            },
        ) as service_counts,
        patch.object(agent_v2, "_SUPERVISOR_RUNNABLE", fake_runnable),
    ):
        with client.stream(
            "POST",
            "/api/v2/agent/chat/stream",
            json={"message": "90 days", "shop_id": 41},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "service_customer_counts" in body
    assert "last 90 days" in body
    assert "[DONE]" in body
    service_counts.assert_called_once_with(41, query="90 days", limit=20)
    fake_runnable.stream.assert_not_called()


def test_chat_stream_route_answers_today_revenue_without_graph():
    agent_v2, client = _build_test_app_with_real_graph()
    fake_runnable = SimpleNamespace(stream=Mock(side_effect=AssertionError("direct finance fastpath should not run graph")))

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2.finance_tools,
            "_local_daily_revenue",
            return_value={
                "date": "2026-05-02",
                "total_revenue": 245.0,
                "completed_services": 7,
                "total_customers": 9,
                "average_transaction": 35.0,
            },
        ) as daily_revenue,
        patch.object(agent_v2, "_SUPERVISOR_RUNNABLE", fake_runnable),
    ):
        with client.stream(
            "POST",
            "/api/v2/agent/chat/stream",
            json={"message": "how much revenue today?", "shop_id": 41},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "daily_revenue" in body
    assert "245.0" in body
    assert "[DONE]" in body
    daily_revenue.assert_called_once_with(41, None)
    fake_runnable.stream.assert_not_called()


def test_chat_stream_route_answers_top_services_without_graph():
    agent_v2, client = _build_test_app_with_real_graph()
    fake_runnable = SimpleNamespace(stream=Mock(side_effect=AssertionError("direct finance fastpath should not run graph")))

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2.finance_tools,
            "_local_top_services",
            return_value={
                "window_display": "last 30 days",
                "services": [
                    {"name": "Full Service", "completed_services": 5, "revenue": 225.0},
                    {"name": "Fade", "completed_services": 4, "revenue": 140.0},
                ],
            },
        ) as top_services,
        patch.object(agent_v2, "_SUPERVISOR_RUNNABLE", fake_runnable),
    ):
        with client.stream(
            "POST",
            "/api/v2/agent/chat/stream",
            json={"message": "top services by revenue", "shop_id": 41},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "top_services" in body
    assert "Full Service" in body
    assert "225.0" in body
    assert "[DONE]" in body
    top_services.assert_called_once_with(41, 5)
    fake_runnable.stream.assert_not_called()


def test_chat_route_runs_supervisor_graph_through_finance_specialist():
    agent_v2, client = _build_test_app_with_real_graph()

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 501,
                "run_id": 601,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 501, "run_id": 601},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_finalize_chat_work_context", return_value=None),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch("agents.supervisor.get_conversation_history", return_value=[]),
        patch("agents.supervisor.save_conversation_turn", return_value=None),
        patch("agents.supervisor._classify_intent_fastpath", return_value=None),
        patch(
            "agents.supervisor.get_llm",
            return_value=_FakeLLM(
                RoutingDecision(
                    thought_process="Revenue question routes to finance.",
                    next_agent="finance",
                    is_followup=False,
                )
            ),
        ),
        patch(
            "agents.specialist_graph.get_llm",
            return_value=_FakeLLM(
                SpecialistPlan(
                    operation="daily_revenue",
                    arguments={"date": "2026-04-20"},
                    requires_clarification=False,
                    clarification_question="",
                    rationale="Single-day finance question.",
                )
            ),
        ),
        patch("agents.finance._build_finance_fast_plan", return_value=None),
        patch(
            "agents.tools.finance_tools.daily_revenue",
            return_value={
                "date": "2026-04-20",
                "total_revenue": 245.0,
                "completed_services": 7,
                "average_transaction": 35.0,
                "shop_id": 41,
            },
        ) as mock_daily_revenue,
    ):
        response = client.post(
            "/api/v2/agent/chat",
            json={"message": "What was yesterday's revenue?", "shop_id": 41},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"] == "finance"
    assert payload["approval_required"] is False
    assert payload["response"] == "Revenue for 2026-04-20 was $245.00 across 7 completed services. Average transaction was $35.00."
    assert payload["metadata"]["goal_id"] == 501
    assert payload["metadata"]["run_id"] == 601
    mock_daily_revenue.assert_called_once_with(41, "2026-04-20")


def test_chat_route_fast_paths_close_queue_to_receptionist_without_supervisor_llm():
    agent_v2, client = _build_test_app_with_real_graph()

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 741,
                "run_id": 841,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 741, "run_id": 841},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_finalize_chat_work_context", side_effect=lambda **kwargs: kwargs["pending_action"]),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch("agents.supervisor.get_conversation_history", return_value=[]),
        patch("agents.supervisor.save_conversation_turn", return_value=None),
        patch(
            "agents.supervisor.get_llm",
            side_effect=AssertionError("explicit close_queue requests should bypass supervisor LLM routing"),
        ),
        patch(
            "agents.specialist_graph.get_llm",
            return_value=_FakeLLM(
                SpecialistPlan(
                    operation="close_queue",
                    arguments={"reason": "Owner requested closure"},
                    requires_clarification=False,
                    clarification_question="",
                    rationale="Queue closure is a receptionist operation.",
                )
            ),
        ),
        patch(
            "agents.specialist_graph.approval_policy.build_pending_approval",
            return_value=_pending_policy_payload(
                "close_queue",
                {"reason": "Owner requested closure"},
            ),
        ),
    ):
        response = client.post(
            "/api/v2/agent/chat",
            json={"message": "Close the queue for today", "shop_id": 41},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"] == "receptionist"
    assert payload["approval_required"] is True
    assert payload["pending_action"]["action"] == "close_queue"


def test_chat_route_returns_explicit_504_when_sync_invoke_times_out():
    agent_v2, client = _build_test_app_with_real_graph()

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(agent_v2, "_get_current_pending_approval", return_value=None),
        patch.object(agent_v2, "_reset_checkpoint_thread_if_idle", return_value=None),
        patch.object(agent_v2, "_create_chat_work_context", return_value={
            "goal_id": 742,
            "run_id": 842,
            "execution_mode": "interactive",
            "trigger_source": "chat",
            "event_context": {"trigger_source": "chat", "goal_id": 742, "run_id": 842},
        }),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_invoke_supervisor_sync", AsyncMock(side_effect=asyncio.TimeoutError())),
    ):
        response = client.post(
            "/api/v2/agent/chat",
            json={"message": "Create an invoice for one haircut at 35 dollars", "shop_id": 41},
        )

    assert response.status_code == 504
    assert response.json()["detail"] == "Sync agent request timed out. Use /api/v2/agent/chat/stream for long-running requests."


def test_chat_stream_route_emits_finance_events_and_done():
    agent_v2, client = _build_test_app_with_real_graph()

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 701,
                "run_id": 801,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 701, "run_id": 801},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(agent_v2, "_finalize_chat_work_context", side_effect=lambda **kwargs: kwargs["pending_action"]),
        patch("agents.supervisor.get_conversation_history", return_value=[]),
        patch("agents.supervisor.save_conversation_turn", return_value=None),
        patch(
            "agents.supervisor.get_llm",
            return_value=_FakeLLM(
                RoutingDecision(
                    thought_process="Revenue question routes to finance.",
                    next_agent="finance",
                    is_followup=False,
                )
            ),
        ),
        patch(
            "agents.specialist_graph.get_llm",
            return_value=_FakeLLM(
                SpecialistPlan(
                    operation="daily_revenue",
                    arguments={"date": "2026-04-20"},
                    requires_clarification=False,
                    clarification_question="",
                    rationale="Single-day finance question.",
                )
            ),
        ),
        patch(
            "agents.tools.finance_tools.daily_revenue",
            return_value={
                "date": "2026-04-20",
                "total_revenue": 245.0,
                "completed_services": 7,
                "average_transaction": 35.0,
                "shop_id": 41,
            },
        ),
    ):
        with client.stream(
            "POST",
            "/api/v2/agent/chat/stream",
            json={"message": "What was yesterday's revenue?", "shop_id": 41},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "agent_switch", "agent": "finance"' in body
    assert '"type": "thinking_step"' in body
    assert '"type": "reasoning"' in body
    assert 'Revenue question routes to finance.' in body
    assert 'Single-day finance question.' in body
    assert '"type": "tool_call", "tool": "daily_revenue"' in body
    assert '"type": "tool_result"' in body
    assert '"type": "suggestions"' in body
    assert '"type": "text"' in body
    assert '"type": "stream_status", "status": "completed"' in body
    assert "[DONE]" in body


def test_chat_stream_route_emits_finance_table_for_list_requests():
    agent_v2, client = _build_test_app_with_real_graph()

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_create_chat_work_context", return_value={"goal_id": 1, "run_id": 2, "execution_mode": "interactive", "trigger_source": "chat", "event_context": {}}),
        patch.object(agent_v2, "_finalize_chat_work_context", side_effect=lambda **kwargs: kwargs["pending_action"]),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(agent_v2.db_interface, "get_shop_live_wait_metrics", return_value={}),
        patch("agents.supervisor.get_conversation_history", return_value=[]),
        patch("agents.supervisor.save_conversation_turn", return_value=None),
        patch(
            "agents.supervisor.get_llm",
            return_value=_FakeLLM(
                RoutingDecision(
                    next_agent="finance",
                    thought_process="Finance question",
                    is_followup=False,
                )
            ),
        ),
        patch(
            "agents.specialist_graph.create_chat_model",
            return_value=_FakeLLM(
                SpecialistPlan(
                    operation="trend_summary",
                    arguments={"query": "give me as a list for last 10 days"},
                    requires_clarification=False,
                    clarification_question="",
                    rationale="Trend request.",
                )
            ),
        ),
        patch(
            "agents.tools.finance_tools.trend_summary",
            return_value={
                "window": "last_10_days",
                "total_revenue": 835.0,
                "completed_services": 37,
                "best_period": "2026-04-21",
                "best_period_revenue": 420.0,
                "preferred_presentation": "table",
                "points": [
                    {"period": "2026-04-21", "revenue": 420.0, "customers": 10, "completed_services": 12},
                    {"period": "2026-04-22", "revenue": 215.0, "customers": 7, "completed_services": 9},
                ],
            },
        ),
    ):
        with client.stream(
            "POST",
            "/api/v2/agent/chat/stream",
            json={"message": "give me as a list for last 10 days", "shop_id": 41},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "table"' in body
    assert '"title": "Revenue by Day (last 10 days)"' in body
    assert '"rowIdKey": "period"' in body
    assert '"type": "stream_status", "status": "completed"' in body


def test_chat_stream_route_emits_multi_series_finance_chart_for_trend_requests():
    agent_v2, client = _build_test_app_with_real_graph()

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_create_chat_work_context", return_value={"goal_id": 1, "run_id": 2, "execution_mode": "interactive", "trigger_source": "chat", "event_context": {}}),
        patch.object(agent_v2, "_finalize_chat_work_context", side_effect=lambda **kwargs: kwargs["pending_action"]),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(agent_v2.db_interface, "get_shop_live_wait_metrics", return_value={}),
        patch("agents.supervisor.get_conversation_history", return_value=[]),
        patch("agents.supervisor.save_conversation_turn", return_value=None),
        patch(
            "agents.supervisor.get_llm",
            return_value=_FakeLLM(
                RoutingDecision(
                    next_agent="finance",
                    thought_process="Finance question",
                    is_followup=False,
                )
            ),
        ),
        patch(
            "agents.specialist_graph.create_chat_model",
            return_value=_FakeLLM(
                SpecialistPlan(
                    operation="trend_summary",
                    arguments={"query": "show this week's revenue trend and customers"},
                    requires_clarification=False,
                    clarification_question="",
                    rationale="Trend request.",
                )
            ),
        ),
        patch(
            "agents.tools.finance_tools.trend_summary",
            return_value={
                "window": "this_week",
                "total_revenue": 835.0,
                "completed_services": 37,
                "best_period": "2026-04-21",
                "best_period_revenue": 420.0,
                "points": [
                    {"period": "2026-04-21", "revenue": 420.0, "customers": 10, "completed_services": 12},
                    {"period": "2026-04-22", "revenue": 215.0, "customers": 7, "completed_services": 9},
                    {"period": "2026-04-23", "revenue": 200.0, "customers": 5, "completed_services": 8},
                ],
            },
        ),
    ):
        with client.stream(
            "POST",
            "/api/v2/agent/chat/stream",
            json={"message": "show this week's revenue trend and customers", "shop_id": 41},
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "chart"' in body
    assert '"title": "Revenue Trend (this week)"' in body
    assert '"description": "Revenue and customers by period."' in body
    assert '"key": "revenue"' in body
    assert '"key": "customers"' in body
    assert '"showLegend": true' in body
    assert '"showGrid": true' in body
    assert '"type": "stream_status", "status": "completed"' in body


def test_approve_route_resumes_pending_action_from_real_interrupt():
    agent_v2, client = _build_test_app_with_real_graph()

    def _passthrough_finalize(**kwargs):
        return kwargs["pending_action"]

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 901,
                "run_id": 902,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 901, "run_id": 902},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_finalize_chat_work_context", side_effect=_passthrough_finalize),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(agent_v2.db_interface, "get_shop_live_wait_metrics", return_value={}),
        patch.object(agent_v2, "_record_approval_decision", return_value=None),
        patch("agents.supervisor.get_conversation_history", return_value=[]),
        patch("agents.supervisor.save_conversation_turn", return_value=None),
        patch(
            "agents.supervisor.get_llm",
            return_value=_FakeLLM(
                RoutingDecision(
                    thought_process="Queue closure routes to booking.",
                    next_agent="booking",
                    is_followup=False,
                )
            ),
        ),
        patch(
            "agents.specialist_graph.get_llm",
            return_value=_FakeLLM(
                SpecialistPlan(
                    operation="close_queue",
                    arguments={"reason": "Owner requested closure"},
                    requires_clarification=False,
                    clarification_question="",
                    rationale="High-impact queue closure.",
                )
            ),
        ),
        patch(
            "agents.specialist_graph.approval_policy.build_pending_approval",
            return_value=_pending_policy_payload(
                "close_queue",
                {"reason": "Owner requested closure"},
            ),
        ),
    ):
        create_response = client.post(
            "/api/v2/agent/chat",
            json={"message": "Close the queue for today", "shop_id": 41},
        )

        assert create_response.status_code == 200
        pending_action = create_response.json()["pending_action"]
        assert pending_action["action"] == "close_queue"
        assert pending_action["action_id"]

        approve_response = client.post(
            "/api/v2/agent/approve",
            json={
                "shop_id": 41,
                "action_id": pending_action["action_id"],
                "approved": False,
                "reason": "Not today",
            },
        )

    assert approve_response.status_code == 200
    payload = approve_response.json()
    assert payload["status"] == "rejected"
    assert payload["agent"] == "receptionist"
    assert payload["tool_results"]["status"] == "rejected"
    assert payload["message"] == "Action 'close_queue' was rejected. No changes were made."


def test_chat_route_auto_executes_policy_allowed_action():
    agent_v2, client = _build_test_app_with_real_graph()

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 951,
                "run_id": 952,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 951, "run_id": 952},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_finalize_chat_work_context", return_value=None),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch("agents.supervisor.get_conversation_history", return_value=[]),
        patch("agents.supervisor.save_conversation_turn", return_value=None),
        patch(
            "agents.supervisor.get_llm",
            return_value=_FakeLLM(
                RoutingDecision(
                    thought_process="Queue closure routes to booking.",
                    next_agent="booking",
                    is_followup=False,
                )
            ),
        ),
        patch(
            "agents.specialist_graph.get_llm",
            return_value=_FakeLLM(
                SpecialistPlan(
                    operation="close_queue",
                    arguments={"reason": "Owner requested closure"},
                    requires_clarification=False,
                    clarification_question="",
                    rationale="High-impact queue closure.",
                )
            ),
        ),
        patch(
            "agents.specialist_graph.approval_policy.build_pending_approval",
            return_value=_pending_policy_payload(
                "close_queue",
                {"reason": "Owner requested closure"},
                mode="allow",
            ),
        ),
        patch(
            "agents.supervisor.booking_tools.close_queue",
            return_value={"message": "Queue closed. Reason: Owner requested closure", "status": "closed"},
        ),
    ):
        response = client.post(
            "/api/v2/agent/chat",
            json={"message": "Close the queue for today", "shop_id": 41},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"] == "receptionist"
    assert payload["approval_required"] is False
    assert payload["pending_action"] is None
    assert "executed this automatically" in payload["response"]


def test_list_policies_route_returns_catalog_with_modes():
    agent_v2, client = _build_test_app_with_real_graph()

    policies = [
        {
            "action": "close_queue",
            "policy_key": "approval.close_queue",
            "category": "operations",
            "title": "Close Active Queue",
            "risk_level": "high",
            "urgency": "high",
            "default_mode": "require_approval",
            "supported_modes": ["allow", "require_approval", "forbid", "notify_only", "silent"],
            "mode": "notify_only",
            "explicit": True,
        }
    ]

    with patch.object(agent_v2, "_list_policy_payload", return_value=policies) as mock_list:
        response = client.get("/api/v2/agent/policies", params={"shop_id": 41})

    assert response.status_code == 200
    payload = response.json()
    assert payload["shop_id"] == 41
    assert payload["user_id"] == 17
    assert payload["policies"] == policies
    mock_list.assert_called_once_with(41)


def test_update_policy_route_persists_mode_change():
    agent_v2, client = _build_test_app_with_real_graph()

    updated_policy = {
        "action": "close_queue",
        "policy_key": "approval.close_queue",
        "category": "operations",
        "title": "Close Active Queue",
        "risk_level": "high",
        "urgency": "high",
        "default_mode": "require_approval",
        "supported_modes": ["allow", "require_approval", "forbid", "notify_only", "silent"],
        "mode": "allow",
        "explicit": True,
    }

    with patch.object(agent_v2, "_upsert_policy_payload", return_value=updated_policy) as mock_upsert:
        response = client.put(
            "/api/v2/agent/policies/approval.close_queue",
            json={"shop_id": 41, "mode": "allow"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy"] == updated_policy
    mock_upsert.assert_called_once_with(
        shop_id=41,
        policy_key="approval.close_queue",
        mode="allow",
        policy_value=None,
        config=None,
    )


def test_chat_route_requires_approval_for_finance_invoice_creation():
    agent_v2, client = _build_test_app_with_real_graph()

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 961,
                "run_id": 962,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 961, "run_id": 962},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_finalize_chat_work_context", side_effect=lambda **kwargs: kwargs["pending_action"]),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(agent_v2.db_interface, "get_shop_live_wait_metrics", return_value={}),
        patch("agents.supervisor.get_conversation_history", return_value=[]),
        patch("agents.supervisor.save_conversation_turn", return_value=None),
        patch(
            "agents.supervisor.get_llm",
            return_value=_FakeLLM(
                RoutingDecision(
                    thought_process="Invoice creation routes to finance.",
                    next_agent="finance",
                    is_followup=False,
                )
            ),
        ),
        patch(
            "agents.specialist_graph.get_llm",
            return_value=_FakeLLM(
                SpecialistPlan(
                    operation="create_invoice",
                    arguments={"service_name": "Haircut", "unit_price": 35.0, "quantity": 2},
                    requires_clarification=False,
                    clarification_question="",
                    rationale="Owner wants to create a bill.",
                )
            ),
        ),
        patch(
            "agents.specialist_graph.approval_policy.build_pending_approval",
            return_value=_pending_policy_payload(
                "create_invoice",
                {"service_name": "Haircut", "unit_price": 35.0, "quantity": 2},
            ),
        ),
    ):
        response = client.post(
            "/api/v2/agent/chat",
            json={"message": "Create an invoice for two haircuts at 35 each", "shop_id": 41},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"] == "finance"
    assert payload["approval_required"] is True
    assert payload["pending_action"]["action"] == "create_invoice"
    assert payload["pending_action"]["policy_key"] == "approval.create_invoice"


def test_approve_route_executes_finance_invoice_action():
    agent_v2, client = _build_test_app_with_real_graph()

    def _passthrough_finalize(**kwargs):
        return kwargs["pending_action"]

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 971,
                "run_id": 972,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 971, "run_id": 972},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_finalize_chat_work_context", side_effect=_passthrough_finalize),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(agent_v2.db_interface, "get_shop_live_wait_metrics", return_value={}),
        patch.object(agent_v2, "_record_approval_decision", return_value=None),
        patch("agents.supervisor.get_conversation_history", return_value=[]),
        patch("agents.supervisor.save_conversation_turn", return_value=None),
        patch(
            "agents.supervisor.get_llm",
            return_value=_FakeLLM(
                RoutingDecision(
                    thought_process="Invoice creation routes to finance.",
                    next_agent="finance",
                    is_followup=False,
                )
            ),
        ),
        patch(
            "agents.specialist_graph.get_llm",
            return_value=_FakeLLM(
                SpecialistPlan(
                    operation="create_invoice",
                    arguments={"service_name": "Haircut", "unit_price": 35.0, "quantity": 2},
                    requires_clarification=False,
                    clarification_question="",
                    rationale="Owner wants to create a bill.",
                )
            ),
        ),
        patch(
            "agents.specialist_graph.approval_policy.build_pending_approval",
            return_value=_pending_policy_payload(
                "create_invoice",
                {"service_name": "Haircut", "unit_price": 35.0, "quantity": 2},
            ),
        ),
        patch(
            "agents.supervisor.finance_tools.create_invoice",
            return_value={"message": "Invoice INV-100 created successfully", "status": "created", "invoice_id": 100},
        ),
    ):
        create_response = client.post(
            "/api/v2/agent/chat",
            json={"message": "Create an invoice for two haircuts at 35 each", "shop_id": 41},
        )
        assert create_response.status_code == 200

        pending_action = create_response.json()["pending_action"]
        approve_response = client.post(
            "/api/v2/agent/approve",
            json={
                "shop_id": 41,
                "action_id": pending_action["action_id"],
                "approved": True,
                "reason": "Approved",
            },
        )

    assert approve_response.status_code == 200
    payload = approve_response.json()
    assert payload["status"] == "approved"
    assert payload["agent"] == "finance"
    assert payload["tool_results"]["status"] == "created"
    assert payload["tool_results"]["invoice_id"] == 100


def test_chat_route_requires_approval_for_finance_refund():
    agent_v2, client = _build_test_app_with_real_graph()

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 981,
                "run_id": 982,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 981, "run_id": 982},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_finalize_chat_work_context", side_effect=lambda **kwargs: kwargs["pending_action"]),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(agent_v2.db_interface, "get_shop_live_wait_metrics", return_value={}),
        patch("agents.supervisor.get_conversation_history", return_value=[]),
        patch("agents.supervisor.save_conversation_turn", return_value=None),
        patch(
            "agents.supervisor.get_llm",
            return_value=_FakeLLM(
                RoutingDecision(
                    thought_process="Refunds route to finance.",
                    next_agent="finance",
                    is_followup=False,
                )
            ),
        ),
        patch(
            "agents.specialist_graph.get_llm",
            return_value=_FakeLLM(
                SpecialistPlan(
                    operation="process_refund",
                    arguments={"payment_id": 77, "refund_amount": 12.5, "reason": "Duplicate charge"},
                    requires_clarification=False,
                    clarification_question="",
                    rationale="Owner wants to issue a refund.",
                )
            ),
        ),
        patch(
            "agents.specialist_graph.approval_policy.build_pending_approval",
            return_value=_pending_policy_payload(
                "process_refund",
                {"payment_id": 77, "refund_amount": 12.5, "reason": "Duplicate charge"},
            ),
        ),
    ):
        response = client.post(
            "/api/v2/agent/chat",
            json={"message": "Refund payment 77 for 12.50 because it was a duplicate charge", "shop_id": 41},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"] == "finance"
    assert payload["approval_required"] is True
    assert payload["pending_action"]["action"] == "process_refund"
    assert payload["pending_action"]["policy_key"] == "approval.process_refund"


def test_approve_route_executes_finance_refund_action():
    agent_v2, client = _build_test_app_with_real_graph()

    def _passthrough_finalize(**kwargs):
        return kwargs["pending_action"]

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 991,
                "run_id": 992,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 991, "run_id": 992},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_finalize_chat_work_context", side_effect=_passthrough_finalize),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(agent_v2.db_interface, "get_shop_live_wait_metrics", return_value={}),
        patch.object(agent_v2, "_record_approval_decision", return_value=None),
        patch("agents.supervisor.get_conversation_history", return_value=[]),
        patch("agents.supervisor.save_conversation_turn", return_value=None),
        patch(
            "agents.supervisor.get_llm",
            return_value=_FakeLLM(
                RoutingDecision(
                    thought_process="Refunds route to finance.",
                    next_agent="finance",
                    is_followup=False,
                )
            ),
        ),
        patch(
            "agents.specialist_graph.get_llm",
            return_value=_FakeLLM(
                SpecialistPlan(
                    operation="process_refund",
                    arguments={"payment_id": 77, "refund_amount": 12.5, "reason": "Duplicate charge"},
                    requires_clarification=False,
                    clarification_question="",
                    rationale="Owner wants to issue a refund.",
                )
            ),
        ),
        patch(
            "agents.specialist_graph.approval_policy.build_pending_approval",
            return_value=_pending_policy_payload(
                "process_refund",
                {"payment_id": 77, "refund_amount": 12.5, "reason": "Duplicate charge"},
            ),
        ),
        patch(
            "agents.supervisor.finance_tools.process_refund",
            return_value={
                "message": "Refunded payment 77 for $12.50. Payment is now partially refunded.",
                "status": "partially_refunded",
                "payment_id": 77,
                "refund_amount": 12.5,
            },
        ),
    ):
        create_response = client.post(
            "/api/v2/agent/chat",
            json={"message": "Refund payment 77 for 12.50 because it was a duplicate charge", "shop_id": 41},
        )
        assert create_response.status_code == 200

        pending_action = create_response.json()["pending_action"]
        approve_response = client.post(
            "/api/v2/agent/approve",
            json={
                "shop_id": 41,
                "action_id": pending_action["action_id"],
                "approved": True,
                "reason": "Approved",
            },
        )

    assert approve_response.status_code == 200
    payload = approve_response.json()
    assert payload["status"] == "approved"
    assert payload["agent"] == "finance"
    assert payload["tool_results"]["status"] == "partially_refunded"
    assert payload["tool_results"]["payment_id"] == 77


def test_history_route_returns_checkpoint_messages_after_chat():
    agent_v2, client = _build_test_app_with_real_graph()

    with (
        patch.object(agent_v2._redis, "check_rate_limit", return_value=True),
        patch.object(
            agent_v2,
            "_create_chat_work_context",
            return_value={
                "goal_id": 1001,
                "run_id": 1002,
                "execution_mode": "interactive",
                "trigger_source": "chat",
                "event_context": {"trigger_source": "chat", "goal_id": 1001, "run_id": 1002},
            },
        ),
        patch.object(agent_v2, "_build_memory_context", return_value=""),
        patch.object(agent_v2, "_finalize_chat_work_context", side_effect=lambda **kwargs: kwargs["pending_action"]),
        patch.object(agent_v2, "_persist_chat_turn_memory", return_value=None),
        patch.object(agent_v2.db_interface, "get_shop_live_wait_metrics", return_value={}),
        patch("agents.supervisor.get_conversation_history", return_value=[]),
        patch("agents.supervisor.save_conversation_turn", return_value=None),
        patch(
            "agents.supervisor.get_llm",
            return_value=_FakeLLM(
                RoutingDecision(
                    thought_process="Revenue question routes to finance.",
                    next_agent="finance",
                    is_followup=False,
                )
            ),
        ),
        patch(
            "agents.specialist_graph.get_llm",
            return_value=_FakeLLM(
                SpecialistPlan(
                    operation="daily_revenue",
                    arguments={"date": "2026-04-20"},
                    requires_clarification=False,
                    clarification_question="",
                    rationale="Single-day finance question.",
                )
            ),
        ),
        patch(
            "agents.tools.finance_tools.daily_revenue",
            return_value={
                "date": "2026-04-20",
                "total_revenue": 245.0,
                "completed_services": 7,
                "average_transaction": 35.0,
                "shop_id": 41,
            },
        ),
    ):
        chat_response = client.post(
            "/api/v2/agent/chat",
            json={"message": "What was yesterday's revenue?", "shop_id": 41},
        )
        assert chat_response.status_code == 200

        history_response = client.get("/api/v2/agent/history", params={"shop_id": 41})

    assert history_response.status_code == 200
    payload = history_response.json()
    assert payload["checkpoint_id"] == "tenant_41_17"
    assert payload["pending"] == []
    assert payload["messages"] == [
        {"role": "user", "content": "What was yesterday's revenue?"},
        {
            "role": "assistant",
            "content": "Revenue for 2026-04-20 was $245.00 across 7 completed services. Average transaction was $35.00.",
        },
    ]


def test_pending_route_returns_enriched_pending_approvals():
    agent_v2, client = _build_test_app_with_real_graph()

    pending_payload = [
        {
            "action_id": "interrupt-123",
            "action": "close_queue",
            "title": "Close Active Queue",
            "risk_level": "high",
            "details": {"reason": "Team is at capacity"},
        }
    ]

    with (
        patch.object(agent_v2.db_interface, "get_shop_live_wait_metrics", return_value={"queue_length": 6, "estimated_wait_minutes": 35}),
        patch.object(agent_v2, "_get_pending_approval_payload", return_value=pending_payload) as mock_pending,
    ):
        response = client.get("/api/v2/agent/pending", params={"shop_id": 41})

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"pending": pending_payload}
    mock_pending.assert_called_once_with(41, 17, metrics={"queue_length": 6, "estimated_wait_minutes": 35})


def test_history_route_falls_back_to_stored_conversation_when_checkpoint_empty():
    agent_v2, client = _build_test_app_with_real_graph()

    with (
        patch.object(agent_v2._SUPERVISOR_RUNNABLE, "get_state", return_value=None),
        patch.object(agent_v2, "get_conversation_history", return_value=[
            {"role": "user", "content": "Show me today's queue summary"},
            {"role": "assistant", "content": "You currently have 4 people waiting."},
        ]),
        patch.object(agent_v2, "_get_pending_approval_payload", return_value=[]),
    ):
        response = client.get("/api/v2/agent/history", params={"shop_id": 41})

    assert response.status_code == 200
    payload = response.json()
    assert payload["messages"] == [
        {"role": "user", "content": "Show me today's queue summary"},
        {"role": "assistant", "content": "You currently have 4 people waiting."},
    ]


def test_build_memory_context_uses_latest_uploaded_document_for_referential_prompt():
    agent_v2 = _load_agent_v2_module()

    latest_document_memories = [
        {
            "id": 401,
            "memory_type": "document",
            "content": "From finance_trend_41_this_month.csv (chunk 1/2): month,revenue\n2026-04,6400",
            "source": "finance_trend_41_this_month.csv",
            "memory_meta": {
                "document_id": 22,
                "filename": "finance_trend_41_this_month.csv",
                "relative_path": "finance_trend_41_this_month.csv",
                "chunk_index": 1,
            },
            "created_at": "2026-04-27T02:10:00",
        },
        {
            "id": 402,
            "memory_type": "document",
            "content": "From finance_trend_41_this_month.csv (chunk 2/2): 2026-05,7100",
            "source": "finance_trend_41_this_month.csv",
            "memory_meta": {
                "document_id": 22,
                "filename": "finance_trend_41_this_month.csv",
                "relative_path": "finance_trend_41_this_month.csv",
                "chunk_index": 2,
            },
            "created_at": "2026-04-27T02:10:01",
        },
        {
            "id": 301,
            "memory_type": "document",
            "content": "From older_report.csv (chunk 1/1): old data",
            "source": "older_report.csv",
            "memory_meta": {
                "document_id": 11,
                "filename": "older_report.csv",
                "relative_path": "older_report.csv",
                "chunk_index": 1,
            },
            "created_at": "2026-04-20T02:10:00",
        },
    ]

    with (
        patch.object(agent_v2.db_interface, "search_agent_memories", return_value=[]),
        patch.object(agent_v2.db_interface, "get_agent_memories", side_effect=[[], latest_document_memories]),
        patch.object(agent_v2.db_interface, "touch_agent_memory") as mock_touch,
    ):
        context = agent_v2._build_memory_context(41, 17, "summarize the document")

    assert "finance_trend_41_this_month.csv" in context
    assert "older_report.csv" not in context
    assert "month,revenue" in context
    assert [call.args for call in mock_touch.call_args_list] == [(401,), (402,)]


def test_pending_route_falls_back_to_persisted_approval_requests_when_checkpoint_empty():
    agent_v2, client = _build_test_app_with_real_graph()

    approval_request = SimpleNamespace(
        id=7001,
        external_action_id="approval-7001",
        shop_id=41,
        action_type="close_queue",
        request_payload={
            "action": "close_queue",
            "details": {"reason": "Team is at capacity"},
            "shop_id": 41,
            "policy_key": "approval.close_queue",
            "policy_mode": "require_approval",
            "category": "operations",
        },
        requested_at=datetime(2026, 4, 21, 9, 15, 0),
    )

    fake_repo = SimpleNamespace(list_pending_approval_requests=lambda shop_id: [approval_request])
    fake_db = SimpleNamespace(close=lambda: None)

    with (
        patch.object(agent_v2._SUPERVISOR_RUNNABLE, "get_state", return_value=None),
        patch.object(agent_v2.db_interface, "get_shop_live_wait_metrics", return_value={"queue_length": 6, "estimated_wait_minutes": 35}),
        patch.object(agent_v2, "SessionLocal", return_value=fake_db),
        patch.object(agent_v2, "AgentWorkRepository", return_value=fake_repo),
    ):
        response = client.get("/api/v2/agent/pending", params={"shop_id": 41})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["pending"]) == 1
    pending = payload["pending"][0]
    assert pending["action_id"] == "approval-7001"
    assert pending["approval_request_id"] == 7001
    assert pending["action"] == "close_queue"
    assert pending["policy_key"] == "approval.close_queue"
    assert pending["created_at"] == "2026-04-21T09:15:00"


def test_pending_route_dedupes_matching_persisted_request_when_interrupt_is_active():
    agent_v2, client = _build_test_app_with_real_graph()

    pending_action = {
        "action": "add_employee",
        "details": {
            "name": "Jordan Browser",
            "email": "jordan.browser@example.com",
            "phone": "555-555-1200",
            "role": "stylist",
        },
        "shop_id": 41,
        "policy_key": "approval.add_employee",
        "policy_mode": "require_approval",
        "category": "staffing",
        "title": "Add Team Member",
        "risk_level": "medium",
        "urgency": "normal",
        "summary": "Add Jordan Browser to the shop team.",
        "reason": "Create a new employee record for Jordan Browser.",
        "expected_impact": "The person will appear in team management and become eligible for shift assignment.",
        "recommended_decision": "Approve if the hiring or onboarding decision is final.",
    }
    fake_snapshot = SimpleNamespace(
        values={"pending_approval": pending_action},
        interrupts=[SimpleNamespace(id="interrupt-123")],
    )
    approval_request = SimpleNamespace(
        id=2,
        external_action_id=None,
        shop_id=41,
        action_type="add_employee",
        request_payload=pending_action,
        requested_at=datetime(2026, 4, 21, 9, 15, 0),
    )

    fake_repo = SimpleNamespace(list_pending_approval_requests=lambda shop_id: [approval_request])
    fake_db = SimpleNamespace(close=lambda: None)

    with (
        patch.object(agent_v2._SUPERVISOR_RUNNABLE, "get_state", return_value=fake_snapshot),
        patch.object(agent_v2, "SessionLocal", return_value=fake_db),
        patch.object(agent_v2, "AgentWorkRepository", return_value=fake_repo),
    ):
        response = client.get("/api/v2/agent/pending", params={"shop_id": 41})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["pending"]) == 1
    assert payload["pending"][0]["action_id"] == "interrupt-123"


def test_record_approval_decision_matches_pending_request_by_payload_when_action_id_missing():
    agent_v2 = _load_agent_v2_module()

    pending_action = {
        "action": "add_employee",
        "details": {
            "name": "Jordan Browser",
            "email": "jordan.browser@example.com",
            "phone": "555-555-1200",
            "role": "stylist",
        },
        "shop_id": 41,
        "title": "Add Team Member",
    }
    approval_request = SimpleNamespace(
        id=2,
        external_action_id=None,
        goal_id=11,
        run_id=12,
        request_payload=pending_action,
        action_type="add_employee",
    )
    fake_repo = SimpleNamespace(
        get_pending_approval_by_action_id=lambda shop_id, action_id: None,
        list_pending_approval_requests=lambda shop_id: [approval_request],
        decide_approval_request=Mock(),
        update_goal_status=Mock(),
        update_run_status=Mock(),
    )
    fake_db = SimpleNamespace(commit=Mock(), refresh=Mock(), close=Mock())

    with (
        patch.object(agent_v2, "SessionLocal", return_value=fake_db),
        patch.object(agent_v2, "AgentWorkRepository", return_value=fake_repo),
    ):
        agent_v2._record_approval_decision(
            shop_id=41,
            action_id="interrupt-123",
            pending_action=pending_action,
            approved=True,
            reason=None,
            user_id=17,
            resumed={
                "messages": [AIMessage(content="Approval received. Action executed successfully.")],
                "current_agent": "hr",
                "tool_results": {"status": "approved"},
            },
        )

    assert approval_request.external_action_id == "interrupt-123"
    fake_repo.decide_approval_request.assert_called_once()
    fake_repo.update_goal_status.assert_called_once()
    fake_repo.update_run_status.assert_called_once()


def test_resume_persisted_approval_matches_placeholder_action_id():
    agent_v2 = _load_agent_v2_module()

    approval_request = SimpleNamespace(
        id=2,
        external_action_id=None,
        shop_id=41,
        action_type="add_employee",
        requested_by_agent="hr",
        request_payload={
            "action": "add_employee",
            "details": {
                "name": "Jordan Browser",
                "email": "jordan.browser@example.com",
                "phone": "555-555-1200",
                "role": "stylist",
            },
            "shop_id": 41,
        },
    )
    fake_repo = SimpleNamespace(
        get_pending_approval_by_action_id=lambda shop_id, action_id: None,
        list_pending_approval_requests=lambda shop_id: [approval_request],
    )
    fake_db = SimpleNamespace(close=lambda: None)

    with (
        patch.object(agent_v2, "SessionLocal", return_value=fake_db),
        patch.object(agent_v2, "AgentWorkRepository", return_value=fake_repo),
        patch("agents.supervisor._execute_approved_action", return_value={"message": "Employee created", "status": "approved"}),
    ):
        resumed = agent_v2._resume_persisted_approval(
            shop_id=41,
            action_id="approval-request-2",
            approved=True,
            reason=None,
            user_id=17,
        )

    assert resumed is not None
    assert resumed["tool_results"]["message"] == "Employee created"


def test_briefing_route_returns_snapshot_with_pending_actions():
    agent_v2, client = _build_test_app_with_real_graph()

    cached_snapshot = {
        "generated_at": "2026-04-21T08:30:00Z",
        "source": "cache",
        "metrics": {
            "queue_length": 4,
            "estimated_wait_minutes": 20,
            "people_being_served": 1,
            "active_services": 3,
            "active_employees": 2,
            "today_revenue": 420.0,
            "today_transactions": 12,
            "weekly_revenue": 2100.0,
        },
    }
    pending_payload = [
        {
            "action_id": "interrupt-456",
            "action": "assign_shift",
            "title": "Assign Employee Shift",
            "risk_level": "medium",
            "details": {"user_id": 12, "date": "2026-04-21", "start_time": "09:00", "end_time": "17:00"},
        }
    ]
    built_briefing = {
        "shop_id": 41,
        "shop_name": "North Barbers",
        "generated_at": "2026-04-21T08:30:00Z",
        "source": "cache",
        "summary": "North Barbers currently has 4 people waiting.",
        "metrics": {
            "queue_length": 4,
            "estimated_wait_minutes": 20,
            "people_being_served": 1,
            "active_employees": 2,
            "active_services": 3,
            "pending_approvals": 1,
            "today_revenue": 420.0,
            "today_transactions": 12,
            "weekly_revenue": 2100.0,
        },
        "alerts": [{"severity": "info", "title": "Owner decisions are waiting", "body": "You have 1 approval request that can unblock agent work.", "created_at": "2026-04-21T08:30:00Z"}],
        "alert_history": [{"severity": "warning", "title": "Queue pressure is building", "body": "There are 4 people waiting.", "created_at": "2026-04-21T08:00:00Z"}],
        "recommendations": ["Review pending approvals first so agent work is not blocked."],
        "actions": [{"label": "Review approvals", "prompt": "Show my pending approvals."}],
    }

    with (
        patch.object(agent_v2.db_interface, "get_shop_by_id", return_value={"id": 41, "name": "North Barbers"}),
        patch.object(agent_v2, "get_cached_shop_briefing_snapshot", return_value=cached_snapshot),
        patch.object(agent_v2, "refresh_shop_briefing_cache", return_value=None),
        patch.object(agent_v2.db_interface, "get_shop_live_wait_metrics", return_value={"queue_length": 4, "estimated_wait_minutes": 20, "people_being_served": 1}),
        patch.object(agent_v2, "_get_pending_approval_payload", return_value=pending_payload),
        patch.object(agent_v2, "get_shop_alert_history", return_value=built_briefing["alert_history"]),
        patch.object(agent_v2, "build_owner_briefing", return_value=dict(built_briefing)) as mock_build,
    ):
        response = client.get("/api/v2/agent/briefing", params={"shop_id": 41})

    assert response.status_code == 200
    payload = response.json()
    assert payload["shop_id"] == 41
    assert payload["shop_name"] == "North Barbers"
    assert payload["pending"] == pending_payload
    assert payload["metrics"]["pending_approvals"] == 1
    mock_build.assert_called_once()


def test_feed_route_returns_persisted_notifications():
    agent_v2, client = _build_test_app_with_real_graph()

    notifications = [
        SimpleNamespace(
            id=301,
            notification_type="policy_action_executed",
            title="Queue auto-closed by policy",
            message="The receptionist closed intake automatically under the current policy.",
            severity="warning",
            status="unread",
            created_at=datetime(2026, 4, 21, 10, 45, 0),
            payload={"action": "close_queue", "shop_id": 41},
        ),
        SimpleNamespace(
            id=302,
            notification_type="finance_summary_ready",
            title="Weekly summary ready",
            message="This week's finance summary is ready to review.",
            severity="info",
            status="unread",
            created_at=datetime(2026, 4, 21, 10, 50, 0),
            payload={"report": "weekly_summary", "shop_id": 41},
        ),
    ]

    fake_repo = SimpleNamespace(list_recent_notifications=lambda shop_id, limit=25: notifications[:limit])
    fake_db = SimpleNamespace(close=lambda: None)

    with (
        patch.object(agent_v2, "SessionLocal", return_value=fake_db),
        patch.object(agent_v2, "AgentWorkRepository", return_value=fake_repo),
    ):
        response = client.get("/api/v2/agent/feed", params={"shop_id": 41, "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert [event["id"] for event in payload["events"]] == ["notification_301", "notification_302"]
    assert payload["events"][0]["type"] == "approval_decision"
    assert payload["events"][0]["notification_id"] == 301
    assert payload["events"][1]["type"] == "system"


def test_briefing_route_includes_recent_notifications():
    agent_v2, client = _build_test_app_with_real_graph()

    built_briefing = {
        "shop_id": 41,
        "shop_name": "North Barbers",
        "generated_at": "2026-04-21T08:30:00Z",
        "source": "cache",
        "summary": "North Barbers currently has 4 people waiting.",
        "metrics": {
            "queue_length": 4,
            "estimated_wait_minutes": 20,
            "people_being_served": 1,
            "active_employees": 2,
            "active_services": 3,
            "pending_approvals": 0,
            "today_revenue": 420.0,
            "today_transactions": 12,
            "weekly_revenue": 2100.0,
        },
        "alerts": [],
        "alert_history": [],
        "recommendations": [],
        "actions": [],
    }
    recent_notifications = [{
        "id": "notification_401",
        "type": "system",
        "title": "Weekly summary ready",
        "description": "This week's finance summary is ready to review.",
        "timestamp": "2026-04-21T10:50:00",
        "payload": {"report": "weekly_summary", "shop_id": 41},
    }]

    with (
        patch.object(agent_v2.db_interface, "get_shop_by_id", return_value={"id": 41, "name": "North Barbers"}),
        patch.object(agent_v2, "get_cached_shop_briefing_snapshot", return_value={"generated_at": "2026-04-21T08:30:00Z", "source": "cache", "metrics": {}}),
        patch.object(agent_v2.db_interface, "get_shop_live_wait_metrics", return_value={}),
        patch.object(agent_v2.db_interface, "get_shop_services", return_value=[]),
        patch.object(agent_v2.db_interface, "get_shop_employees", return_value=[]),
        patch.object(agent_v2, "_get_pending_approval_payload", return_value=[]),
        patch.object(agent_v2, "get_shop_alert_history", return_value=[]),
        patch.object(agent_v2, "build_owner_briefing", return_value=dict(built_briefing)),
        patch.object(agent_v2, "_get_notification_feed_payload", return_value=recent_notifications),
    ):
        response = client.get("/api/v2/agent/briefing", params={"shop_id": 41})

    assert response.status_code == 200
    payload = response.json()
    assert payload["recent_notifications"] == recent_notifications


def test_mark_notification_read_route_returns_updated_notification():
    agent_v2, client = _build_test_app_with_real_graph()

    updated_notification = SimpleNamespace(
        id=301,
        notification_type="policy_action_executed",
        title="Queue auto-closed by policy",
        message="The receptionist closed intake automatically under the current policy.",
        severity="warning",
        status="read",
        created_at=datetime(2026, 4, 21, 10, 45, 0),
        payload={"action": "close_queue", "shop_id": 41},
    )
    fake_repo = SimpleNamespace(mark_notification_read_for_shop=lambda notification_id, shop_id: updated_notification)
    fake_db = SimpleNamespace(close=lambda: None)

    with (
        patch.object(agent_v2, "SessionLocal", return_value=fake_db),
        patch.object(agent_v2, "AgentWorkRepository", return_value=fake_repo),
    ):
        response = client.post("/api/v2/agent/notifications/301/read", json={"shop_id": 41})

    assert response.status_code == 200
    payload = response.json()
    assert payload["notification"]["notification_id"] == 301
    assert payload["notification"]["status"] == "read"


def test_mark_all_notifications_read_route_returns_updated_count():
    agent_v2, client = _build_test_app_with_real_graph()

    fake_repo = SimpleNamespace(mark_all_notifications_read=lambda shop_id: 3)
    fake_db = SimpleNamespace(close=lambda: None)

    with (
        patch.object(agent_v2, "SessionLocal", return_value=fake_db),
        patch.object(agent_v2, "AgentWorkRepository", return_value=fake_repo),
    ):
        response = client.post("/api/v2/agent/notifications/read-all", json={"shop_id": 41})

    assert response.status_code == 200
    assert response.json() == {"updated": 3}
