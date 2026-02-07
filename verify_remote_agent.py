import requests
import json
import uuid
import sys

URL = "http://192.168.2.88.nip.io/api/agent/master/chat"

payload = {
    "message": "find shops near me",
    "history": [],
    "session_id": str(uuid.uuid4()),
    "is_voice": False,
    # Simulate location for direct results
    "latitude": 40.7128, 
    "longitude": -74.0060
}

try:
    print(f"Sending request to {URL}...")
    r = requests.post(URL, json=payload, timeout=20)
    print(f"Status Code: {r.status_code}")
    try:
        data = r.json()
        print("Response JSON:")
        print(json.dumps(data, indent=2))
        
        if "error" in data:
            print("\n❌ Error found in response!")
            sys.exit(1)
        
        response_text = data.get("response", "")
        if "trouble" in response_text or "catch that" in response_text:
             print("\n❌ Failed: Still getting fallback error message.")
             sys.exit(1)
             
        print("\n✅ Success: Agent responded correctly.")
        
    except Exception as e:
        print("Response Text:")
        print(r.text)
        print(f"JSON Decode Error: {e}")

except Exception as e:
    print(f"Request failed: {e}")
