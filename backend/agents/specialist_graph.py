from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from . import approval_policy


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
    tool_results: Optional[Dict[str, Any]]
    pending_approval: Optional[Dict[str, Any]]
    proposal_message: Optional[str]
    needs_human_input: bool


Executor = Callable[[str, Dict[str, Any], Sequence[BaseMessage]], Dict[str, Any]]
Formatter = Callable[[str, Dict[str, Any]], str]


def _ollama_base_url() -> str:
    base_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1").rstrip("/")
    if base_url.endswith("/v1"):
        return base_url[:-3]
    return base_url


def get_llm(temperature: float) -> ChatOllama:
    return ChatOllama(
        model=os.getenv("MODEL_NAME", "qwen3:14b-q4_K_M"),
        base_url=_ollama_base_url(),
        temperature=temperature,
        top_p=0.9,
        num_gpu=-1,
    )


def _latest_user_text(messages: Sequence[BaseMessage]) -> str:
    for message in reversed(list(messages or [])):
        if isinstance(message, HumanMessage):
            return str(message.content)
        if isinstance(message, BaseMessage):
            return str(message.content)
    return ""


def build_specialist_runnable(
    *,
    agent_name: str,
    shop_id: int,
    temperature: float,
    planner_instructions: str,
    supported_operations: Sequence[str],
    executor: Executor,
    formatter: Formatter,
):
    supported_operation_set = set(supported_operations)

    def plan_request(state: SpecialistState) -> Dict[str, Any]:
        messages = list(state.get("messages") or [])
        if not messages:
            raise ValueError(f"{agent_name} planner requires at least one message")

        llm = get_llm(temperature)
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

        decision = llm.with_structured_output(SpecialistPlan).invoke(
            [SystemMessage(content=planner_prompt)] + messages
        )
        plan = decision.model_dump()
        operation = str(plan.get("operation") or "").strip()
        if not operation:
            raise ValueError(f"{agent_name} planner returned an empty operation")
        if operation not in supported_operation_set:
            raise ValueError(f"{agent_name} planner returned unsupported operation: {operation}")
        return {"plan": plan, "current_agent": agent_name}

    def execute_operation(state: SpecialistState) -> Dict[str, Any]:
        plan = dict(state.get("plan") or {})
        messages = list(state.get("messages") or [])
        if not plan:
            raise ValueError(f"{agent_name} execute_operation called without a plan")

        if bool(plan.get("requires_clarification")):
            return {
                "current_agent": agent_name,
                "needs_human_input": False,
                "pending_approval": None,
                "tool_results": None,
            }

        operation = str(plan.get("operation"))
        arguments = dict(plan.get("arguments") or {})
        result = executor(operation, arguments, messages)

        if result.get("requires_approval"):
            return {
                "current_agent": agent_name,
                "pending_approval": approval_policy.build_pending_approval(
                    shop_id=shop_id,
                    action=str(result.get("action") or "approval_required"),
                    details=dict(result.get("details") or {}),
                ),
                "proposal_message": result.get("message"),
                "needs_human_input": True,
                "tool_results": None,
            }

        return {
            "current_agent": agent_name,
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