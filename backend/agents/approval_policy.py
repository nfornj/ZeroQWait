from __future__ import annotations

from typing import Any, Dict

from database import SessionLocal
from modules.agent.models import PolicyMode
from modules.agent.work_repository import AgentWorkRepository


SUPPORTED_POLICY_MODES = tuple(mode.value for mode in PolicyMode)


_ACTION_CATALOG: Dict[str, Dict[str, str]] = {
    "close_queue": {
        "policy_key": "approval.close_queue",
        "category": "operations",
        "title": "Close Active Queue",
        "risk_level": "high",
        "urgency": "high",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "add_employee": {
        "policy_key": "approval.add_employee",
        "category": "staffing",
        "title": "Add Team Member",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "remove_employee": {
        "policy_key": "approval.remove_employee",
        "category": "staffing",
        "title": "Deactivate Team Member",
        "risk_level": "high",
        "urgency": "high",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "assign_shift": {
        "policy_key": "approval.assign_shift",
        "category": "staffing",
        "title": "Assign Employee Shift",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "create_invoice": {
        "policy_key": "approval.create_invoice",
        "category": "finance",
        "title": "Create Invoice",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "record_payment": {
        "policy_key": "approval.record_payment",
        "category": "finance",
        "title": "Record Payment",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "process_refund": {
        "policy_key": "approval.process_refund",
        "category": "finance",
        "title": "Process Refund",
        "risk_level": "high",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "leave_request": {
        "policy_key": "approval.leave_request",
        "category": "staffing",
        "title": "Employee Leave Request",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "update_service_price": {
        "policy_key": "approval.update_service_price",
        "category": "operations",
        "title": "Update Service Price",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "apply_discount": {
        "policy_key": "approval.apply_discount",
        "category": "finance",
        "title": "Apply Customer Discount",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    # ── Payroll actions ────────────────────────────────────────────────────────
    "onboard_employee": {
        "policy_key": "approval.onboard_employee",
        "category": "payroll",
        "title": "Onboard Employee (Payroll)",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "update_pay_rate": {
        "policy_key": "approval.update_pay_rate",
        "category": "payroll",
        "title": "Update Employee Pay Rate",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "run_payroll": {
        "policy_key": "approval.run_payroll",
        "category": "payroll",
        "title": "Run Payroll",
        "risk_level": "high",
        "urgency": "high",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "finalize_payroll": {
        "policy_key": "approval.finalize_payroll",
        "category": "payroll",
        "title": "Finalize & Pay Payroll",
        "risk_level": "high",
        "urgency": "high",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "split_tips": {
        "policy_key": "approval.split_tips",
        "category": "payroll",
        "title": "Split Tip Pool",
        "risk_level": "low",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
    "generate_t4": {
        "policy_key": "approval.generate_t4",
        "category": "payroll",
        "title": "Generate T4 Slips",
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    },
}


def _action_defaults(action: str) -> Dict[str, str]:
    fallback_title = action.replace("_", " ").title() if action else "Approval Required"
    return {
        "policy_key": f"approval.{action or 'action'}",
        "category": "operations",
        "title": fallback_title,
        "risk_level": "medium",
        "urgency": "normal",
        "default_mode": PolicyMode.REQUIRE_APPROVAL.value,
    }


def _summary_for_action(action: str, details: Dict[str, Any]) -> str:
    if action == "close_queue":
        return "Pause new customers from joining the queue for this shop."
    if action == "add_employee":
        employee_name = str(details.get("name") or "this employee")
        return f"Add {employee_name} to the shop team."
    if action == "remove_employee":
        employee_id = details.get("user_id")
        return f"Remove employee access for user ID {employee_id}."
    if action == "assign_shift":
        employee_id = details.get("user_id")
        date = details.get("date") or "the selected day"
        return f"Assign employee {employee_id} to a shift on {date}."
    if action == "create_invoice":
        service_name = str(details.get("service_name") or "the requested service")
        return f"Create an invoice for {service_name}."
    if action == "record_payment":
        amount = details.get("amount")
        return f"Record a payment of ${float(amount or 0.0):.2f}."
    if action == "process_refund":
        payment_id = details.get("payment_id")
        refund_amount = details.get("refund_amount")
        if refund_amount in (None, ""):
            return f"Refund payment {payment_id}."
        return f"Refund ${float(refund_amount or 0.0):.2f} for payment {payment_id}."
    if action == "leave_request":
        employee_name = str(details.get("employee_name") or "An employee")
        leave_date = str(details.get("leave_date") or details.get("date") or "the requested date")
        reason = str(details.get("reason") or "")
        suffix = f" — reason: {reason}" if reason else ""
        return f"{employee_name} has requested leave on {leave_date}{suffix}."
    if action == "update_service_price":
        service_name = str(details.get("service_name") or "a service")
        new_price = details.get("new_price")
        return f"Update the price for '{service_name}' to ${float(new_price or 0.0):.2f}."
    if action == "apply_discount":
        customer = str(details.get("customer_name") or "a customer")
        discount = details.get("discount_percent") or details.get("discount_amount")
        return f"Apply a discount of {discount} for {customer}."
    if action == "onboard_employee":
        employee_name = str(details.get("name") or "a new employee")
        rate = details.get("hourly_rate") or details.get("annual_salary")
        rate_str = f" at ${float(rate):.2f}/hr" if details.get("hourly_rate") else (f" at ${float(rate):,.2f}/yr" if rate else "")
        return f"Create payroll profile for {employee_name}{rate_str}."
    if action == "update_pay_rate":
        employee_name = str(details.get("employee_name") or "the employee")
        new_rate = details.get("new_rate") or details.get("hourly_rate")
        return f"Update pay rate for {employee_name} to ${float(new_rate or 0):.2f}/hr."
    if action == "run_payroll":
        period = str(details.get("period") or "this pay period")
        count = details.get("employee_count", "")
        count_str = f" for {count} employees" if count else ""
        return f"Calculate draft payslips{count_str} for {period}."
    if action == "finalize_payroll":
        period = str(details.get("period") or "this pay period")
        total = details.get("total_net_pay")
        total_str = f" (${float(total):,.2f} total net pay)" if total else ""
        return f"Approve and mark payroll as paid for {period}{total_str}."
    if action == "split_tips":
        pool_date = str(details.get("pool_date") or "today")
        amount = details.get("total_amount")
        amount_str = f" ${float(amount):.2f}" if amount else ""
        return f"Split{amount_str} tip pool from {pool_date} among staff."
    if action == "generate_t4":
        tax_year = details.get("tax_year", "")
        count = details.get("employee_count", "")
        count_str = f" for {count} employees" if count else ""
        return f"Generate T4 slips{count_str} for tax year {tax_year}."
    return "A business action needs a policy decision before the agent can continue."


def _rationale_for_action(action: str, details: Dict[str, Any]) -> str:
    if action == "close_queue":
        return str(details.get("reason") or "The agent wants to pause new queue intake.")
    if action == "add_employee":
        employee_name = str(details.get("name") or "this employee")
        return f"Create a new employee record for {employee_name}."
    if action == "remove_employee":
        employee_id = details.get("user_id")
        return f"Remove employee access for user ID {employee_id}."
    if action == "assign_shift":
        employee_id = details.get("user_id")
        start_time = details.get("start_time") or "start time"
        end_time = details.get("end_time") or "end time"
        return f"Create a shift from {start_time} to {end_time} for employee {employee_id}."
    if action == "create_invoice":
        service_name = str(details.get("service_name") or "the requested service")
        unit_price = float(details.get("unit_price") or 0.0)
        quantity = int(details.get("quantity") or 1)
        return f"Create an invoice for {service_name} at ${unit_price:.2f} x {quantity}."
    if action == "record_payment":
        amount = float(details.get("amount") or 0.0)
        method = str(details.get("method") or "cash")
        return f"Record a {method} payment of ${amount:.2f}."
    if action == "process_refund":
        payment_id = details.get("payment_id")
        refund_amount = details.get("refund_amount")
        reason = str(details.get("reason") or "No explicit reason was provided.")
        if refund_amount in (None, ""):
            return f"Refund payment {payment_id}. Reason: {reason}"
        return f"Refund ${float(refund_amount or 0.0):.2f} for payment {payment_id}. Reason: {reason}"
    if action == "leave_request":
        employee_name = str(details.get("employee_name") or "the employee")
        leave_date = str(details.get("leave_date") or details.get("date") or "the requested date")
        reason = str(details.get("reason") or "No reason given.")
        return f"{employee_name} is requesting time off on {leave_date}. Reason: {reason}"
    if action == "update_service_price":
        service_name = str(details.get("service_name") or "a service")
        old_price = details.get("old_price")
        new_price = details.get("new_price")
        old_str = f" (currently ${float(old_price):.2f})" if old_price is not None else ""
        return f"Change the price of '{service_name}'{old_str} to ${float(new_price or 0.0):.2f}."
    if action == "apply_discount":
        customer = str(details.get("customer_name") or "a customer")
        discount = details.get("discount_percent") or details.get("discount_amount")
        service = str(details.get("service_name") or "their service")
        return f"Apply a discount of {discount} on {service} for {customer}."
    if action == "onboard_employee":
        employee_name = str(details.get("name") or "the new employee")
        pay_freq = str(details.get("pay_frequency") or "biweekly")
        return f"Create a payroll profile for {employee_name} with {pay_freq} pay schedule."
    if action == "update_pay_rate":
        employee_name = str(details.get("employee_name") or "the employee")
        old_rate = details.get("old_rate")
        new_rate = details.get("new_rate") or details.get("hourly_rate")
        old_str = f" from ${float(old_rate):.2f}" if old_rate else ""
        return f"Change hourly rate for {employee_name}{old_str} to ${float(new_rate or 0):.2f}."
    if action == "run_payroll":
        period = str(details.get("period") or "this pay period")
        return f"Draft payslips for all active employees covering {period}."
    if action == "finalize_payroll":
        period = str(details.get("period") or "this pay period")
        total = details.get("total_net_pay")
        total_str = f" totalling ${float(total):,.2f}" if total else ""
        return f"Approve all draft payslips for {period}{total_str} and mark as paid."
    if action == "split_tips":
        method = str(details.get("split_method") or "hours_worked")
        return f"Split the tip pool using the '{method}' method and log individual tip entries."
    if action == "generate_t4":
        tax_year = details.get("tax_year", "the selected year")
        return f"Generate draft T4 slips from YTD accumulator data for {tax_year}."
    return "The agent flagged this change as operationally significant."


def _impact_for_action(action: str, details: Dict[str, Any]) -> str:
    if action == "close_queue":
        return "New walk-ins will stop joining until the queue is reopened."
    if action == "add_employee":
        return "The team roster will change and the employee can be scheduled immediately."
    if action == "remove_employee":
        return "The employee will no longer appear as active for staffing and scheduling workflows."
    if action == "assign_shift":
        return "The staffing schedule will change immediately after execution."
    if action == "create_invoice":
        return "A new financial record will be created and become available for payment tracking."
    if action == "record_payment":
        return "The invoice and payment ledger will update immediately after execution."
    if action == "process_refund":
        return "The payment ledger will be adjusted immediately and the refund cannot be silently ignored by staff or customers."
    if action == "leave_request":
        return "The employee's schedule will be marked as leave on the requested date, affecting staffing coverage."
    if action == "update_service_price":
        return "All future customers will see and be charged the new price immediately."
    if action == "apply_discount":
        return "The discount will be applied to the invoice and will reduce revenue for this transaction."
    if action == "onboard_employee":
        return "The employee's pay rate and T4 province will be set permanently until updated."
    if action == "update_pay_rate":
        return "All future payslips for this employee will use the new rate immediately."
    if action == "run_payroll":
        return "Draft payslips will be created. No money moves until the owner approves and finalizes."
    if action == "finalize_payroll":
        return "Payslips are marked as paid and YTD accumulators are updated. This cannot be easily reversed."
    if action == "split_tips":
        return "Tips are distributed to staff and logged. The pool is closed."
    if action == "generate_t4":
        return "T4 drafts are created. Filing with CRA requires a separate step."
    return "Shop operations will change immediately after execution."


def get_policy_definition(policy_key: str) -> Dict[str, Any] | None:
    normalized = str(policy_key or "").strip()
    if not normalized:
        return None
    for action, config in sorted(_ACTION_CATALOG.items()):
        if config["policy_key"] != normalized:
            continue
        return {
            "action": action,
            "policy_key": config["policy_key"],
            "category": config["category"],
            "title": config["title"],
            "risk_level": config["risk_level"],
            "urgency": config["urgency"],
            "default_mode": config["default_mode"],
            "supported_modes": list(SUPPORTED_POLICY_MODES),
        }
    return None


def list_policy_definitions() -> list[Dict[str, Any]]:
    definitions: list[Dict[str, Any]] = []
    for action, config in sorted(_ACTION_CATALOG.items(), key=lambda item: (item[1]["category"], item[1]["policy_key"])):
        definitions.append(
            {
                "action": action,
                "policy_key": config["policy_key"],
                "category": config["category"],
                "title": config["title"],
                "risk_level": config["risk_level"],
                "urgency": config["urgency"],
                "default_mode": config["default_mode"],
                "supported_modes": list(SUPPORTED_POLICY_MODES),
            }
        )
    return definitions


def list_shop_policies(shop_id: int) -> list[Dict[str, Any]]:
    if shop_id <= 0:
        return []

    stored_modes: Dict[str, str] = {}
    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        for policy in repo.get_shop_policies(shop_id):
            policy_key = str(getattr(policy, "policy_key", "") or "").strip()
            if not policy_key:
                continue
            resolved_mode = getattr(policy, "mode", None)
            stored_modes[policy_key] = resolved_mode.value if hasattr(resolved_mode, "value") else str(resolved_mode)
    finally:
        db.close()

    payload: list[Dict[str, Any]] = []
    for item in list_policy_definitions():
        payload.append(
            {
                **item,
                "mode": stored_modes.get(item["policy_key"], item["default_mode"]),
                "explicit": item["policy_key"] in stored_modes,
            }
        )
    return payload


def resolve_action_policy(shop_id: int, action: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    normalized_action = str(action or "approval_required").strip() or "approval_required"
    detail_payload = dict(details or {})
    catalog = {**_action_defaults(normalized_action), **_ACTION_CATALOG.get(normalized_action, {})}
    policy_mode = catalog["default_mode"]

    db = SessionLocal()
    try:
        repo = AgentWorkRepository(db)
        for policy in repo.get_shop_policies(shop_id):
            if getattr(policy, "policy_key", None) != catalog["policy_key"]:
                continue
            resolved_mode = getattr(policy, "mode", policy_mode)
            policy_mode = resolved_mode.value if hasattr(resolved_mode, "value") else str(resolved_mode)
            break
    finally:
        db.close()

    return {
        "action": normalized_action,
        "policy_key": catalog["policy_key"],
        "policy_mode": policy_mode,
        "category": catalog["category"],
        "title": catalog["title"],
        "risk_level": catalog["risk_level"],
        "urgency": catalog["urgency"],
        "summary": _summary_for_action(normalized_action, detail_payload),
        "rationale": _rationale_for_action(normalized_action, detail_payload),
        "expected_impact": _impact_for_action(normalized_action, detail_payload),
    }


def build_pending_approval(shop_id: int, action: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    pending_details = dict(details or {})
    policy = resolve_action_policy(shop_id, action, pending_details)
    return {
        "action": policy["action"],
        "details": pending_details,
        "shop_id": shop_id,
        "policy_key": policy["policy_key"],
        "policy_mode": policy["policy_mode"],
        "category": policy["category"],
        "title": policy["title"],
        "risk_level": policy["risk_level"],
        "urgency": policy["urgency"],
        "summary": policy["summary"],
        "rationale": policy["rationale"],
        "expected_impact": policy["expected_impact"],
    }
