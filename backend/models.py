from modules.auth.models import User, UserRole, SubscriptionTier
from modules.shops.models import Shop, ShopService, DailyAnalytics, ShopCloseDay, ShopCustomer
from modules.queues.models import Queue, QueueItem, QueueStatus
from modules.employees.models import ShopEmployee, EmployeeShift
from modules.agent.models import ConversationHistory, CategoryAlias, LearnedSynonym, AgentKnowledge, AgentMemory, AgentDocument, ShopLLMConfig, ShopSoul, SoulLearning, Commitment, ShopSchedule, AgentGoal, AgentTask, AgentRun, ApprovalRequest, ShopPolicy, AgentNotification, CustomerCase, GoalSource, GoalStatus, TaskStatus, RunStatus, ApprovalStatus, PolicyMode, NotificationStatus, CaseStatus, CasePriority
from modules.appointments.models import Appointment, AppointmentStatus
from modules.payments.models import Invoice, InvoiceLineItem, Payment, PaymentMethod, PaymentStatus, InvoiceStatus
from modules.testing.models import TestingFeedback
from modules.audit.models import AuditLog

# Re-export Base for migration scripts
from database import Base
