#!/usr/bin/env python3
"""
Comprehensive test script to verify:
1. Supabase connection
2. Email functionality
3. All API endpoints
4. Create sample data for testing
"""
import sys
import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Configuration
API_BASE_URL = "http://localhost:8000/api"
TEST_USERS = [
    {
        "email": "shop_owner1@test.com",
        "username": "shop_owner1",
        "password": "TestPassword123!",
        "role": "shop_owner"
    },
    {
        "email": "shop_owner2@test.com",
        "username": "shop_owner2",
        "password": "TestPassword123!",
        "role": "shop_owner"
    },
    {
        "email": "customer1@test.com",
        "username": "customer1",
        "password": "TestPassword123!",
        "role": "customer"
    },
    {
        "email": "customer2@test.com",
        "username": "customer2",
        "password": "TestPassword123!",
        "role": "customer"
    },
    {
        "email": "employee1@test.com",
        "username": "employee1",
        "password": "TestPassword123!",
        "role": "employee"
    }
]

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_header(text):
    print(f"\n{'='*70}")
    print(f"{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{'='*70}")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_info(text):
    print(f"{Colors.YELLOW}ℹ {text}{Colors.RESET}")

def test_supabase_connection():
    """Test Supabase connection"""
    print_header("1. Testing Supabase Connection")
    
    try:
        from supabase_client import supabase
        
        # Check if client is initialized
        print_success(f"Supabase client initialized: {supabase.supabase_url}")
        
        # Test database access
        response = supabase.table("users").select("*").limit(1).execute()
        print_success("Database connection successful")
        
        # Check tables
        tables = ["users", "shops", "queues", "queue_items", "password_reset_tokens"]
        for table in tables:
            try:
                supabase.table(table).select("*").limit(0).execute()
                print_success(f"Table '{table}' exists")
            except Exception as e:
                print_error(f"Table '{table}' not found: {e}")
        
        return True
    except Exception as e:
        print_error(f"Supabase connection failed: {e}")
        return False

def test_email_configuration():
    """Test email configuration"""
    print_header("2. Testing Email Configuration")
    
    try:
        import smtplib
        
        EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
        EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
        EMAIL_USER = os.getenv("EMAIL_USER")
        EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
        
        print_info(f"Email Host: {EMAIL_HOST}")
        print_info(f"Email Port: {EMAIL_PORT}")
        print_info(f"Email User: {EMAIL_USER}")
        
        if not EMAIL_PASSWORD:
            print_error("EMAIL_PASSWORD not set in .env file")
            return False
        
        # Test SMTP connection
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.quit()
        
        print_success("SMTP connection successful")
        print_success("Email credentials are valid")
        return True
        
    except Exception as e:
        print_error(f"Email configuration test failed: {e}")
        print_info("Emails will be logged to console instead of being sent")
        return False

def test_api_health():
    """Test if API is running"""
    print_header("3. Testing API Health")
    
    try:
        response = requests.get("http://localhost:8000/")
        if response.status_code == 200:
            print_success(f"API is running: {response.json()}")
            return True
        else:
            print_error(f"API returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("Cannot connect to API. Is the server running?")
        print_info("Run: docker-compose up -d")
        return False
    except Exception as e:
        print_error(f"API health check failed: {e}")
        return False

def create_sample_users():
    """Create sample users"""
    print_header("4. Creating Sample Users")
    
    created_users = []
    
    for user_data in TEST_USERS:
        try:
            response = requests.post(
                f"{API_BASE_URL}/users",
                json=user_data
            )
            
            if response.status_code == 200:
                user = response.json()
                created_users.append({
                    "id": user["id"],
                    "username": user_data["username"],
                    "password": user_data["password"],
                    "email": user_data["email"],
                    "role": user_data["role"]
                })
                print_success(f"Created user: {user_data['username']} ({user_data['role']})")
            elif response.status_code == 400 and "already" in response.text.lower():
                print_info(f"User already exists: {user_data['username']}")
                # Still add to list for login testing
                created_users.append({
                    "username": user_data["username"],
                    "password": user_data["password"],
                    "email": user_data["email"],
                    "role": user_data["role"]
                })
            else:
                print_error(f"Failed to create {user_data['username']}: {response.text}")
        except Exception as e:
            print_error(f"Error creating {user_data['username']}: {e}")
    
    return created_users

def test_user_login(username, password):
    """Test user login"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/token",
            data={"username": username, "password": password}
        )
        
        if response.status_code == 200:
            token = response.json()["access_token"]
            print_success(f"Login successful: {username}")
            return token
        else:
            print_error(f"Login failed for {username}: {response.text}")
            return None
    except Exception as e:
        print_error(f"Login error for {username}: {e}")
        return None

def test_auth_endpoints(users):
    """Test authentication endpoints"""
    print_header("5. Testing Authentication Endpoints")
    
    tokens = {}
    
    # Test login for all users
    for user in users:
        token = test_user_login(user["username"], user["password"])
        if token:
            tokens[user["username"]] = token
    
    # Test /users/me endpoint
    print_info("\nTesting /users/me endpoint...")
    for username, token in tokens.items():
        try:
            response = requests.get(
                f"{API_BASE_URL}/users/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                print_success(f"Got user info for: {username}")
            else:
                print_error(f"Failed to get user info for {username}")
        except Exception as e:
            print_error(f"Error getting user info for {username}: {e}")
    
    return tokens

def test_password_reset(email):
    """Test password reset functionality"""
    print_header("6. Testing Password Reset (Email Functionality)")
    
    print_info(f"Testing password reset for: {email}")
    
    try:
        # Request password reset
        response = requests.post(
            f"{API_BASE_URL}/auth/forgot-password",
            params={"email": email}
        )
        
        if response.status_code == 200:
            print_success("Password reset request successful")
            print_info("Check console logs for reset link (if email is not configured)")
            print_info("Check email inbox (if email is configured)")
            return True
        else:
            print_error(f"Password reset failed: {response.text}")
            return False
    except Exception as e:
        print_error(f"Password reset error: {e}")
        return False

def create_sample_shops(tokens):
    """Create sample shops"""
    print_header("7. Creating Sample Shops")
    
    shop_owners = [u for u in TEST_USERS if u["role"] == "shop_owner"]
    created_shops = []
    
    sample_shops = [
        {
            "name": "Premium Cuts Barbershop",
            "description": "Classic barbershop with modern styling",
            "shop_type": "barbershop",
            "address": "123 Main Street",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94102",
            "country": "United States",
            "phone": "+1-555-0101",
            "email": "info@premiumcuts.com",
            "website": "https://premiumcuts.com",
            "average_service_time": 30,
            "primary_color": "#2c3e50",
            "slug": "premium-cuts"
        },
        {
            "name": "Quick Clinic",
            "description": "Fast and efficient medical services",
            "shop_type": "clinic",
            "address": "456 Health Ave",
            "city": "Los Angeles",
            "state": "CA",
            "zip_code": "90001",
            "country": "United States",
            "phone": "+1-555-0202",
            "email": "contact@quickclinic.com",
            "website": "https://quickclinic.com",
            "average_service_time": 20,
            "primary_color": "#27ae60",
            "slug": "quick-clinic"
        }
    ]
    
    for i, shop_data in enumerate(sample_shops):
        if i < len(shop_owners):
            owner = shop_owners[i]
            token = tokens.get(owner["username"])
            
            if not token:
                print_error(f"No token for {owner['username']}, skipping shop creation")
                continue
            
            try:
                response = requests.post(
                    f"{API_BASE_URL}/shops",
                    json=shop_data,
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code == 200:
                    shop = response.json()
                    created_shops.append(shop)
                    print_success(f"Created shop: {shop_data['name']} (Owner: {owner['username']})")
                elif response.status_code == 400 and "already exists" in response.text.lower():
                    print_info(f"Shop already exists: {shop_data['name']}")
                else:
                    print_error(f"Failed to create shop: {response.text}")
            except Exception as e:
                print_error(f"Error creating shop: {e}")
    
    return created_shops

def create_sample_queue_items(shops, tokens):
    """Create sample queue items"""
    print_header("8. Creating Sample Queue Items")
    
    if not shops:
        print_info("No shops available, skipping queue item creation")
        return
    
    customers = [u for u in TEST_USERS if u["role"] == "customer"]
    
    sample_queue_items = [
        {
            "customer_name": "John Doe",
            "customer_phone": "+1-555-1001",
            "customer_email": "john.doe@example.com",
            "notes": "Haircut and beard trim"
        },
        {
            "customer_name": "Jane Smith",
            "customer_phone": "+1-555-1002",
            "customer_email": "jane.smith@example.com",
            "notes": "Quick checkup"
        },
        {
            "customer_name": "Mike Johnson",
            "customer_phone": "+1-555-1003",
            "customer_email": "mike.j@example.com",
            "notes": "Regular cut"
        }
    ]
    
    # Add queue items to first shop
    shop = shops[0]
    shop_id = shop["id"]
    
    for item_data in sample_queue_items:
        try:
            response = requests.post(
                f"{API_BASE_URL}/queues/{shop_id}/join",
                json=item_data
            )
            
            if response.status_code == 200:
                item = response.json()
                print_success(f"Added to queue: {item_data['customer_name']} (Position: {item.get('position', 'N/A')})")
            else:
                print_error(f"Failed to add queue item: {response.text}")
        except Exception as e:
            print_error(f"Error adding queue item: {e}")

def test_shops_endpoints(tokens):
    """Test shops endpoints"""
    print_header("9. Testing Shops Endpoints")
    
    # Test get all shops
    try:
        response = requests.get(f"{API_BASE_URL}/shops")
        if response.status_code == 200:
            shops = response.json()
            print_success(f"Retrieved {len(shops)} shops")
        else:
            print_error(f"Failed to get shops: {response.text}")
    except Exception as e:
        print_error(f"Error getting shops: {e}")

def test_queues_endpoints(shops):
    """Test queue endpoints"""
    print_header("10. Testing Queue Endpoints")
    
    if not shops:
        print_info("No shops available, skipping queue tests")
        return
    
    shop_id = shops[0]["id"]
    
    try:
        # Get queue for shop
        response = requests.get(f"{API_BASE_URL}/queues/{shop_id}")
        if response.status_code == 200:
            queue = response.json()
            print_success(f"Retrieved queue for shop {shop_id}")
            if queue.get("queue_items"):
                print_info(f"Queue has {len(queue['queue_items'])} items")
        else:
            print_error(f"Failed to get queue: {response.text}")
    except Exception as e:
        print_error(f"Error getting queue: {e}")

def print_summary(users, tokens):
    """Print summary of created test data"""
    print_header("TEST DATA SUMMARY")
    
    print(f"\n{Colors.BLUE}Created User Accounts:{Colors.RESET}")
    print(f"\n{'Username':<20} {'Email':<30} {'Password':<20} {'Role':<15}")
    print("-" * 85)
    
    for user in users:
        username = user.get('username', 'N/A')
        email = user.get('email', 'N/A')
        password = user.get('password', 'N/A')
        role = user.get('role', 'N/A')
        
        status = "✓" if username in tokens else "✗"
        print(f"{status} {username:<18} {email:<30} {password:<20} {role:<15}")
    
    print(f"\n{Colors.GREEN}Login Status:{Colors.RESET}")
    print(f"Successfully logged in: {len(tokens)}/{len(users)} users")
    
    print(f"\n{Colors.YELLOW}Quick Login Instructions:{Colors.RESET}")
    print(f"1. Go to: http://localhost:3000")
    print(f"2. Use any of the credentials above")
    print(f"3. Example: username='shop_owner1', password='TestPassword123!'")
    
    print(f"\n{Colors.BLUE}API Documentation:{Colors.RESET}")
    print(f"Swagger UI: http://localhost:8000/docs")
    print(f"ReDoc: http://localhost:8000/redoc")

def main():
    """Main test function"""
    print(f"\n{Colors.BLUE}{'='*70}")
    print("COMPREHENSIVE API & EMAIL TEST")
    print(f"{'='*70}{Colors.RESET}\n")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Test Supabase
    if not test_supabase_connection():
        print_error("\nSupabase connection failed. Please check configuration.")
        return False
    
    # Step 2: Test Email (optional - can fail)
    email_working = test_email_configuration()
    
    # Step 3: Test API health
    if not test_api_health():
        print_error("\nAPI is not running. Please start it first:")
        print_info("docker-compose up -d")
        return False
    
    # Step 4-5: Create users and test login
    users = create_sample_users()
    if not users:
        print_error("\nFailed to create any users")
        return False
    
    tokens = test_auth_endpoints(users)
    
    # Step 6: Test password reset / email
    if users:
        test_password_reset(users[0]["email"])
    
    # Step 7: Create shops
    shops = create_sample_shops(tokens)
    
    # Step 8: Create queue items
    create_sample_queue_items(shops, tokens)
    
    # Step 9-10: Test other endpoints
    test_shops_endpoints(tokens)
    test_queues_endpoints(shops)
    
    # Print summary
    print_summary(users, tokens)
    
    # Final status
    print_header("TEST SUMMARY")
    print_success("Supabase: Connected")
    print_success("Email: Configured" if email_working else "Email: Not configured (emails logged to console)")
    print_success(f"API: Running")
    print_success(f"Users: {len(users)} created")
    print_success(f"Logins: {len(tokens)} successful")
    print_success(f"Shops: {len(shops)} created")
    
    print(f"\n{Colors.GREEN}✅ All tests completed!{Colors.RESET}\n")
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Test interrupted by user{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
