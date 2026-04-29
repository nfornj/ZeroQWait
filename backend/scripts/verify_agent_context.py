import requests
import json
import sys

BASE_URL = "http://localhost:8000/api/agent/chat/1"
HEADERS = {"Content-Type": "application/json"}

def run_test():
    print("--- Starting Context Memory Test ---")
    
    # Simulating a new session
    history = []
    
    # Turn 1: Introduce user
    msg1 = "My name is John Doe and I want to book a haircut."
    print(f"\nUser: {msg1}")
    
    payload1 = {
        "message": msg1,
        "history": history,
        "session_id": "test_session_123"
    }
    
    try:
        r1 = requests.post(BASE_URL, json=payload1)
        r1.raise_for_status()
        resp1 = r1.json()
        agent_reply1 = resp1["response"]
        print(f"Agent: {agent_reply1}")
        
        # Update history
        history.append({"role": "user", "text": msg1})
        history.append({"role": "ai", "text": agent_reply1})
        
    except Exception as e:
        print(f"Error in Turn 1: {e}")
        if 'r1' in locals():
            print(f"Response: {r1.text}")
        return False

    # Turn 2: Ask question relying on context
    msg2 = "What is my name?"
    print(f"\nUser: {msg2}")
    
    payload2 = {
        "message": msg2,
        "history": history,
        "session_id": "test_session_123"
    }
    
    try:
        r2 = requests.post(BASE_URL, json=payload2)
        r2.raise_for_status()
        resp2 = r2.json()
        agent_reply2 = resp2["response"]
        print(f"Agent: {agent_reply2}")
        
        if "John" in agent_reply2 or "Doe" in agent_reply2:
            print("\n[SUCCESS] Agent remembered the name!")
            return True
        else:
            print("\n[FAILURE] Agent forgot the name.")
            return False
            
    except Exception as e:
        print(f"Error in Turn 2: {e}")
        return False

if __name__ == "__main__":
    success = run_test()
    if not success:
        sys.exit(1)
