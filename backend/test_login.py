"""
Test script for login and authentication functionality.
"""
import requests
import json
from auth_utils import get_password_hash
from supabase_client import supabase

BASE_URL = "http://localhost:8000/api"

def setup_test_user():
    """Create a test user if it doesn't exist."""
    print("=" * 60)
    print("Setting up test user...")
    print("=" * 60)
    
    test_username = "testuser"
    test_email = "test@example.com"
    test_password = "testpassword123"
    
    try:
        # Check if user already exists
        response = supabase.table("users").select("*").eq("username", test_username).execute()
        
        if response.data:
            print(f"✓ Test user '{test_username}' already exists")
            return test_username, test_password
        
        # Create new test user
        user_data = {
            "username": test_username,
            "email": test_email,
            "hashed_password": get_password_hash(test_password),
            "is_active": True,
            "role": "customer"
        }
        
        result = supabase.table("users").insert(user_data).execute()
        
        if result.data:
            print(f"✓ Created test user: {test_username}")
            print(f"  Email: {test_email}")
            print(f"  Password: {test_password}")
            return test_username, test_password
        else:
            print("✗ Failed to create test user")
            return None, None
            
    except Exception as e:
        print(f"✗ Error setting up test user: {e}")
        return None, None

def test_login_success(username, password):
    """Test successful login."""
    print("\n" + "=" * 60)
    print("Test 1: Successful Login")
    print("=" * 60)
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/token",
            data={
                "username": username,
                "password": password,
                "grant_type": "password"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Login successful")
            print(f"  Access Token: {data['access_token'][:50]}...")
            print(f"  Token Type: {data['token_type']}")
            return data['access_token']
        else:
            print(f"✗ Login failed")
            print(f"  Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"✗ Error during login: {e}")
        return None

def test_login_wrong_password(username):
    """Test login with wrong password."""
    print("\n" + "=" * 60)
    print("Test 2: Login with Wrong Password")
    print("=" * 60)
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/token",
            data={
                "username": username,
                "password": "wrongpassword",
                "grant_type": "password"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print("✓ Correctly rejected wrong password")
            print(f"  Response: {response.json()}")
        else:
            print(f"✗ Unexpected status code: {response.status_code}")
            print(f"  Response: {response.text}")
            
    except Exception as e:
        print(f"✗ Error during test: {e}")

def test_login_nonexistent_user():
    """Test login with non-existent user."""
    print("\n" + "=" * 60)
    print("Test 3: Login with Non-existent User")
    print("=" * 60)
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/token",
            data={
                "username": "nonexistentuser12345",
                "password": "password",
                "grant_type": "password"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print("✓ Correctly rejected non-existent user")
            print(f"  Response: {response.json()}")
        else:
            print(f"✗ Unexpected status code: {response.status_code}")
            print(f"  Response: {response.text}")
            
    except Exception as e:
        print(f"✗ Error during test: {e}")

def test_protected_endpoint(token):
    """Test accessing a protected endpoint with token."""
    print("\n" + "=" * 60)
    print("Test 4: Access Protected Endpoint")
    print("=" * 60)
    
    if not token:
        print("✗ No token available, skipping test")
        return
    
    try:
        # Try to access user profile (protected endpoint)
        response = requests.get(
            f"{BASE_URL}/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Successfully accessed protected endpoint")
            print(f"  User: {data.get('username')}")
            print(f"  Email: {data.get('email')}")
            print(f"  Role: {data.get('role')}")
        else:
            print(f"✗ Failed to access protected endpoint")
            print(f"  Response: {response.text}")
            
    except Exception as e:
        print(f"✗ Error during test: {e}")

def test_invalid_token():
    """Test accessing protected endpoint with invalid token."""
    print("\n" + "=" * 60)
    print("Test 5: Access Protected Endpoint with Invalid Token")
    print("=" * 60)
    
    try:
        response = requests.get(
            f"{BASE_URL}/users/me",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print("✓ Correctly rejected invalid token")
            print(f"  Response: {response.json()}")
        else:
            print(f"✗ Unexpected status code: {response.status_code}")
            print(f"  Response: {response.text}")
            
    except Exception as e:
        print(f"✗ Error during test: {e}")

def cleanup_test_user(username):
    """Clean up test user after tests."""
    print("\n" + "=" * 60)
    print("Cleanup (Optional)")
    print("=" * 60)
    print(f"Test user '{username}' has been left in database for manual inspection.")
    print("To remove it manually, run:")
    print(f"  supabase.table('users').delete().eq('username', '{username}').execute()")

def main():
    print("\n" + "=" * 60)
    print("LOGIN & AUTHENTICATION TESTS")
    print("=" * 60)
    print("\nMake sure the backend server is running on http://localhost:8000")
    print("Run: pdm run start")
    
    input("\nPress Enter to continue...")
    
    # Setup
    username, password = setup_test_user()
    if not username:
        print("\n✗ Failed to setup test user. Exiting.")
        return
    
    # Test 1: Successful login
    token = test_login_success(username, password)
    
    # Test 2: Wrong password
    test_login_wrong_password(username)
    
    # Test 3: Non-existent user
    test_login_nonexistent_user()
    
    # Test 4: Protected endpoint with valid token
    test_protected_endpoint(token)
    
    # Test 5: Protected endpoint with invalid token
    test_invalid_token()
    
    # Cleanup info
    cleanup_test_user(username)
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
