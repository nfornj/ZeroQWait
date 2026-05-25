"""
observability/metrics.py — ZeroQwait Prometheus metrics registry.

All metric objects are module-level singletons; import them wherever you need
to record an observation.  Never create metrics inside functions — that causes
duplicate-registration errors.

Label cardinality rules (MUST follow):
  - All label sets are bounded to low-cardinality values.
  - Never use tenant_id, user_id, message_text, or session_id as labels.
  - Use tenant_tier ("free" | "premium" | "shared") for per-tier breakdowns.
"""

from prometheus_client import Counter, Gauge, Histogram

# ── Bucket configs ─────────────────────────────────────────────────────────────

_LATENCY_BUCKETS = (.05, .1, .25, .5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0)
_TOOL_LATENCY_BUCKETS = (.025, .05, .1, .25, .5, 1.0, 2.5, 5.0, 15.0, 30.0)
_UPLOAD_SIZE_BUCKETS = (
    1_024,
    10_240,
    102_400,
    1_048_576,
    5_242_880,
    10_485_760,
    52_428_800,
    104_857_600,
)

# ── Agent request lifecycle ────────────────────────────────────────────────────

agent_requests_total = Counter(
    "zq_agent_requests_total",
    "Total agent requests by entry-point and final status.",
    ["entrypoint", "status"],
    # entrypoint: chat | stream | approve | briefing | other
    # status:     success | error | timeout
)

agent_request_duration = Histogram(
    "zq_agent_request_duration_seconds",
    "End-to-end agent request duration in seconds.",
    ["entrypoint"],
    buckets=_LATENCY_BUCKETS,
)

agent_inflight = Gauge(
    "zq_agent_inflight_requests",
    "Currently inflight agent requests.",
    ["entrypoint"],
)

# ── Supervisor routing ─────────────────────────────────────────────────────────

agent_route_total = Counter(
    "zq_agent_route_total",
    "Intent classifications and routing decisions.",
    ["to_agent", "source"],
    # to_agent: receptionist | finance | hr | crm | inventory | general | schedule | greeting
    # source:   fastpath | llm | greeting | empty
)

agent_unhandled_intent_total = Counter(
    "zq_agent_unhandled_intent_total",
    "Messages that fell through all intent classifiers to general/unknown.",
    [],
)

# ── Specialist / tool execution ────────────────────────────────────────────────

agent_execute_total = Counter(
    "zq_agent_execute_total",
    "Specialist execution attempts by target and status.",
    ["target", "status"],
    # target: receptionist | finance | hr | crm | inventory | general
    # status: success | error | timeout
)

agent_execute_duration = Histogram(
    "zq_agent_execute_duration_seconds",
    "Duration of execute_plan specialist execution.",
    ["target"],
    buckets=_LATENCY_BUCKETS,
)

agent_tool_call_total = Counter(
    "zq_agent_tool_call_total",
    "Individual tool calls by tool name and status.",
    ["tool", "status"],
    # tool:   list_queue | call_next | close_queue | daily_revenue | ... any tool name
    # status: success | error | timeout
)

agent_tool_duration = Histogram(
    "zq_agent_tool_call_duration_seconds",
    "Duration of individual agent tool calls.",
    ["tool"],
    buckets=_TOOL_LATENCY_BUCKETS,
)

# ── HITL / approval flow ───────────────────────────────────────────────────────

agent_approval_required_total = Counter(
    "zq_agent_approval_required_total",
    "High-impact actions that triggered a HITL approval gate.",
    ["action_type"],
)

agent_approval_outcome_total = Counter(
    "zq_agent_approval_outcome_total",
    "Owner decisions on HITL approval requests.",
    ["action_type", "outcome"],
    # outcome: approved | rejected | expired
)

agent_approval_wait_seconds = Histogram(
    "zq_agent_approval_wait_seconds",
    "Time the owner took to approve or reject a pending action.",
    ["action_type"],
    buckets=(10, 30, 60, 120, 300, 600, 1800, 3600, float("inf")),
)

# ── LangGraph checkpoint reliability ──────────────────────────────────────────

agent_checkpoint_total = Counter(
    "zq_agent_checkpoint_total",
    "LangGraph checkpoint read/write operations by status.",
    ["operation", "status"],
    # operation: write | read | resume
    # status:    success | error
)

agent_checkpoint_duration = Histogram(
    "zq_agent_checkpoint_duration_seconds",
    "Duration of checkpoint write/read operations.",
    ["operation"],
    buckets=_TOOL_LATENCY_BUCKETS,
)

# ── Notifications ──────────────────────────────────────────────────────────────

notification_dispatch_total = Counter(
    "zq_notification_dispatch_total",
    "Notification dispatch attempts by channel, event type, and outcome.",
    ["channel", "event_type", "status"],
    # channel:    telegram | email | sms
    # event_type: morning_briefing | appointment_confirmation | ... (see _EMAIL_SUBJECTS)
    # status:     sent | failed | no_address | not_configured | channel_not_implemented
)

notification_dispatch_duration = Histogram(
    "zq_notification_dispatch_duration_seconds",
    "Latency of notification dispatch calls.",
    ["channel"],
    buckets=_TOOL_LATENCY_BUCKETS,
)

notification_provider_errors_total = Counter(
    "zq_notification_provider_errors_total",
    "Provider-side errors from Telegram / AWS SES / AWS SNS.",
    ["provider", "error_code"],
    # provider:   telegram | ses | sns
    # error_code: normalized short code from the provider error
)

# ── Product operations metrics ───────────────────────────────────────────────

email_delivery_total = Counter(
    "zeroqwait_emails_total",
    "Emails sent or failed by bounded email type.",
    ["email_type", "status"],
    # email_type: queue_join | youre_next | appointment_confirmation | password_reset | ... | direct | other
    # status:     sent | failed
)

sms_delivery_total = Counter(
    "zeroqwait_sms_total",
    "SMS messages sent or failed.",
    ["status"],
    # status: sent | failed
)

b2_uploads_total = Counter(
    "zeroqwait_b2_uploads_total",
    "Backblaze B2 upload attempts by status.",
    ["status"],
    # status: success | failed
)

b2_upload_size_bytes = Histogram(
    "zeroqwait_b2_upload_size_bytes",
    "Size of successful Backblaze B2 uploads in bytes.",
    buckets=_UPLOAD_SIZE_BUCKETS,
)

infisical_secret_fetch_duration = Histogram(
    "zeroqwait_infisical_secret_fetch_duration_seconds",
    "Infisical startup secret fetch latency in seconds.",
    ["status"],
    # status: success | failed
    buckets=(.05, .1, .25, .5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# ── HTTP layer (FastAPI) ───────────────────────────────────────────────────────

http_requests_total = Counter(
    "zq_http_requests_total",
    "Total HTTP requests handled by the FastAPI app.",
    ["method", "path_group", "status_code"],
)

http_request_duration = Histogram(
    "zq_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path_group"],
    buckets=_LATENCY_BUCKETS,
)

# ── Temporal / brain workflows ─────────────────────────────────────────────────

temporal_workflow_total = Counter(
    "zq_temporal_workflow_total",
    "Temporal workflow runs by workflow type and status.",
    ["workflow", "status"],
    # workflow: soul_evolution | commitment_resolver | custom_schedule | commitment_scanner
    # status:   success | error
)

temporal_workflow_duration = Histogram(
    "zq_temporal_workflow_duration_seconds",
    "Duration of Temporal workflow executions.",
    ["workflow"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800),
)
