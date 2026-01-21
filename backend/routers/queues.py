from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from db_interface import db_interface
from schemas import Queue, QueueItem, QueueItemCreate, QueueCreate
from auth_utils import get_current_user, get_current_user_optional
from permissions import check_shop_access
from datetime import datetime

router = APIRouter()

# Helper function to anonymize customer names for privacy
def anonymize_customer_name(name: str) -> str:
    """Anonymize customer name by showing first name and first letter of last name"""
    if not name or not name.strip():
        return "Customer"
    
    parts = name.strip().split()
    if len(parts) == 1:
        # Single name: show first 3 chars + "..."
        return parts[0][:3] + "..." if len(parts[0]) > 3 else parts[0]
    else:
        # Multiple names: show first name + first letter of last name
        return f"{parts[0]} {parts[-1][0]}."

# Helper function to populate employee details for queue items
def populate_employee_details(items: List[dict]) -> List[dict]:
    """Populate assigned_employee details for queue items"""
    if not items:
        return items
    
    # Get unique employee IDs
    employee_ids = list(set([item.get("assigned_employee_id") for item in items if item.get("assigned_employee_id")]))
    
    if not employee_ids:
        return items
    
    # Fetch employee details
    try:
        employees_dict = {}
        for emp_id in employee_ids:
            user = db_interface.get_user_by_id(emp_id)
            if user:
                # Filter sensitive fields
                employees_dict[emp_id] = {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                    "profile_photo_url": user.get("profile_photo_url")
                }
            
        # Populate employee details in items
        for item in items:
            if item.get("assigned_employee_id"):
                item["assigned_employee"] = employees_dict.get(item["assigned_employee_id"])
    except Exception:
        pass  # Continue even if employee fetch fails
    
    return items

# Queue status enum values
QUEUE_STATUS_WAITING = "waiting"
QUEUE_STATUS_BEING_SERVED = "being_served"
QUEUE_STATUS_COMPLETED = "completed"
QUEUE_STATUS_CANCELLED = "cancelled"

@router.get("/shop/{shop_id}/active", response_model=Queue)
def get_active_queue(
    shop_id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Get the active queue for a shop (public endpoint with privacy protection)"""
    try:
        # Check if user has access to this shop (owner or employee)
        has_shop_access = False
        if current_user:
            try:
                check_shop_access(shop_id, current_user, require_owner=False)
                has_shop_access = True
            except HTTPException:
                has_shop_access = False
        
        # Get active queues for this shop
        active_queues = db_interface.get_queues({"shop_id": shop_id, "is_active": True})
        
        if not active_queues:
            # Create a new queue if none exists
            shop = db_interface.get_shop_by_id(shop_id)
            if not shop:
                raise HTTPException(status_code=404, detail="Shop not found")
            
            queue_data = {
                "shop_id": shop_id,
                "is_active": True,
                "name": "Main Queue"
            }
            queue = db_interface.create_queue(queue_data)
            if queue:
                queue["queue_items"] = []
                return queue
            raise HTTPException(status_code=500, detail="Failed to create queue")
        
        queue = active_queues[0]
        # Fetch queue items
        all_items = db_interface.get_queue_items({"queue_id": queue["id"]})
        
        # Renumber positions dynamically for active customers only
        # (waiting and being_served get sequential positions 1, 2, 3...)
        active_items = [item for item in all_items if item["status"] in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]]
        for idx, item in enumerate(active_items, start=1):
            item["position"] = idx
        
        # Populate employee details
        all_items = populate_employee_details(all_items)
        
        # PRIVACY: Anonymize customer names for public users (non-shop staff)
        if not has_shop_access:
            for item in all_items:
                if item.get("customer_name"):
                    item["customer_name"] = anonymize_customer_name(item["customer_name"])
                # Also remove sensitive fields for public view
                item.pop("customer_phone", None)
                item.pop("customer_email", None)
                item.pop("notes", None)
        
        queue["queue_items"] = all_items
        return queue
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch queue: {str(e)}")


@router.get("/shop/{shop_id}/all", response_model=List[Queue])
def get_all_shop_queues(
    shop_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get all queues for a shop (Shop Owner or Employee)"""
    try:
        # Check if user is owner or active employee
        check_shop_access(shop_id, current_user, require_owner=False)
        
        queues = db_interface.get_queues({"shop_id": shop_id})
        # Sort manually since get_queues doesn't support complex ordering in params yet (it uses simple filters)
        # Assuming we want active first or date desc
        queues.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        result_queues = []
        for queue in queues:
            all_items = db_interface.get_queue_items({"queue_id": queue["id"]})
            
            # Renumber positions for active customers
            active_items = [item for item in all_items if item["status"] in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]]
            for idx, item in enumerate(active_items, start=1):
                item["position"] = idx
            
            # Populate employee details
            all_items = populate_employee_details(all_items)
            
            queue["queue_items"] = all_items
            result_queues.append(queue)
        
        return result_queues
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch queues: {str(e)}")


@router.post("/shop/{shop_id}", response_model=Queue)
def create_queue(
    shop_id: int,
    queue_create: QueueCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new queue for a shop (Shop Owner or Employee)"""
    try:
        # Check if user is owner or active employee
        check_shop_access(shop_id, current_user, require_owner=False)
        
        # Get shop for subscription check
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        # Check queue limit based on subscription tier
        try:
            from tier_limits import TIER_LIMITS
            active_queues = db_interface.get_queues({"shop_id": shop_id, "is_active": True})
            current_queue_count = len(active_queues)
            
            tier_limit = TIER_LIMITS.get(current_user.get("subscription_tier", "free"), {}).get("max_queues_per_shop", 1)
            if current_queue_count >= tier_limit:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Queue limit reached for {current_user.get('subscription_tier', 'free')} tier. Maximum: {tier_limit} active queue(s). Upgrade to Premium for up to 5 queues."
                )
        except ImportError:
            pass
        except HTTPException:
            raise
        except Exception:
            pass
        
        queue_data = {
            "shop_id": shop_id,
            "name": queue_create.name,
            "is_active": True
        }
        queue = db_interface.create_queue(queue_data)
        if queue:
            queue["queue_items"] = []
            return queue
        raise HTTPException(status_code=500, detail="Failed to create queue")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create queue: {str(e)}")


@router.post("/shop/{shop_id}/join", response_model=QueueItem)
def join_queue(
    shop_id: int,
    queue_item: QueueItemCreate
):
    """Join a shop's queue (public endpoint - no auth required)"""
    try:
        # Get shop and verify it exists
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        # Get shop owner to check their subscription tier
        owner = db_interface.get_user_by_id(shop["owner_id"])
        owner_tier = owner["subscription_tier"] if owner else "free"
        
        # Get or create active queue
        active_queues = db_interface.get_queues({"shop_id": shop_id, "is_active": True})
        
        if not active_queues:
            queue_data = {
                "shop_id": shop_id,
                "is_active": True,
                "name": "Main Queue"
            }
            queue = db_interface.create_queue(queue_data)
            if not queue:
                raise HTTPException(status_code=500, detail="Failed to create queue")
        else:
            queue = active_queues[0]
        
        # Check queue size limit based on shop owner's subscription tier
        try:
            from tier_limits import TIER_LIMITS
            all_items = db_interface.get_queue_items({"queue_id": queue["id"]})
            current_items = [i for i in all_items if i["status"] in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]]
            current_queue_size = len(current_items)
            
            tier_limit = TIER_LIMITS.get(owner_tier, {}).get("max_queue_size")
            if tier_limit is not None and current_queue_size >= tier_limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Queue is full. Maximum capacity for {owner_tier} tier: {tier_limit} customers. Please try again later or contact the shop to upgrade their plan."
                )
        except ImportError:
            pass
        except HTTPException:
            raise
        except Exception:
            pass
        
        # Calculate position (last position + 1)
        all_items = db_interface.get_queue_items({"queue_id": queue["id"]})
        max_position = max([item["position"] for item in all_items], default=0) if all_items else 0
        position = max_position + 1
        
        # Create queue item
        queue_item_data = queue_item.dict()
        queue_item_data["queue_id"] = queue["id"]
        queue_item_data["user_id"] = None  # Public queue, no user association
        queue_item_data["position"] = position
        queue_item_data["status"] = QUEUE_STATUS_WAITING
        
        # Handle Service Selection
        if queue_item.service_id:
            service = db_interface.get_shop_service_by_id(queue_item.service_id)
            if service and service["shop_id"] == shop_id:
                queue_item_data["service_cost"] = service["cost"]
            else:
                queue_item_data["service_id"] = None # Reset if invalid
        
        new_item = db_interface.create_queue_item(queue_item_data)
        if new_item:
            # Calculate the actual display position (sequential for active customers)
            all_active_items = db_interface.get_queue_items({"queue_id": queue["id"]})
            active_items = [i for i in all_active_items if i["status"] in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]]
            
            # The display position is the count of active items
            new_item["position"] = len(active_items)
            
            return new_item
        raise HTTPException(status_code=500, detail="Failed to join queue")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to join queue: {str(e)}")


@router.get("/{queue_id}/items", response_model=List[QueueItem])
def get_queue_items(queue_id: int):
    """Get all items in a queue"""
    try:
        items = db_interface.get_queue_items({"queue_id": queue_id})
        return items
    except Exception:
        return []


@router.patch("/items/{item_id}/status")
def update_queue_item_status(
    item_id: int,
    new_status: str,
    current_user: dict = Depends(get_current_user)
):
    """Update queue item status (Shop Owner or Employee)"""
    try:
        # We need to find the item to get details, db_interface doesn't have get_queue_item_by_id directly exposed in generic get
        # But wait, we can filter.
        # However, update_queue_item requires ID.
        # Let's verify access first.
        # We need to know which shop this item belongs to.
        # This requires a join or two queries.
        
        # Currently db_interface doesn't support get_queue_item_by_id directly (it returns list with filters)
        # We can use get_queue_items({"id": item_id}) if we support filtering by ID on items.
        # Looking at db_interface, get_queue_items filters by equality. So yes.
        items = db_interface.get_queue_items({"id": item_id})
        if not items:
            raise HTTPException(status_code=404, detail="Queue item not found")
        item = items[0]

        queue = db_interface.get_queue_by_id(item["queue_id"])
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
        
        shop_id = queue["shop_id"]
        
        # Check if user is owner or active employee
        check_shop_access(shop_id, current_user, require_owner=False)
        
        # Update status and timestamps
        update_data = {"status": new_status}
        if new_status == QUEUE_STATUS_BEING_SERVED:
            update_data["service_started_at"] = datetime.utcnow().isoformat()
        elif new_status in [QUEUE_STATUS_COMPLETED, QUEUE_STATUS_CANCELLED]:
            update_data["completed_at"] = datetime.utcnow().isoformat()
        
        updated_item = db_interface.update_queue_item(item_id, update_data)
        if updated_item:
            return updated_item
        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")


@router.post("/{queue_id}/call-next", response_model=QueueItem)
def call_next_customer(
    queue_id: int,
    employee_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """Call the next customer in line (Shop Owner or Employee)"""
    try:
        import random
        
        queue = db_interface.get_queue_by_id(queue_id)
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
        
        shop_id = queue["shop_id"]
        
        # Check if user is owner or active employee
        check_shop_access(shop_id, current_user, require_owner=False)
        
        # Determine which employee to assign
        assigned_employee_id = employee_id
        
        if assigned_employee_id is None:
            # Random assignment: get clocked-in employees
            active_shifts = db_interface.get_shop_active_shifts(shop_id)
            
            if active_shifts:
                # Randomly select from clocked-in employees
                available_employees = [shift["user_id"] for shift in active_shifts]
                assigned_employee_id = random.choice(available_employees)
            else:
                # No employees clocked in, assign to shop owner or current user
                shop = db_interface.get_shop_by_id(shop_id)
                if shop:
                    assigned_employee_id = shop["owner_id"]
                else:
                    assigned_employee_id = current_user["id"]
        
        # Complete any currently serving customers first
        all_items = db_interface.get_queue_items({"queue_id": queue_id})
        currently_serving = [i for i in all_items if i["status"] == QUEUE_STATUS_BEING_SERVED]
        
        for serving_item in currently_serving:
            db_interface.update_queue_item(serving_item["id"], {
                "status": QUEUE_STATUS_COMPLETED,
                "completed_at": datetime.utcnow().isoformat()
            })

        # Find next waiting customer
        waiting_items = [i for i in all_items if i["status"] == QUEUE_STATUS_WAITING]
        # Sort by position just in case
        waiting_items.sort(key=lambda x: x["position"])
        
        if not waiting_items:
            raise HTTPException(status_code=404, detail="No customers waiting")
        
        next_item = waiting_items[0]
        
        update_data = {
            "status": QUEUE_STATUS_BEING_SERVED,
            "service_started_at": datetime.utcnow().isoformat(),
            "assigned_employee_id": assigned_employee_id
        }
        result = db_interface.update_queue_item(next_item["id"], update_data)
        
        if result:
            # Fetch employee details
            if result.get("assigned_employee_id"):
                user = db_interface.get_user_by_id(result["assigned_employee_id"])
                if user:
                    result["assigned_employee"] = {
                        "id": user["id"],
                        "username": user["username"],
                        "email": user["email"],
                        "profile_photo_url": user.get("profile_photo_url")
                    }
            return result
        return next_item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to call next customer: {str(e)}")


@router.delete("/items/{item_id}")
def remove_queue_item(
    item_id: int,
    reason: str,
    current_user: dict = Depends(get_current_user)
):
    """Remove a customer from queue with reason (Shop Owner or Employee)"""
    try:
        # Get queue item
        items = db_interface.get_queue_items({"id": item_id})
        if not items:
            raise HTTPException(status_code=404, detail="Queue item not found")
        item = items[0]
        
        # Get shop_id from queue
        queue = db_interface.get_queue_by_id(item["queue_id"])
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
        
        shop_id = queue["shop_id"]
        
        # Check if user is owner or active employee
        check_shop_access(shop_id, current_user, require_owner=False)
        
        # Mark as cancelled with reason
        update_data = {
            "status": QUEUE_STATUS_CANCELLED,
            "completed_at": datetime.utcnow().isoformat(),
            "notes": f"{item.get('notes', '')}\n[REMOVED: {reason}]" if item.get('notes') else f"[REMOVED: {reason}]"
        }
        
        result = db_interface.update_queue_item(item_id, update_data)
        if result:
            return {"message": "Customer removed from queue", "item": result}
        raise HTTPException(status_code=500, detail="Failed to remove customer")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove customer: {str(e)}"
        )


@router.delete("/items/{item_id}/leave")
def leave_queue(
    item_id: int
):
    """Customer leaves the queue (public endpoint - no auth required)"""
    try:
        # Get queue item
        items = db_interface.get_queue_items({"id": item_id})
        if not items:
            raise HTTPException(status_code=404, detail="Queue item not found")
        item = items[0]
        
        # Only allow if customer is still waiting
        if item["status"] not in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot leave queue - already completed or cancelled"
            )
        
        # Mark as cancelled
        update_data = {
            "status": QUEUE_STATUS_CANCELLED,
            "completed_at": datetime.utcnow().isoformat(),
            "notes": f"{item.get('notes', '')}\n[Customer left queue]" if item.get('notes') else "[Customer left queue]"
        }
        
        result = db_interface.update_queue_item(item_id, update_data)
        if result:
            return {"message": "You have left the queue", "item": result}
        raise HTTPException(status_code=500, detail="Failed to leave queue")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to leave queue: {str(e)}"
        )


@router.post("/items/{item_id}/serve")
def serve_specific_customer(
    item_id: int,
    employee_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """Serve a specific customer (skip the queue) (Shop Owner or Employee)"""
    try:
        # Get queue item
        items = db_interface.get_queue_items({"id": item_id})
        if not items:
            raise HTTPException(status_code=404, detail="Queue item not found")
        item = items[0]
        queue_id = item["queue_id"]
        
        # Get shop_id from queue
        queue = db_interface.get_queue_by_id(queue_id)
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
        shop_id = queue["shop_id"]
        
        # Check if user is owner or active employee
        check_shop_access(shop_id, current_user, require_owner=False)
        
        # Check if customer is waiting
        if item["status"] != QUEUE_STATUS_WAITING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer is not in waiting status"
            )
        
        # First, complete any currently serving customers in this queue
        all_items = db_interface.get_queue_items({"queue_id": queue_id})
        currently_serving = [i for i in all_items if i["status"] == QUEUE_STATUS_BEING_SERVED]
        
        for serving_item in currently_serving:
            db_interface.update_queue_item(serving_item["id"], {
                "status": QUEUE_STATUS_COMPLETED,
                "completed_at": datetime.utcnow().isoformat()
            })
        
        # Determine employee assignment
        assigned_employee_id = employee_id if employee_id else current_user["id"]
        
        # Now serve the selected customer
        update_data = {
            "status": QUEUE_STATUS_BEING_SERVED,
            "service_started_at": datetime.utcnow().isoformat(),
            "assigned_employee_id": assigned_employee_id
        }
        
        result = db_interface.update_queue_item(item_id, update_data)
        if result:
            return {"message": "Now serving customer", "item": result}
        raise HTTPException(status_code=500, detail="Failed to serve customer")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to serve customer: {str(e)}"
        )


@router.get("/items/{item_id}/estimate")
def get_wait_estimate(item_id: int):
    """Get estimated wait time for a queue item"""
    try:
        items = db_interface.get_queue_items({"id": item_id})
        if not items:
            raise HTTPException(status_code=404, detail="Queue item not found")
        item = items[0]
        
        # Count how many people are ahead
        all_items = db_interface.get_queue_items({"queue_id": item["queue_id"]})
        ahead = 0
        for other in all_items:
            if other["status"] in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]:
                if other["position"] < item["position"]:
                    ahead += 1
        
        # Get shop's average service time
        queue = db_interface.get_queue_by_id(item["queue_id"])
        if not queue:
            raise HTTPException(status_code=404, detail="Queue not found")
        
        shop = db_interface.get_shop_by_id(queue["shop_id"])
        average_service_time = shop.get("average_service_time", 30) if shop else 30
        
        estimated_minutes = ahead * average_service_time
        
        return {
            "item_id": item_id,
            "position": item["position"],
            "people_ahead": ahead,
            "estimated_wait_minutes": estimated_minutes,
            "status": item["status"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get estimate: {str(e)}")
