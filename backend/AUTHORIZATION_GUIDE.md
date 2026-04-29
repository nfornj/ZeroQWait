# Authorization Quick Reference Guide

## Purpose

Use this guide when adding or reviewing protected backend endpoints.

The current authorization model is application-level and shop-scoped:

- JWT authentication establishes the current user
- permission helpers enforce owner or employee access
- public endpoints may use optional auth and sanitize data for non-staff users

## Step 1: Choose Authentication Type

### Required Authentication

```python
from fastapi import Depends
from auth_utils import get_current_user

@router.get("/protected-endpoint")
def my_endpoint(current_user: dict = Depends(get_current_user)):
    return {"user_id": current_user["id"]}
```

Use this for owner workspaces, employee tools, analytics, approvals, and any write endpoint that should not be public.

### Optional Authentication

```python
from typing import Optional
from fastapi import Depends
from auth_utils import get_current_user_optional

@router.get("/public-endpoint")
def my_endpoint(current_user: Optional[dict] = Depends(get_current_user_optional)):
    if current_user:
        return {"authenticated": True, "user_id": current_user["id"]}
    return {"authenticated": False}
```

Use this for public shop or queue views where authenticated staff may see more detail than customers or anonymous visitors.

## Step 2: Add Shop Authorization

### Owner-Only Shop Operation

```python
from permissions import check_shop_access

@router.put("/shops/{shop_id}/settings")
def update_shop_settings(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
):
    check_shop_access(shop_id, current_user, require_owner=True)
    return {"ok": True}
```

Use for:

- shop settings
- employee management
- owner analytics
- approval-gated owner actions

### Owner Or Employee Operation

```python
from permissions import check_shop_access
from db_interface import db_interface

@router.post("/queues/{queue_id}/call-next")
def call_next(
    queue_id: int,
    current_user: dict = Depends(get_current_user),
):
    queue = db_interface.get_queue_by_id(queue_id)
    check_shop_access(queue["shop_id"], current_user, require_owner=False)
    return {"ok": True}
```

Use for:

- queue serving actions
- employee shift operations tied to a shop
- staff-facing queue views

### Queue Item Access Helper

```python
from permissions import verify_queue_item_access

@router.patch("/queues/items/{item_id}/status")
def update_status(
    item_id: int,
    current_user: dict = Depends(get_current_user),
):
    access_data = verify_queue_item_access(item_id, current_user, require_owner=False)
    queue_item = access_data["queue_item"]
    return {"item_id": queue_item["id"]}
```

Use this when the request starts from a queue item and the permission check needs to trace back to the shop.

## Step 3: Sanitize Public Data

```python
from typing import Optional
from fastapi import Depends
from auth_utils import get_current_user_optional
from permissions import sanitize_queue_data_for_public

@router.get("/shops/{shop_id}/public-queue")
def get_public_queue(
    shop_id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    queue = {"queue_items": []}
    return sanitize_queue_data_for_public(queue, current_user, shop_id)
```

Use this when returning queue or staffing-adjacent data to public or customer-facing surfaces.

The helper removes employee assignment details unless the current user is authenticated staff for that shop.

## Common Patterns

### Role-Specific Check

```python
from fastapi import HTTPException, status

if current_user.get("role") != "employee":
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Employees only",
    )
```

Use role checks only when the action is not fundamentally shop-scoped, or when a specific actor type is required in addition to shop access.

### Preferred Error Handling

Let helpers raise the correct errors whenever possible.

```python
check_shop_access(shop_id, current_user, require_owner=True)
```

Avoid duplicating manual ownership checks in every route.

## Test Guidance

When adding a new protected endpoint, cover at least these cases:

- unauthenticated access returns `401` when auth is required
- wrong owner or unrelated employee returns `403` or `404`, depending on endpoint behavior
- valid owner succeeds
- valid assigned employee succeeds when employee access is intended
- public output is sanitized when employee data should be hidden

Example test shape:

```python
def test_other_owner_cannot_update_shop(client, owner_b_token, shop_a):
    response = client.put(
        f"/api/shops/{shop_a['id']}",
        json={"name": "Blocked"},
        headers={"Authorization": f"Bearer {owner_b_token}"},
    )
    assert response.status_code == 403
```

## Common Mistakes To Avoid

- Do not trust client-provided user identifiers for authorization.
- Do not skip shop access checks on shop-owned resources.
- Do not return internal staffing data from public endpoints without sanitization.

## Quick Checklist

- [ ] Does the endpoint require auth or optional auth?
- [ ] Is the action shop-scoped?
- [ ] Should it be owner-only or owner-plus-employee?
- [ ] Does the response expose employee or internal staffing data?
- [ ] Is there a focused authorization test for the new behavior?

## Related Files

- `permissions.py`
- `auth_utils.py`
- `db_interface.py`
- `tests/test_multi_tenancy.py`
