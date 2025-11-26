# Authorization Quick Reference Guide

## For Developers: How to Add Authorization to New Endpoints

### Step 1: Choose Authentication Type

#### Required Authentication (most endpoints)
```python
from fastapi import Depends
from auth_utils import get_current_user

@router.get("/protected-endpoint")
def my_endpoint(current_user: dict = Depends(get_current_user)):
    # User must be authenticated
    # current_user will never be None
    pass
```

#### Optional Authentication (public endpoints that show different data based on auth)
```python
from fastapi import Depends
from typing import Optional
from auth_utils import get_current_user_optional

@router.get("/public-endpoint")
def my_endpoint(current_user: Optional[dict] = Depends(get_current_user_optional)):
    # current_user can be None (unauthenticated)
    # Check if current_user is not None before using
    pass
```

### Step 2: Add Authorization Check

#### For Shop-Related Endpoints
```python
from permissions import check_shop_access

@router.put("/shops/{shop_id}/update")
def update_shop(
    shop_id: int,
    current_user: dict = Depends(get_current_user)
):
    # Only shop owner can update
    check_shop_access(shop_id, current_user, require_owner=True)
    
    # Your logic here
    pass
```

#### For Queue Management Endpoints
```python
from permissions import check_shop_access

@router.post("/queues/{queue_id}/call-next")
def call_next(
    queue_id: int,
    current_user: dict = Depends(get_current_user)
):
    # Get shop_id from queue
    queue = supabase.table("queues").select("shop_id").eq("id", queue_id).execute()
    shop_id = queue.data[0]["shop_id"]
    
    # Owner OR employee can call next
    check_shop_access(shop_id, current_user, require_owner=False)
    
    # Your logic here
    pass
```

#### For Queue Item Endpoints (Alternative Helper)
```python
from permissions import verify_queue_item_access

@router.put("/queue-items/{item_id}/status")
def update_status(
    item_id: int,
    current_user: dict = Depends(get_current_user)
):
    # Automatically traces item → queue → shop and checks access
    access_data = verify_queue_item_access(item_id, current_user, require_owner=False)
    
    # access_data contains: queue_item, queue, shop_id
    queue_item = access_data["queue_item"]
    
    # Your logic here
    pass
```

### Step 3: Sanitize Public Data (if needed)

#### For Endpoints That Return Shop/Queue Data
```python
from typing import Optional
from fastapi import Depends
from auth_utils import get_current_user_optional
from permissions import sanitize_queue_data_for_public

@router.get("/shops/{shop_id}")
def get_shop(
    shop_id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    # Fetch shop data
    shop = supabase.table("shops").select("*").eq("id", shop_id).execute().data[0]
    
    # Fetch queues with items
    queues = supabase.table("queues").select("*").eq("shop_id", shop_id).execute().data
    
    for queue in queues:
        # Fetch items
        items = supabase.table("queue_items").select("*").eq("queue_id", queue["id"]).execute().data
        queue["queue_items"] = items
        
        # Sanitize employee data for non-staff users
        queue = sanitize_queue_data_for_public(queue, current_user, shop_id)
    
    shop["queues"] = queues
    return shop
```

## Common Authorization Patterns

### Pattern: Owner-Only Operation
```python
check_shop_access(shop_id, current_user, require_owner=True)
```

**Use for**:
- Creating/deleting shops
- Adding/removing employees
- Modifying shop settings
- Viewing analytics

### Pattern: Owner OR Employee Operation
```python
check_shop_access(shop_id, current_user, require_owner=False)
```

**Use for**:
- Managing queue items
- Calling next customer
- Viewing queue details
- Serving customers

### Pattern: Role-Based Check
```python
if current_user.get("role") != "shop_owner":
    raise HTTPException(status_code=403, detail="Shop owners only")
```

**Use for**:
- Creating shops (shop_owner role required)
- Clock in/out (employee role required)

## Error Handling

### Authorization Errors
```python
from fastapi import HTTPException, status

# 401 Unauthorized - User not authenticated
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required"
)

# 403 Forbidden - User authenticated but lacks permission
raise HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Access denied"
)

# 404 Not Found - Resource doesn't exist OR user doesn't have access
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Shop not found"
)
```

### Best Practice: Let Helpers Handle Errors
```python
# ✅ GOOD - helper raises appropriate exceptions
check_shop_access(shop_id, current_user, require_owner=True)

# ❌ BAD - manual checks are error-prone
shop = supabase.table("shops").select("*").eq("id", shop_id).execute()
if shop.data[0]["owner_id"] != current_user["id"]:
    raise HTTPException(status_code=403, detail="Access denied")
```

## Testing Authorization

### Test Template
```python
def test_unauthorized_access():
    # Setup: Create shop owned by owner_a
    shop_a = create_test_shop(owner_a["id"])
    
    # Test: Try to access as owner_b
    headers = {"Authorization": f"Bearer {owner_b_token}"}
    response = client.put(f"/api/shops/{shop_a['id']}", json={"name": "Hacked"}, headers=headers)
    
    # Assert: Should be denied
    assert response.status_code == 403
```

## Quick Checklist for New Endpoints

- [ ] Does this endpoint need authentication?
  - Yes → Use `get_current_user`
  - No/Optional → Use `get_current_user_optional`

- [ ] Does this endpoint access shop data?
  - Yes → Add `check_shop_access()` call
  - Owner only? → `require_owner=True`
  - Owner or employee? → `require_owner=False`

- [ ] Does this endpoint return employee data?
  - Yes → Use `sanitize_queue_data_for_public()`
  - Show to staff only, hide from public

- [ ] Have you written tests?
  - Test as shop owner (should succeed)
  - Test as different shop owner (should fail)
  - Test as employee (should succeed/fail based on logic)
  - Test as unauthenticated user (should fail or show public data)

## Common Mistakes to Avoid

### ❌ Don't: Trust client-provided user_id
```python
def bad_endpoint(user_id: int):
    # User can pass any user_id!
    pass
```

### ✅ Do: Use authenticated user from token
```python
def good_endpoint(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    # user_id is verified from JWT
    pass
```

### ❌ Don't: Forget to check shop ownership
```python
def bad_endpoint(shop_id: int, current_user: dict = Depends(get_current_user)):
    # Missing authorization check!
    shop = supabase.table("shops").select("*").eq("id", shop_id).execute()
    return shop
```

### ✅ Do: Always verify access
```python
def good_endpoint(shop_id: int, current_user: dict = Depends(get_current_user)):
    check_shop_access(shop_id, current_user, require_owner=True)
    shop = supabase.table("shops").select("*").eq("id", shop_id).execute()
    return shop
```

### ❌ Don't: Expose sensitive data in public endpoints
```python
def bad_endpoint(shop_id: int):
    # Returns employee names, photos, etc. to anyone!
    return supabase.table("shops").select("*, queues(*, queue_items(*))").execute()
```

### ✅ Do: Sanitize public data
```python
def good_endpoint(shop_id: int, current_user: Optional[dict] = Depends(get_current_user_optional)):
    shop = fetch_shop_with_queues(shop_id)
    for queue in shop["queues"]:
        queue = sanitize_queue_data_for_public(queue, current_user, shop_id)
    return shop
```

## Additional Resources

- **Full documentation**: `SECURITY_IMPROVEMENTS.md`
- **Integration tests**: `backend/tests/test_multi_tenancy.py`
- **Helper functions**: `backend/permissions.py`
- **Auth utilities**: `backend/auth_utils.py`

## Questions?

Review the existing endpoints in:
- `backend/routers/shops.py` - Shop authorization examples
- `backend/routers/queues.py` - Queue authorization examples
- `backend/routers/employees.py` - Employee authorization examples
