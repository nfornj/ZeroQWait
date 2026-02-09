from typing import List, Optional
from datetime import datetime
from shared.schemas import DictModel
from modules.queues.models import QueueStatus
from modules.shops.schemas import Shop, ShopService
from modules.employees.schemas import ShopEmployee

# Queue Item schemas
class QueueItemBase(DictModel):
    customer_name: str
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    service_id: Optional[int] = None
    notes: Optional[str] = None

class QueueItemCreate(QueueItemBase):
    pass

class QueueItem(QueueItemBase):
    id: int
    queue_id: int
    user_id: Optional[int] = None
    position: int
    status: QueueStatus
    checked_in_at: datetime
    service_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_employee_id: Optional[int] = None
    assigned_employee: Optional[ShopEmployee] = None  # Populated with employee details
    service_cost: Optional[float] = 0.0
    service: Optional[ShopService] = None # Populated with service details

    class Config:
        from_attributes = True

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
    queue_items: List[QueueItem] = []

    class Config:
        from_attributes = True

# Shop with active queue
class ShopWithQueue(Shop):
    queues: List[Queue] = []

    class Config:
        from_attributes = True
