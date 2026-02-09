import requests
import sys

def test_login(username, password):
    url = "http://localhost:8000/api/auth/token"
    data = {
        "username": username,
        "password": password
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print(f"✅ Login successful for {username}")
            print(f"Token: {response.json().get('access_token')[:20]}...")
            return True
        else:
            print(f"❌ Login failed for {username}: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error during login: {e}")
        return False

if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 else "admin"
    pw = sys.argv[2] if len(sys.argv) > 2 else "Password123!"
    test_login(user, pw)
