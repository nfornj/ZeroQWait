import importlib
import os
import sys
import json
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
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
    with patch("agents.checkpoints.get_sync_checkpoint_saver", return_value=_NoopCheckpointerContextManager()):
        return importlib.import_module("routers.agent_v2")


def _build_test_app_with_real_graph():
    agent_v2 = _load_agent_v2_module()
    saver = InMemorySaver()
    agent_v2._SUPERVISOR_RUNNABLE = create_supervisor_runnable(checkpointer=saver)

    app = FastAPI()
    app.include_router(agent_v2.router)
    app.dependency_overrides[agent_v2.get_current_user] = lambda: {"user_id": 17, "shops": [41]}
    client = TestClient(app)
    return agent_v2, client


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
    assert '"type": "tool_result"' in body
    assert '"type": "suggestions"' in body
    assert '"type": "text"' in body
    assert "[DONE]" in body


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
