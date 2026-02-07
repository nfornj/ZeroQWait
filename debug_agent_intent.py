import requests
import json
import uuid
import sys

# Use local endpoint which should be working via tunnel
URL = "http://localhost:8000/api/agent/master/chat"

payload = {
    "message": "find shops near me",
    "history": [],
    "session_id": str(uuid.uuid4()),
    "is_voice": False
}

try:
    print(f"Sending request to {URL}...")
    r = requests.post(URL, json=payload, timeout=30)
    print(f"Status Code: {r.status_code}")
    try:
        data = r.json()
        print("Response JSON:")
        print(json.dumps(data, indent=2))
    except:
        print("Response Text:")
        print(r.text)

except Exception as e:
    print(f"Request failed: {e}")
