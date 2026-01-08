from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from supabase_client import supabase
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
        employees_response = supabase.table("users").select(
            "id, username, email, profile_photo_url"
        ).in_("id", employee_ids).execute()
        
        if employees_response.data:
            employees_dict = {emp["id"]: emp for emp in employees_response.data}
            
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
        
        queue_response = supabase.table("queues").select("*").eq(
            "shop_id", shop_id
        ).eq("is_active", True).execute()
        
        if not queue_response.data:
            # Create a new queue if none exists
            shop_response = supabase.table("shops").select("id").eq("id", shop_id).execute()
            if not shop_response.data:
                raise HTTPException(status_code=404, detail="Shop not found")
            
            queue_data = {
                "shop_id": shop_id,
                "is_active": True,
                "name": "Main Queue"
            }
            new_queue_response = supabase.table("queues").insert(queue_data).execute()
            if new_queue_response.data:
                queue = new_queue_response.data[0]
                queue["queue_items"] = []
                return queue
            raise HTTPException(status_code=500, detail="Failed to create queue")
        
        queue = queue_response.data[0]
        # Fetch queue items
        items_response = supabase.table("queue_items").select("*").eq(
            "queue_id", queue["id"]
        ).order("position").execute()
        
        all_items = items_response.data if items_response.data else []
        
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
        
        queues_response = supabase.table("queues").select("*").eq(
            "shop_id", shop_id
        ).order("date", desc=True).execute()
        
        queues = []
        if queues_response.data:
            for queue in queues_response.data:
                items_response = supabase.table("queue_items").select("*").eq(
                    "queue_id", queue["id"]
                ).order("position").execute()
                
                all_items = items_response.data if items_response.data else []
                
                # Renumber positions for active customers
                active_items = [item for item in all_items if item["status"] in [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]]
                for idx, item in enumerate(active_items, start=1):
                    item["position"] = idx
                
                # Populate employee details
                all_items = populate_employee_details(all_items)
                
                queue["queue_items"] = all_items
                queues.append(queue)
        
        return queues
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
        shop_response = supabase.table("shops").select("*").eq("id", shop_id).execute()
        if not shop_response.data:
            raise HTTPException(status_code=404, detail="Shop not found")
        shop = shop_response.data[0]
        
        # Check queue limit based on subscription tier
        try:
            from tier_limits import TIER_LIMITS
            active_queues = supabase.table("queues").select("id").eq(
                "shop_id", shop_id
            ).eq("is_active", True).execute()
            current_queue_count = len(active_queues.data) if active_queues.data else 0
            
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
        response = supabase.table("queues").insert(queue_data).execute()
        if response.data:
            queue = response.data[0]
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
        shop_response = supabase.table("shops").select("*").eq("id", shop_id).execute()
        if not shop_response.data:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        shop = shop_response.data[0]
        
        # Get shop owner to check their subscription tier
        owner_response = supabase.table("users").select("subscription_tier").eq("id", shop["owner_id"]).execute()
        owner_tier = owner_response.data[0]["subscription_tier"] if owner_response.data else "free"
        
        # Get or create active queue
        queue_response = supabase.table("queues").select("*").eq(
            "shop_id", shop_id
        ).eq("is_active", True).execute()
        
        if not queue_response.data:
            queue_data = {
                "shop_id": shop_id,
                "is_active": True,
                "name": "Main Queue"
            }
            new_queue_response = supabase.table("queues").insert(queue_data).execute()
            if not new_queue_response.data:
                raise HTTPException(status_code=500, detail="Failed to create queue")
            queue = new_queue_response.data[0]
        else:
            queue = queue_response.data[0]
        
        # Check queue size limit based on shop owner's subscription tier
        try:
            from tier_limits import TIER_LIMITS
            current_items = supabase.table("queue_items").select("id").eq(
                "queue_id", queue["id"]
            ).in_("status", [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]).execute()
            current_queue_size = len(current_items.data) if current_items.data else 0
            
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
        all_items = supabase.table("queue_items").select("position").eq(
            "queue_id", queue["id"]
        ).execute()
        max_position = max([item["position"] for item in all_items.data], default=0) if all_items.data else 0
        position = max_position + 1
        
        # Create queue item
        queue_item_data = queue_item.dict()
        queue_item_data["queue_id"] = queue["id"]
        queue_item_data["user_id"] = None  # Public queue, no user association
        queue_item_data["position"] = position
        queue_item_data["status"] = QUEUE_STATUS_WAITING
        
        response = supabase.table("queue_items").insert(queue_item_data).execute()
        if response.data:
            new_item = response.data[0]
            
            # Calculate the actual display position (sequential for active customers)
            active_items = supabase.table("queue_items").select("id").eq(
                "queue_id", queue["id"]
            ).in_("status", [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]).execute()
            
            # The display position is the count of active items
            new_item["position"] = len(active_items.data) if active_items.data else 1
            
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
        items_response = supabase.table("queue_items").select("*").eq(
            "queue_id", queue_id
        ).order("position").execute()
        return items_response.data if items_response.data else []
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
        item_response = supabase.table("queue_items").select("*").eq("id", item_id).execute()
        if not item_response.data:
            raise HTTPException(status_code=404, detail="Queue item not found")
        
        item = item_response.data[0]
        
        # Get shop_id from queue
        queue_response = supabase.table("queues").select("shop_id").eq("id", item["queue_id"]).execute()
        if not queue_response.data:
            raise HTTPException(status_code=404, detail="Queue not found")
        
        shop_id = queue_response.data[0]["shop_id"]
        
        # Check if user is owner or active employee
        check_shop_access(shop_id, current_user, require_owner=False)
        
        # Update status and timestamps
        update_data = {"status": new_status}
        if new_status == QUEUE_STATUS_BEING_SERVED:
            update_data["service_started_at"] = datetime.utcnow().isoformat()
        elif new_status in [QUEUE_STATUS_COMPLETED, QUEUE_STATUS_CANCELLED]:
            update_data["completed_at"] = datetime.utcnow().isoformat()
        
        supabase.table("queue_items").update(update_data).eq("id", item_id).execute()
        updated = supabase.table("queue_items").select("*").eq("id", item_id).execute()
        if updated.data:
            return updated.data[0]
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
    """Call the next customer in line (Shop Owner or Employee)
    
    Args:
        queue_id: Queue ID
        employee_id: Optional employee ID to assign. If None, random assignment from clocked-in employees
    """
    try:
        import random
        
        queue_response = supabase.table("queues").select("*").eq("id", queue_id).execute()
        if not queue_response.data:
            raise HTTPException(status_code=404, detail="Queue not found")
        
        queue = queue_response.data[0]
        shop_id = queue["shop_id"]
        
        # Check if user is owner or active employee
        check_shop_access(shop_id, current_user, require_owner=False)
        
        # Determine which employee to assign
        assigned_employee_id = employee_id
        
        if assigned_employee_id is None:
            # Random assignment: get clocked-in employees
            active_shifts = supabase.table("employee_shifts").select("user_id").eq(
                "shop_id", shop_id
            ).is_("clock_out", "null").execute()
            
            if active_shifts.data and len(active_shifts.data) > 0:
                # Randomly select from clocked-in employees
                available_employees = [shift["user_id"] for shift in active_shifts.data]
                assigned_employee_id = random.choice(available_employees)
            else:
                # No employees clocked in, assign to shop owner or current user
                shop_response = supabase.table("shops").select("owner_id").eq("id", shop_id).execute()
                if shop_response.data:
                    assigned_employee_id = shop_response.data[0]["owner_id"]
                else:
                    assigned_employee_id = current_user["id"]
        
        # Complete any currently serving customers first
        currently_serving = supabase.table("queue_items").select("id").eq(
            "queue_id", queue_id
        ).eq("status", QUEUE_STATUS_BEING_SERVED).execute()
        if currently_serving.data:
            for serving_item in currently_serving.data:
                supabase.table("queue_items").update({
                    "status": QUEUE_STATUS_COMPLETED,
                    "completed_at": datetime.utcnow().isoformat()
                }).eq("id", serving_item["id"]).execute()

        # Find next waiting customer
        items_response = supabase.table("queue_items").select("*").eq(
            "queue_id", queue_id
        ).eq("status", QUEUE_STATUS_WAITING).order("position").execute()
        
        if not items_response.data:
            raise HTTPException(status_code=404, detail="No customers waiting")
        
        next_item = items_response.data[0]
        
        update_data = {
            "status": QUEUE_STATUS_BEING_SERVED,
            "service_started_at": datetime.utcnow().isoformat(),
            "assigned_employee_id": assigned_employee_id
        }
        supabase.table("queue_items").update(update_data).eq("id", next_item["id"]).execute()
        updated = supabase.table("queue_items").select("*").eq("id", next_item["id"]).execute()
        
        if updated.data:
            result = updated.data[0]
            # Fetch employee details
            if result.get("assigned_employee_id"):
                employee_response = supabase.table("users").select(
                    "id, username, email, profile_photo_url"
                ).eq("id", result["assigned_employee_id"]).execute()
                if employee_response.data:
                    result["assigned_employee"] = employee_response.data[0]
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
        item_response = supabase.table("queue_items").select("*").eq("id", item_id).execute()
        if not item_response.data:
            raise HTTPException(status_code=404, detail="Queue item not found")
        
        item = item_response.data[0]
        
        # Get shop_id from queue
        queue_response = supabase.table("queues").select("shop_id").eq("id", item["queue_id"]).execute()
        if not queue_response.data:
            raise HTTPException(status_code=404, detail="Queue not found")
        
        shop_id = queue_response.data[0]["shop_id"]
        
        # Check if user is owner or active employee
        check_shop_access(shop_id, current_user, require_owner=False)
        
        # Mark as cancelled with reason
        update_data = {
            "status": QUEUE_STATUS_CANCELLED,
            "completed_at": datetime.utcnow().isoformat(),
            "notes": f"{item.get('notes', '')}\n[REMOVED: {reason}]" if item.get('notes') else f"[REMOVED: {reason}]"
        }
        
        supabase.table("queue_items").update(update_data).eq("id", item_id).execute()
        updated = supabase.table("queue_items").select("*").eq("id", item_id).execute()
        if updated.data:
            return {"message": "Customer removed from queue", "item": updated.data[0]}
        raise HTTPException(status_code=500, detail="Failed to remove customer (post-fetch failed)")
        
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
        item_response = supabase.table("queue_items").select("*").eq("id", item_id).execute()
        if not item_response.data:
            raise HTTPException(status_code=404, detail="Queue item not found")
        
        item = item_response.data[0]
        
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
        
        supabase.table("queue_items").update(update_data).eq("id", item_id).execute()
        updated = supabase.table("queue_items").select("*").eq("id", item_id).execute()
        if updated.data:
            return {"message": "You have left the queue", "item": updated.data[0]}
        raise HTTPException(status_code=500, detail="Failed to leave queue (post-fetch failed)")
        
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
    """Serve a specific customer (skip the queue) (Shop Owner or Employee)
    
    Args:
        item_id: Queue item ID
        employee_id: Optional employee ID to assign
    """
    try:
        # Get queue item
        item_response = supabase.table("queue_items").select("*").eq("id", item_id).execute()
        if not item_response.data:
            raise HTTPException(status_code=404, detail="Queue item not found")
        
        item = item_response.data[0]
        queue_id = item["queue_id"]
        
        # Get shop_id from queue
        queue_response = supabase.table("queues").select("shop_id").eq("id", queue_id).execute()
        if not queue_response.data:
            raise HTTPException(status_code=404, detail="Queue not found")
        
        shop_id = queue_response.data[0]["shop_id"]
        
        # Check if user is owner or active employee
        check_shop_access(shop_id, current_user, require_owner=False)
        
        # Check if customer is waiting
        if item["status"] != QUEUE_STATUS_WAITING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer is not in waiting status"
            )
        
        # First, complete any currently serving customers in this queue
        currently_serving = supabase.table("queue_items").select("*").eq(
            "queue_id", queue_id
        ).eq("status", QUEUE_STATUS_BEING_SERVED).execute()
        
        if currently_serving.data:
            for serving_item in currently_serving.data:
                supabase.table("queue_items").update({
                    "status": QUEUE_STATUS_COMPLETED,
                    "completed_at": datetime.utcnow().isoformat()
                }).eq("id", serving_item["id"]).execute()
        
        # Determine employee assignment
        assigned_employee_id = employee_id if employee_id else current_user["id"]
        
        # Now serve the selected customer
        update_data = {
            "status": QUEUE_STATUS_BEING_SERVED,
            "service_started_at": datetime.utcnow().isoformat(),
            "assigned_employee_id": assigned_employee_id
        }
        
        # Perform update
        supabase.table("queue_items").update(update_data).eq("id", item_id).execute()
        # Fetch updated row explicitly
        fetch = supabase.table("queue_items").select("*").eq("id", item_id).execute()
        if fetch.data:
            return {"message": "Now serving customer", "item": fetch.data[0]}
        raise HTTPException(status_code=500, detail="Failed to serve customer (post-fetch failed)")
        
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
        item_response = supabase.table("queue_items").select("*").eq("id", item_id).execute()
        if not item_response.data:
            raise HTTPException(status_code=404, detail="Queue item not found")
        
        item = item_response.data[0]
        
        # Count how many people are ahead
        ahead_response = supabase.table("queue_items").select("id").eq(
            "queue_id", item["queue_id"]
        ).lt("position", item["position"]).in_(
            "status", [QUEUE_STATUS_WAITING, QUEUE_STATUS_BEING_SERVED]
        ).execute()
        ahead = len(ahead_response.data) if ahead_response.data else 0
        
        # Get shop's average service time
        queue_response = supabase.table("queues").select("shop_id").eq("id", item["queue_id"]).execute()
        if not queue_response.data:
            raise HTTPException(status_code=404, detail="Queue not found")
        
        shop_response = supabase.table("shops").select("average_service_time").eq(
            "id", queue_response.data[0]["shop_id"]
        ).execute()
        
        average_service_time = shop_response.data[0]["average_service_time"] if shop_response.data else 30
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
