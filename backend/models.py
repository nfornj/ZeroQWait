from modules.auth.models import User, UserRole, SubscriptionTier
from modules.shops.models import Shop, ShopService, DailyAnalytics, ShopCloseDay, ShopCustomer
from modules.queues.models import Queue, QueueItem, QueueStatus
from modules.employees.models import ShopEmployee, EmployeeShift
from modules.agent.models import ConversationHistory, CategoryAlias, LearnedSynonym, AgentKnowledge, AgentMemory

# Re-export Base for migration scripts
from database import Base
