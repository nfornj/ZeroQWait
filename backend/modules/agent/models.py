import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.types import UserDefinedType
from datetime import datetime
from database import Base


class _Vector(UserDefinedType):
    """Minimal SQLAlchemy type that maps to PostgreSQL vector(n)."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def get_col_spec(self, **kw):
        return f"vector({self.dim})"

    def bind_expression(self, bindvalue):
        return bindvalue

    class comparator_factory(UserDefinedType.Comparator):
        def cosine_distance(self, other):
            from sqlalchemy import literal_column
            return literal_column(f"({self.expr} <=> {other})")


class ConversationHistory(Base):
    __tablename__ = "conversation_history"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'tool'
    content = Column(Text, nullable=False)
    tool_call_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Semantic embedding (populated by background indexer or at write time)
    embedding = Column(_Vector(384), nullable=True)

class CategoryAlias(Base):
    __tablename__ = "category_aliases"
    
    id = Column(Integer, primary_key=True, index=True)
    category_key = Column(String, index=True, nullable=False)
    alias = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class LearnedSynonym(Base):
    __tablename__ = "learned_synonyms"
    
    id = Column(Integer, primary_key=True, index=True)
    query_term = Column(String, index=True, nullable=False)
    category = Column(String, index=True, nullable=False)
    full_query = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class AgentKnowledge(Base):
    __tablename__ = "agent_knowledge"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    content = Column(Text, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentMemory(Base):
    __tablename__ = "agent_memory"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=True)
    memory_type = Column(String, index=True, nullable=False, default="episodic")
    content = Column(Text, nullable=False)
    source = Column(String, nullable=True)
    importance_score = Column(Float, nullable=False, default=0.5)
    memory_meta = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    last_accessed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GoalSource(str, enum.Enum):
    CHAT = "chat"
    SCHEDULED_JOB = "scheduled_job"
    EVENT = "event"
    SYSTEM = "system"


class GoalStatus(str, enum.Enum):
    PENDING = "pending"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PolicyMode(str, enum.Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    FORBID = "forbid"
    NOTIFY_ONLY = "notify_only"
    SILENT = "silent"


class NotificationStatus(str, enum.Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class CaseStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_ON_CUSTOMER = "waiting_on_customer"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class CasePriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class AgentGoal(Base):
    __tablename__ = "agent_goals"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    source = Column(SQLEnum(GoalSource), nullable=False, default=GoalSource.CHAT, index=True)
    goal_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SQLEnum(GoalStatus), nullable=False, default=GoalStatus.PENDING, index=True)
    priority = Column(String, nullable=False, default="normal", index=True)
    autonomy_policy = Column(String, nullable=True, index=True)
    context = Column(JSON, nullable=True)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    due_at = Column(DateTime, nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("agent_goals.id", ondelete="CASCADE"), nullable=False, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_agent = Column(String, nullable=False, index=True)
    task_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True)
    sequence_index = Column(Integer, nullable=False, default=0)
    requires_approval = Column(Boolean, nullable=False, default=False)
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    goal_id = Column(Integer, ForeignKey("agent_goals.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    triggered_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    run_type = Column(String, nullable=False, default="chat", index=True)
    trigger_source = Column(String, nullable=False, default="chat", index=True)
    execution_mode = Column(String, nullable=False, default="interactive", index=True)
    graph_thread_id = Column(String, nullable=True, index=True)
    current_agent = Column(String, nullable=True, index=True)
    status = Column(SQLEnum(RunStatus), nullable=False, default=RunStatus.PENDING, index=True)
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    event_context = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    external_action_id = Column(String, nullable=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    goal_id = Column(Integer, ForeignKey("agent_goals.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    decided_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    requested_by_agent = Column(String, nullable=False, index=True)
    action_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    rationale = Column(Text, nullable=True)
    expected_impact = Column(Text, nullable=True)
    urgency = Column(String, nullable=False, default="normal", index=True)
    status = Column(SQLEnum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING, index=True)
    request_payload = Column(JSON, nullable=True)
    decision_payload = Column(JSON, nullable=True)
    decision_reason = Column(Text, nullable=True)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    decided_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ShopPolicy(Base):
    __tablename__ = "shop_policies"
    __table_args__ = (
        UniqueConstraint("shop_id", "policy_key", name="uq_shop_policy_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_key = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, default="operations", index=True)
    mode = Column(SQLEnum(PolicyMode), nullable=False, default=PolicyMode.REQUIRE_APPROVAL, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    policy_value = Column(String, nullable=True)
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentNotification(Base):
    __tablename__ = "agent_notifications"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    goal_id = Column(Integer, ForeignKey("agent_goals.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    notification_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String, nullable=False, default="info", index=True)
    status = Column(SQLEnum(NotificationStatus), nullable=False, default=NotificationStatus.UNREAD, index=True)
    payload = Column(JSON, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomerCase(Base):
    __tablename__ = "customer_cases"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    current_goal_id = Column(Integer, ForeignKey("agent_goals.id", ondelete="SET NULL"), nullable=True, index=True)
    case_type = Column(String, nullable=False, index=True)
    status = Column(SQLEnum(CaseStatus), nullable=False, default=CaseStatus.OPEN, index=True)
    priority = Column(SQLEnum(CasePriority), nullable=False, default=CasePriority.NORMAL, index=True)
    source = Column(String, nullable=False, default="customer_chat", index=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    customer_name = Column(String, nullable=True)
    customer_phone = Column(String, nullable=True, index=True)
    customer_email = Column(String, nullable=True, index=True)
    owner_notification_sent = Column(Boolean, nullable=False, default=False)
    last_customer_message_at = Column(DateTime, nullable=True)
    last_agent_response_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
