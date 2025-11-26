"""
Multi-Tenancy Security Integration Tests

These tests verify that:
1. Shop Owner A cannot access Shop Owner B's data
2. Shop Owner A cannot modify Shop Owner B's queues
3. Employee of Shop A cannot access Shop B's data
4. Customers can view public shop data but not employee details
5. Unauthenticated users can only access public endpoints
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from supabase_client import supabase
from auth_utils import get_password_hash, create_access_token

client = TestClient(app)

# Test fixtures and setup
@pytest.fixture(scope="module")
def test_users():
    """Create test users for different roles"""
    users = {}
    
    # Shop Owner A
    owner_a_data = {
        "username": "owner_a_test",
        "email": "owner_a@test.com",
        "hashed_password": get_password_hash("password123"),
        "role": "shop_owner",
        "is_active": True
    }
    users["owner_a"] = supabase.table("users").insert(owner_a_data).execute().data[0]
    users["owner_a_token"] = create_access_token({"sub": "owner_a_test"})
    
    # Shop Owner B
    owner_b_data = {
        "username": "owner_b_test",
        "email": "owner_b@test.com",
        "hashed_password": get_password_hash("password123"),
        "role": "shop_owner",
        "is_active": True
    }
    users["owner_b"] = supabase.table("users").insert(owner_b_data).execute().data[0]
    users["owner_b_token"] = create_access_token({"sub": "owner_b_test"})
    
    # Employee for Shop A
    employee_a_data = {
        "username": "employee_a_test",
        "email": "employee_a@test.com",
        "hashed_password": get_password_hash("password123"),
        "role": "employee",
        "is_active": True
    }
    users["employee_a"] = supabase.table("users").insert(employee_a_data).execute().data[0]
    users["employee_a_token"] = create_access_token({"sub": "employee_a_test"})
    
    # Customer
    customer_data = {
        "username": "customer_test",
        "email": "customer@test.com",
        "hashed_password": get_password_hash("password123"),
        "role": "customer",
        "is_active": True
    }
    users["customer"] = supabase.table("users").insert(customer_data).execute().data[0]
    users["customer_token"] = create_access_token({"sub": "customer_test"})
    
    yield users
    
    # Cleanup
    supabase.table("users").delete().eq("username", "owner_a_test").execute()
    supabase.table("users").delete().eq("username", "owner_b_test").execute()
    supabase.table("users").delete().eq("username", "employee_a_test").execute()
    supabase.table("users").delete().eq("username", "customer_test").execute()


@pytest.fixture(scope="module")
def test_shops(test_users):
    """Create test shops"""
    shops = {}
    
    # Shop A owned by Owner A
    shop_a_data = {
        "name": "Shop A Test",
        "owner_id": test_users["owner_a"]["id"],
        "shop_type": "barbershop",
        "address": "123 Test St",
        "city": "Test City",
        "state": "TS",
        "zip_code": "12345",
        "country": "Test Country",
        "phone": "123-456-7890",
        "slug": "shop-a-test",
        "is_active": True
    }
    shops["shop_a"] = supabase.table("shops").insert(shop_a_data).execute().data[0]
    
    # Shop B owned by Owner B
    shop_b_data = {
        "name": "Shop B Test",
        "owner_id": test_users["owner_b"]["id"],
        "shop_type": "barbershop",
        "address": "456 Test Ave",
        "city": "Test City",
        "state": "TS",
        "zip_code": "12345",
        "country": "Test Country",
        "phone": "098-765-4321",
        "slug": "shop-b-test",
        "is_active": True
    }
    shops["shop_b"] = supabase.table("shops").insert(shop_b_data).execute().data[0]
    
    # Create queues for both shops
    queue_a_data = {
        "shop_id": shops["shop_a"]["id"],
        "name": "Main Queue",
        "is_active": True
    }
    shops["queue_a"] = supabase.table("queues").insert(queue_a_data).execute().data[0]
    
    queue_b_data = {
        "shop_id": shops["shop_b"]["id"],
        "name": "Main Queue",
        "is_active": True
    }
    shops["queue_b"] = supabase.table("queues").insert(queue_b_data).execute().data[0]
    
    # Link Employee A to Shop A
    employee_link_data = {
        "shop_id": shops["shop_a"]["id"],
        "user_id": test_users["employee_a"]["id"],
        "is_active": True,
        "created_by": test_users["owner_a"]["id"]
    }
    supabase.table("shop_employees").insert(employee_link_data).execute()
    
    yield shops
    
    # Cleanup
    supabase.table("shop_employees").delete().eq("shop_id", shops["shop_a"]["id"]).execute()
    supabase.table("queues").delete().eq("id", shops["queue_a"]["id"]).execute()
    supabase.table("queues").delete().eq("id", shops["queue_b"]["id"]).execute()
    supabase.table("shops").delete().eq("id", shops["shop_a"]["id"]).execute()
    supabase.table("shops").delete().eq("id", shops["shop_b"]["id"]).execute()


# =====================================================================
# TEST 1: Shop Owner Isolation
# =====================================================================

def test_owner_cannot_view_other_owners_shop_list(test_users, test_shops):
    """Owner A should only see their own shops, not Owner B's"""
    headers = {"Authorization": f"Bearer {test_users['owner_a_token']}"}
    response = client.get("/api/shops/my-shops", headers=headers)
    
    assert response.status_code == 200
    shops = response.json()
    shop_ids = [shop["id"] for shop in shops]
    
    # Owner A should see Shop A
    assert test_shops["shop_a"]["id"] in shop_ids
    # Owner A should NOT see Shop B
    assert test_shops["shop_b"]["id"] not in shop_ids


def test_owner_cannot_update_other_owners_shop(test_users, test_shops):
    """Owner A should not be able to update Owner B's shop"""
    headers = {"Authorization": f"Bearer {test_users['owner_a_token']}"}
    update_data = {"name": "Hacked Shop Name"}
    
    response = client.put(
        f"/api/shops/{test_shops['shop_b']['id']}",
        json=update_data,
        headers=headers
    )
    
    # Should get 403 Forbidden or 404 Not Found
    assert response.status_code in [403, 404]


def test_owner_cannot_delete_other_owners_shop(test_users, test_shops):
    """Owner A should not be able to delete Owner B's shop"""
    headers = {"Authorization": f"Bearer {test_users['owner_a_token']}"}
    
    response = client.delete(
        f"/api/shops/{test_shops['shop_b']['id']}",
        headers=headers
    )
    
    # Should get 403 Forbidden or 404 Not Found
    assert response.status_code in [403, 404]


# =====================================================================
# TEST 2: Queue Management Isolation
# =====================================================================

def test_owner_cannot_view_other_owners_queues(test_users, test_shops):
    """Owner A should not be able to view Owner B's queue details"""
    headers = {"Authorization": f"Bearer {test_users['owner_a_token']}"}
    
    response = client.get(
        f"/api/queues/shop/{test_shops['shop_b']['id']}/all",
        headers=headers
    )
    
    # Should get 403 Forbidden
    assert response.status_code == 403


def test_owner_cannot_create_queue_for_other_shop(test_users, test_shops):
    """Owner A should not be able to create a queue for Owner B's shop"""
    headers = {"Authorization": f"Bearer {test_users['owner_a_token']}"}
    queue_data = {"name": "Hacked Queue"}
    
    response = client.post(
        f"/api/queues/shop/{test_shops['shop_b']['id']}",
        json=queue_data,
        headers=headers
    )
    
    # Should get 403 Forbidden
    assert response.status_code == 403


def test_owner_cannot_modify_other_owners_queue_items(test_users, test_shops):
    """Owner A should not be able to call next customer in Owner B's queue"""
    # First, add a customer to Shop B's queue
    customer_data = {
        "customer_name": "Test Customer",
        "customer_phone": "555-0000"
    }
    join_response = client.post(
        f"/api/queues/shop/{test_shops['shop_b']['id']}/join",
        json=customer_data
    )
    assert join_response.status_code == 200
    queue_item = join_response.json()
    
    # Now try to call next as Owner A
    headers = {"Authorization": f"Bearer {test_users['owner_a_token']}"}
    response = client.post(
        f"/api/queues/{test_shops['queue_b']['id']}/call-next",
        headers=headers
    )
    
    # Should get 403 Forbidden
    assert response.status_code == 403
    
    # Cleanup
    supabase.table("queue_items").delete().eq("id", queue_item["id"]).execute()


# =====================================================================
# TEST 3: Employee Access Control
# =====================================================================

def test_employee_can_access_own_shop(test_users, test_shops):
    """Employee A should be able to access Shop A's queue"""
    headers = {"Authorization": f"Bearer {test_users['employee_a_token']}"}
    
    response = client.get(
        f"/api/queues/shop/{test_shops['shop_a']['id']}/all",
        headers=headers
    )
    
    # Should succeed
    assert response.status_code == 200


def test_employee_cannot_access_other_shop(test_users, test_shops):
    """Employee A should NOT be able to access Shop B's queue"""
    headers = {"Authorization": f"Bearer {test_users['employee_a_token']}"}
    
    response = client.get(
        f"/api/queues/shop/{test_shops['shop_b']['id']}/all",
        headers=headers
    )
    
    # Should get 403 Forbidden
    assert response.status_code == 403


def test_employee_cannot_add_employees(test_users, test_shops):
    """Employees should not be able to add other employees"""
    headers = {"Authorization": f"Bearer {test_users['employee_a_token']}"}
    new_employee_data = {
        "username": "new_employee_test",
        "email": "new_employee@test.com",
        "password": "password123"
    }
    
    response = client.post(
        f"/api/employees/shops/{test_shops['shop_a']['id']}/employees",
        json=new_employee_data,
        headers=headers
    )
    
    # Should get 403 Forbidden
    assert response.status_code == 403


def test_employee_cannot_modify_shop_settings(test_users, test_shops):
    """Employees should not be able to modify shop settings"""
    headers = {"Authorization": f"Bearer {test_users['employee_a_token']}"}
    update_data = {"name": "Modified Shop Name"}
    
    response = client.put(
        f"/api/shops/{test_shops['shop_a']['id']}",
        json=update_data,
        headers=headers
    )
    
    # Should get 403 Forbidden
    assert response.status_code == 403


# =====================================================================
# TEST 4: Public Endpoint Data Sanitization
# =====================================================================

def test_public_endpoint_hides_employee_data(test_users, test_shops):
    """Public shop endpoint should not expose employee assignment details"""
    # Add queue item with employee assignment
    customer_data = {
        "customer_name": "Test Customer",
        "customer_phone": "555-1111"
    }
    join_response = client.post(
        f"/api/queues/shop/{test_shops['shop_a']['id']}/join",
        json=customer_data
    )
    queue_item = join_response.json()
    
    # Assign employee to this item (as owner)
    headers_owner = {"Authorization": f"Bearer {test_users['owner_a_token']}"}
    client.post(
        f"/api/queues/items/{queue_item['id']}/serve",
        json={"employee_id": test_users["employee_a"]["id"]},
        headers=headers_owner
    )
    
    # Now fetch as unauthenticated user
    response = client.get(f"/api/shops/{test_shops['shop_a']['id']}")
    
    assert response.status_code == 200
    shop_data = response.json()
    
    # Check that employee data is sanitized
    if shop_data.get("queues"):
        for queue in shop_data["queues"]:
            if queue.get("queue_items"):
                for item in queue["queue_items"]:
                    # Employee details should be removed or None
                    assert item.get("assigned_employee") is None
                    assert item.get("assigned_employee_id") is None
    
    # Cleanup
    supabase.table("queue_items").delete().eq("id", queue_item["id"]).execute()


def test_authenticated_staff_sees_employee_data(test_users, test_shops):
    """Shop owner should see employee assignment details"""
    # Add queue item with employee assignment
    customer_data = {
        "customer_name": "Test Customer 2",
        "customer_phone": "555-2222"
    }
    join_response = client.post(
        f"/api/queues/shop/{test_shops['shop_a']['id']}/join",
        json=customer_data
    )
    queue_item = join_response.json()
    
    # Assign employee to this item
    headers_owner = {"Authorization": f"Bearer {test_users['owner_a_token']}"}
    client.post(
        f"/api/queues/items/{queue_item['id']}/serve",
        json={"employee_id": test_users["employee_a"]["id"]},
        headers=headers_owner
    )
    
    # Now fetch as shop owner
    response = client.get(
        f"/api/shops/{test_shops['shop_a']['id']}",
        headers=headers_owner
    )
    
    assert response.status_code == 200
    shop_data = response.json()
    
    # Check that employee data is visible to owner
    found_employee_data = False
    if shop_data.get("queues"):
        for queue in shop_data["queues"]:
            if queue.get("queue_items"):
                for item in queue["queue_items"]:
                    if item.get("id") == queue_item["id"]:
                        # Owner should see employee assignment
                        assert item.get("assigned_employee_id") == test_users["employee_a"]["id"]
                        found_employee_data = True
    
    assert found_employee_data, "Owner should see employee assignment"
    
    # Cleanup
    supabase.table("queue_items").delete().eq("id", queue_item["id"]).execute()


# =====================================================================
# TEST 5: Customer Access Control
# =====================================================================

def test_customer_can_join_queue(test_users, test_shops):
    """Customers should be able to join any shop's queue"""
    customer_data = {
        "customer_name": "Test Customer 3",
        "customer_phone": "555-3333"
    }
    
    response = client.post(
        f"/api/queues/shop/{test_shops['shop_a']['id']}/join",
        json=customer_data
    )
    
    assert response.status_code == 200
    queue_item = response.json()
    
    # Cleanup
    supabase.table("queue_items").delete().eq("id", queue_item["id"]).execute()


def test_customer_cannot_manage_queue(test_users, test_shops):
    """Customers should not be able to call next customer"""
    headers = {"Authorization": f"Bearer {test_users['customer_token']}"}
    
    response = client.post(
        f"/api/queues/{test_shops['queue_a']['id']}/call-next",
        headers=headers
    )
    
    # Should get 403 Forbidden
    assert response.status_code == 403


def test_customer_cannot_view_shop_management_endpoints(test_users, test_shops):
    """Customers should not access shop management endpoints"""
    headers = {"Authorization": f"Bearer {test_users['customer_token']}"}
    
    response = client.get(
        f"/api/queues/shop/{test_shops['shop_a']['id']}/all",
        headers=headers
    )
    
    # Should get 403 Forbidden
    assert response.status_code == 403


# =====================================================================
# TEST 6: Unauthenticated Access
# =====================================================================

def test_unauthenticated_can_view_public_shop(test_shops):
    """Unauthenticated users should be able to view shop details"""
    response = client.get(f"/api/shops/{test_shops['shop_a']['id']}")
    
    assert response.status_code == 200
    shop_data = response.json()
    assert shop_data["id"] == test_shops["shop_a"]["id"]


def test_unauthenticated_can_join_queue(test_shops):
    """Unauthenticated users should be able to join queue"""
    customer_data = {
        "customer_name": "Anonymous Customer",
        "customer_phone": "555-4444"
    }
    
    response = client.post(
        f"/api/queues/shop/{test_shops['shop_a']['id']}/join",
        json=customer_data
    )
    
    assert response.status_code == 200
    queue_item = response.json()
    
    # Cleanup
    supabase.table("queue_items").delete().eq("id", queue_item["id"]).execute()


def test_unauthenticated_cannot_manage_shop(test_shops):
    """Unauthenticated users should not be able to update shop"""
    update_data = {"name": "Hacked Name"}
    
    response = client.put(
        f"/api/shops/{test_shops['shop_a']['id']}",
        json=update_data
    )
    
    # Should get 401 Unauthorized
    assert response.status_code == 401


def test_unauthenticated_cannot_manage_queue(test_shops):
    """Unauthenticated users should not be able to call next customer"""
    response = client.post(f"/api/queues/{test_shops['queue_a']['id']}/call-next")
    
    # Should get 401 Unauthorized
    assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
