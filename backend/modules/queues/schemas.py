from typing import List, Optional
from datetime import datetime
from shared.schemas import DictModel
from modules.queues.models import QueueStatus
from modules.shops.schemas import Shop, ShopService
from modules.auth.models import UserRole


class AssignedEmployeeUser(DictModel):
    id: int
    username: str
    email: Optional[str] = None
    is_active: bool
    role: UserRole

# Queue Item schemas
class QueueItemBase(DictModel):
    customer_name: str
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    service_id: Optional[int] = None
    notes: Optional[str] = None

class QueueItemCreate(QueueItemBase):
    pass

class ReassignRequest(DictModel):
    employee_id: int

class QueueItem(QueueItemBase):
    id: int
    queue_id: int
    user_id: Optional[int] = None
    position: int
    status: QueueStatus
    status_token: Optional[str] = None
    checked_in_at: datetime
    service_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_employee_id: Optional[int] = None
    assigned_employee: Optional[AssignedEmployeeUser] = None  # relationship("User")
    service_cost: Optional[float] = 0.0
    service: Optional[ShopService] = None # Populated with service details

# Queue schemas
class QueueBase(DictModel):
    name: str = "Main Queue"

class QueueCreate(QueueBase):
    pass

class Queue(QueueBase):
    id: int
    shop_id: int
    date: datetime
    is_active: bool
    accepting_joins: bool = True
    lock_reason: Optional[str] = None
    queue_items: List[QueueItem] = []

# Shop with active queue
class ShopWithQueue(Shop):
    queues: List[Queue] = []
