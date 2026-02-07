import requests
import time
import sys

BASE_URL = "http://192.168.2.88.nip.io/api"
EMAIL = f"test_deploy_{int(time.time())}@example.com"
PASSWORD = "password123"
SHOP_NAME = f"Test Shop {int(time.time())}"
SLUG = f"test-shop-{int(time.time())}"

def run_test():
    print(f"🚀 Starting verification against {BASE_URL}")
    s = requests.Session()

    # 1. Health Check
    print("\n1. Checking API Root...")
    try:
        r = s.get(f"{BASE_URL}/")
        print(f"   Status: {r.status_code}")
        if r.status_code == 404:
             print("   (404 is expected for root /api/ if no index route exists there, assuming service is up)")
        elif r.status_code != 200:
             print(f"   ❌ Failed: {r.text}")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return

    # 2. Register
    print(f"\n2. Registering user {EMAIL}...")
    payload = {
        "email": EMAIL,
        "password": PASSWORD,
        "username": EMAIL.split('@')[0], # Use part of email as username
        "full_name": "Test User",
        "phone": "555-0199"
    }
    # Using /users endpoint as per backend implementation
    r = s.post(f"{BASE_URL}/users", json=payload)
    if r.status_code == 200 or r.status_code == 201:
        print("   ✅ Registered")
        user_data = r.json()
    else:
        print(f"   ❌ Failed: {r.status_code} - {r.text}")
        return

    # 3. Login
    print("\n3. Logging in...")
    login_payload = {
        "username": EMAIL,
        "password": PASSWORD
    }
    # Using x-www-form-urlencoded as per OAuth2 standard usually expected by FastAPI security
    r = s.post(f"{BASE_URL}/auth/token", data=login_payload)
    if r.status_code == 200:
        print("   ✅ Logged in")
        token_data = r.json()
        token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
    else:
        print(f"   ❌ Failed: {r.status_code} - {r.text}")
        return

    # 4. Create Shop
    print(f"\n4. Creating Shop '{SHOP_NAME}'...")
    shop_payload = {
        "name": SHOP_NAME,
        "slug": SLUG,
        "description": "Deployment Verification Shop",
        "owner_id": user_data.get("id"), # Might need to fetch me first if ID not in register response
        "logo_url": "https://via.placeholder.com/150"
    }
    # Get user ID if not in register response
    if "id" not in user_data:
        me_r = s.get(f"{BASE_URL}/users/me", headers=headers)
        shop_payload["owner_id"] = me_r.json()["id"]

    r = s.post(f"{BASE_URL}/shops/", json=shop_payload, headers=headers)
    if r.status_code == 200 or r.status_code == 201:
        print("   ✅ Shop Created")
        shop_data = r.json()
        print(f"   Shop ID: {shop_data['id']}")
        print(f"   Dashboard URL: http://{SLUG}.192.168.2.88.nip.io/dashboard")
    else:
        print(f"   ❌ Failed: {r.status_code} - {r.text}")
        return

    print("\n✅ Backend Verification Complete!")

if __name__ == "__main__":
    run_test()
