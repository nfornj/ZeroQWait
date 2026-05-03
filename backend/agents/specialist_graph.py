from __future__ import annotations

import ast
from datetime import datetime
import json
import logging
import time
from typing import Any, Callable, Dict, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from . import approval_policy
from .llm_factory import create_planner_model


logger = logging.getLogger(__name__)


def create_chat_model(shop_id: int | None, *, temperature: float):
    return create_planner_model(shop_id, temperature=temperature)


def get_llm(shop_id: int | None, *, temperature: float):
    return create_chat_model(shop_id, temperature=temperature)


class SpecialistPlan(BaseModel):
    operation: str = Field(description="Exact operation name chosen from the supported specialist operations.")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments needed for the chosen operation.")
    requires_clarification: bool = Field(default=False, description="True when the request is missing required information.")
    clarification_question: str = Field(default="", description="Short question to ask the owner when clarification is required.")
    rationale: str = Field(default="", description="Brief reason for choosing the operation.")


class SpecialistState(TypedDict, total=False):
    messages: Sequence[BaseMessage]
    current_agent: str
    plan: Dict[str, Any]
    metadata: Dict[str, Any]
    tool_results: Optional[Dict[str, Any]]
    pending_approval: Optional[Dict[str, Any]]
    proposal_message: Optional[str]
    needs_human_input: bool


Executor = Callable[[str, Dict[str, Any], Sequence[BaseMessage]], Dict[str, Any]]
Formatter = Callable[[str, Dict[str, Any]], str]
OperationNormalizer = Callable[[str, Dict[str, Any], Sequence[BaseMessage]], str]
FastPlanBuilder = Callable[[Sequence[BaseMessage]], Optional[Dict[str, Any]]]


def _merge_metadata(state: SpecialistState, updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(state.get("metadata") or {})

    existing_reasoning = list(merged.get("reasoning_events") or [])
    incoming_reasoning = list(updates.get("reasoning_events") or [])
    if existing_reasoning or incoming_reasoning:
        merged["reasoning_events"] = [*existing_reasoning, *incoming_reasoning]

    for key, value in updates.items():
        if key == "reasoning_events":
            continue
        merged[key] = value

    return merged


def _format_operation_name(operation: str) -> str:
    return operation.replace("_", " ").strip()


def _summarize_arguments(arguments: Dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in arguments.items():
        if value in (None, "", [], {}, ()):
            continue
        label = key.replace("_", " ")
        parts.append(f"{label}={value}")
        if len(parts) == 3:
            break
    return ", ".join(parts)


def _build_reasoning_event(event_id: str, text: str, *, tool_name: Optional[str] = None) -> Dict[str, Any]:
    event: Dict[str, Any] = {"id": event_id, "text": text}
    if tool_name:
        event["tool"] = tool_name
    return event


def _latest_user_text(messages: Sequence[BaseMessage]) -> str:
    for message in reversed(list(messages or [])):
        if isinstance(message, HumanMessage):
            return str(message.content)
        if isinstance(message, BaseMessage):
            return str(message.content)
    return ""


def _coerce_bool_like(value: Any) -> Any:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return value


def _recover_specialist_plan(error: Exception) -> Optional[SpecialistPlan]:
    message = str(error)
    start_tag = "<function=SpecialistPlan>"
    end_tag = "</function>"
    start_index = message.find(start_tag)
    if start_index == -1:
        return None

    end_index = message.find(end_tag, start_index + len(start_tag))
    if end_index == -1:
        return None

    raw_payload = message[start_index + len(start_tag):end_index].strip()
    if not raw_payload:
        return None

    normalized_payload = raw_payload.replace("\\'", "'")

    try:
        payload = json.loads(normalized_payload)
    except json.JSONDecodeError:
        try:
            payload = ast.literal_eval(normalized_payload)
        except (SyntaxError, ValueError):
            return None

    if not isinstance(payload, dict):
        return None

    if "requires_clarification" in payload:
        payload["requires_clarification"] = _coerce_bool_like(payload.get("requires_clarification"))
    if not isinstance(payload.get("arguments"), dict):
        payload["arguments"] = {}

    try:
        return SpecialistPlan.model_validate(payload)
    except Exception:
        return None


def build_specialist_runnable(
    *,
    agent_name: str,
    shop_id: int,
    temperature: float,
    planner_instructions: str,
    supported_operations: Sequence[str],
    operation_aliases: Optional[Dict[str, str]] = None,
    operation_normalizer: Optional[OperationNormalizer] = None,
    fast_plan_builder: Optional[FastPlanBuilder] = None,
    executor: Executor,
    formatter: Formatter,
):
    supported_operation_set = set(supported_operations)
    normalized_operation_aliases = {
        str(alias).strip().lower(): str(target).strip()
        for alias, target in dict(operation_aliases or {}).items()
        if str(alias).strip() and str(target).strip()
    }

    def _finalize_plan(plan: Dict[str, Any], messages: Sequence[BaseMessage], *, source: str, started_at: float) -> Dict[str, Any]:
        raw_operation = str(plan.get("operation") or "").strip()
        operation = normalized_operation_aliases.get(raw_operation.lower(), raw_operation)
        if operation_normalizer is not None:
            operation = str(operation_normalizer(operation, plan, messages) or operation).strip()
        if not operation:
            raise ValueError(f"{agent_name} planner returned an empty operation")
        if operation not in supported_operation_set:
            raise ValueError(f"{agent_name} planner returned unsupported operation: {operation}")
        plan["operation"] = operation
        rationale = str(plan.get("rationale") or "").strip()
        reasoning_text = rationale or f"Selected {_format_operation_name(operation)} for this {agent_name} request."
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info("%s planner: source=%s operation=%s took %.1fms", agent_name, source, operation, elapsed_ms)
        return {
            "plan": plan,
            "current_agent": agent_name,
            "metadata": _merge_metadata(
                state={},
                updates={
                    "specialist_operation": operation,
                    "specialist_planner_source": source,
                    "reasoning_events": [
                        _build_reasoning_event(
                            f"{agent_name}_plan",
                            reasoning_text,
                        )
                    ],
                },
            ),
        }

    def plan_request(state: SpecialistState) -> Dict[str, Any]:
        started_at = time.perf_counter()
        messages = list(state.get("messages") or [])
        if not messages:
            raise ValueError(f"{agent_name} planner requires at least one message")

        if fast_plan_builder is not None:
            fast_plan = fast_plan_builder(messages)
            if fast_plan:
                return _finalize_plan(dict(fast_plan), messages, source="fast_path", started_at=started_at)

        llm = get_llm(shop_id, temperature=temperature)
        planner_prompt = (
            f"You are the {agent_name} specialist planner for ZeroQwait. "
            "Pick exactly one supported operation and extract the arguments required to run it.\n\n"
            f"Today is {datetime.now().strftime('%Y-%m-%d')}.\n"
            "Rules:\n"
            "- Choose exactly one operation from the supported list.\n"
            "- If the request lacks required information, set requires_clarification=true and ask one direct question.\n"
            "- Do not invent IDs or dates.\n"
            "- The request is already scoped to the current shop. Never ask for shop_id, tenant_id, queue_id, or queue name unless an operation explicitly requires a record ID such as service_id or appointment_id.\n"
            "- For relative dates like today, yesterday, last week, or this month, convert them into arguments when possible.\n"
            "- Keep rationale short.\n\n"
            f"Supported operations: {', '.join(supported_operations)}\n\n"
            f"Operation guidance:\n{planner_instructions}"
        )

        try:
            decision = llm.with_structured_output(SpecialistPlan).invoke(
                [SystemMessage(content=planner_prompt)] + messages
            )
        except Exception as error:
            recovered_plan = _recover_specialist_plan(error)
            if recovered_plan is None:
                raise

            logger.warning("%s planner recovered from structured-output failure: %s", agent_name, error)
            return _finalize_plan(recovered_plan.model_dump(), messages, source="llm_recovery", started_at=started_at)

        return _finalize_plan(decision.model_dump(), messages, source="llm", started_at=started_at)

    def execute_operation(state: SpecialistState) -> Dict[str, Any]:
        started_at = time.perf_counter()
        plan = dict(state.get("plan") or {})
        messages = list(state.get("messages") or [])
        if not plan:
            raise ValueError(f"{agent_name} execute_operation called without a plan")

        if bool(plan.get("requires_clarification")):
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.info("%s executor: skipped tool execution for clarification in %.1fms", agent_name, elapsed_ms)
            return {
                "current_agent": agent_name,
                "metadata": _merge_metadata(
                    state,
                    {
                        "specialist_operation": str(plan.get("operation") or ""),
                        "reasoning_events": [
                            _build_reasoning_event(
                                f"{agent_name}_clarification",
                                "I need one missing detail before I can run this request.",
                            )
                        ],
                    },
                ),
                "needs_human_input": False,
                "pending_approval": None,
                "tool_results": None,
            }

        operation = str(plan.get("operation"))
        arguments = dict(plan.get("arguments") or {})
        result = executor(operation, arguments, messages)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "%s executor: operation=%s took %.1fms (approval=%s, error=%s)",
            agent_name,
            operation,
            elapsed_ms,
            bool(result.get("requires_approval")),
            bool(result.get("error")),
        )

        if result.get("requires_approval"):
            return {
                "current_agent": agent_name,
                "metadata": _merge_metadata(
                    state,
                    {
                        "specialist_operation": operation,
                        "reasoning_events": [
                            _build_reasoning_event(
                                f"{agent_name}_approval",
                                result.get("message") or f"{_format_operation_name(operation).capitalize()} requires approval before it can run.",
                                tool_name=operation,
                            )
                        ],
                    },
                ),
                "pending_approval": approval_policy.build_pending_approval(
                    shop_id=shop_id,
                    action=str(result.get("action") or "approval_required"),
                    details=dict(result.get("details") or {}),
                ),
                "proposal_message": result.get("message"),
                "needs_human_input": True,
                "tool_results": None,
            }

        argument_summary = _summarize_arguments(arguments)
        execution_reasoning = f"Running {_format_operation_name(operation)}"
        if argument_summary:
            execution_reasoning = f"{execution_reasoning} with {argument_summary}."
        else:
            execution_reasoning = f"{execution_reasoning}."

        return {
            "current_agent": agent_name,
            "metadata": _merge_metadata(
                state,
                {
                    "specialist_operation": operation,
                    "reasoning_events": [
                        _build_reasoning_event(
                            f"{agent_name}_execute",
                            execution_reasoning,
                            tool_name=operation,
                        )
                    ],
                },
            ),
            "tool_results": result,
            "pending_approval": None,
            "needs_human_input": False,
        }

    def format_response(state: SpecialistState) -> Dict[str, Any]:
        messages = list(state.get("messages") or [])
        plan = dict(state.get("plan") or {})

        if bool(plan.get("requires_clarification")):
            content = str(plan.get("clarification_question") or "What information should I use?")
        elif state.get("pending_approval"):
            content = str(state.get("proposal_message") or "This action needs owner approval before I can execute it.")
        else:
            operation = str(plan.get("operation") or "")
            tool_results = dict(state.get("tool_results") or {})
            content = formatter(operation, tool_results)

        return {
            "messages": messages + [AIMessage(content=content)],
            "current_agent": agent_name,
            "metadata": dict(state.get("metadata") or {}),
        }

    graph = StateGraph(SpecialistState)
    graph.add_node("plan_request", plan_request)
    graph.add_node("execute_operation", execute_operation)
    graph.add_node("format_response", format_response)
    graph.set_entry_point("plan_request")
    graph.add_edge("plan_request", "execute_operation")
    graph.add_edge("execute_operation", "format_response")
    graph.add_edge("format_response", END)
    return graph.compile()
