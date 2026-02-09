import requests
import sys
import time
from typing import Dict, Any

# --- Configuration ---
BASE_URL = "http://localhost:8000/api"
TEST_OWNER_EMAIL = "test_owner_rigorous@example.com"
TEST_OWNER_PASSWORD = "password123"
TEST_OWNER_USERNAME = "rigorous_owner"

def log_test(name: str, status: bool, detail: str = ""):
    icon = "✅" if status else "❌"
    print(f"{icon} {name}: {'PASSED' if status else 'FAILED'} {f'({detail})' if detail else ''}")

class RigorousBackendTester:
    def __init__(self):
        self.session = requests.Session()
        self.owner_token = None
        self.customer_token = None
        self.free_owner_email = None
        self.prem_owner_email = None
        self.last_shop_id = None

    def find_seeded_accounts(self):
        """Find accounts created by the seeding script to test with."""
        # For simplicity, we'll create a fresh one for this test or use known seeds
        # Here we'll just register a new one to test the full flow
        pass

    def test_auth_flow(self):
        print("\n--- Testing Auth Flow ---")
        # 1. Register (Endpoint: POST /api/users)
        register_data = {
            "email": TEST_OWNER_EMAIL,
            "username": TEST_OWNER_USERNAME,
            "password": TEST_OWNER_PASSWORD,
            "role": "shop_owner"
        }
        resp = self.session.post(f"{BASE_URL}/users", json=register_data)
        if resp.status_code == 400 and "already registered" in resp.text:
            log_test("Register Owner", True, "Already exists")
        else:
            log_test("Register Owner", resp.status_code == 201 or resp.status_code == 200, resp.text)

        # 2. Login (Endpoint: POST /api/auth/token)
        # Note: OAuth2PasswordRequestForm expects form-data (application/x-www-form-urlencoded)
        login_data = {
            "username": TEST_OWNER_USERNAME,
            "password": TEST_OWNER_PASSWORD
        }
        resp = self.session.post(f"{BASE_URL}/auth/token", data=login_data)
        if resp.status_code == 200:
            self.owner_token = resp.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.owner_token}"})
            log_test("Login Owner", True)
        else:
            log_test("Login Owner", False, resp.content.decode())

    def test_shop_management(self):
        print("\n--- Testing Shop Management ---")
        # Create a shop (Endpoint: POST /api/shops/)
        shop_data = {
            "name": "Rigorous Test Shop",
            "shop_type": "barbershop",
            "address": "999 Testing Ave",
            "city": "Test City",
            "state": "TS",
            "zip_code": "12345",
            "phone": "+1-555-000-0000",
            "average_service_time": 20
        }
        resp = self.session.post(f"{BASE_URL}/shops/", json=shop_data)
        if resp.status_code in [200, 201]:
            self.last_shop_id = resp.json().get("id")
            log_test("Create Shop", True, f"ID: {self.last_shop_id}")
        else:
            log_test("Create Shop", False, resp.text)

        # List shops
        resp = self.session.get(f"{BASE_URL}/shops/")
        log_test("List Shops", resp.status_code == 200, f"Count: {len(resp.json()) if resp.status_code == 200 else 0}")

    def test_queue_operations(self):
        print("\n--- Testing Queue Operations ---")
        if not self.last_shop_id:
            log_test("Queue Ops", False, "No shop ID available")
            return

        # 1. Get/Create Queue (Endpoint: GET /api/queues/shop/{shop_id}/active)
        resp = self.session.get(f"{BASE_URL}/queues/shop/{self.last_shop_id}/active")
        if resp.status_code == 200:
            queue_data = resp.json()
            queue_id = queue_data.get("id")
            log_test("Get Active Queue", True, f"ID: {queue_id}")
        else:
            log_test("Get Active Queue", False, resp.text)
            return

        # 2. Join Queue (Endpoint: POST /api/queues/shop/{shop_id}/join)
        join_data = {
            "customer_name": "Rigorous Customer",
            "customer_phone": "+1-555-999-8888"
        }
        resp = self.session.post(f"{BASE_URL}/queues/shop/{self.last_shop_id}/join", json=join_data)
        if resp.status_code in [200, 201]:
            queue_item_id = resp.json().get("id")
            log_test("Join Queue", True, f"Item ID: {queue_item_id}")
        else:
            log_test("Join Queue", False, resp.text)
            return

        # 3. Update Status (as owner) (Endpoint: PATCH /api/queues/items/{item_id}/status)
        resp = self.session.patch(f"{BASE_URL}/queues/items/{queue_item_id}/status", params={"new_status": "being_served"})
        log_test("Serve Customer", resp.status_code == 200, resp.text)

    def test_tier_restrictions_simulation(self):
        print("\n--- Testing Tier Restrictions (Simulation) ---")
        # Check current user tier (Endpoint: GET /api/users/me)
        resp = self.session.get(f"{BASE_URL}/users/me")
        if resp.status_code == 200:
            tier = resp.json().get("subscription_tier")
            log_test("Verify Tier", True, f"Current: {tier}")
        else:
            log_test("Verify Tier", False, resp.text)

    def run_all(self):
        try:
            self.test_auth_flow()
            self.test_shop_management()
            self.test_queue_operations()
            self.test_tier_restrictions_simulation()
            print("\n✅ Rigorous Backend Testing Finished!")
        except Exception as e:
            print(f"\n❌ Error during testing: {e}")

if __name__ == "__main__":
    tester = RigorousBackendTester()
    tester.run_all()
