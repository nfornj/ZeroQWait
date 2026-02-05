import asyncio
import httpx
import json
import random

# Configuration
BASE_URL = "http://localhost:8000/api/agent/master/chat"
SESSION_ID = "stress-test-suite-50"

# Manual Test Cases
TEST_CASES = [
    # --- Block 1: Basic Category Switching ---
    {"input": "find me a barber", "expected_cat": "barber", "desc": "Simple Category"},
    {"input": "actually a salon", "expected_cat": "salon", "desc": "Correction"},
    {"input": "how about a dentist", "expected_cat": "dentist", "desc": "Switch"},
    {"input": "mechanic", "expected_cat": "mechanic", "desc": "Short keyword"},
    {"input": "vet clinic", "expected_cat": "vet", "desc": "Multi-word"},
    
    # --- Block 2: Location Persistence ---
    {"input": "find auto repair", "expected_cat": "auto repair", "expected_city": None, "desc": "Start Context"},
    {"input": "in Toronto", "expected_cat": "auto repair", "expected_city": "Toronto", "desc": "Add City"},
    {"input": "actually Vancouver", "expected_cat": "auto repair", "expected_city": "Vancouver", "desc": "Change City"},
    
    # --- Block 3: Switch Category, Keep City ---
    # "what about gyms" -> Should imply "gyms in Vancouver"
    {"input": "what about gyms", "expected_cat": "gym", "expected_city": "Vancouver", "desc": "Switch Cat, Persist City (Vancouver)"},
    
    # --- Block 4: Specific Services ---
    {"input": "tire rotation", "expected_cat": "tire rotation", "expected_city": "Vancouver", "desc": "Service (Context City)"},
    {"input": "oil change", "expected_cat": "oil change", "expected_city": "Vancouver", "desc": "Service (Context City)"},
    
    # --- Block 5: Reset / New Context ---
    {"input": "new search for plumbers in chicago", "expected_cat": "plumber", "expected_city": "chicago", "desc": "Full Reset"},
    
    # --- Block 6: Conversational Interruptions ---
    {"input": "hello", "expected_intent": "CONVERSATION", "desc": "Chat"},
    {"input": "are you real", "expected_intent": "CONVERSATION", "desc": "Chat"},
    {"input": "plumbers again", "expected_cat": "plumber", "expected_city": "chicago", "desc": "Resume Context"},

    # --- Block 7: Edge Cases ---
    {"input": "auto", "expected_cat": "auto", "desc": "Generic Short"},
    {"input": "fix my car", "expected_cat": "auto", "desc": "Semantic"}, 
    {"input": "nails", "expected_cat": "nail", "desc": "Short"},
]

# --- Block 8: Mass Category Check ---
categories = [
    "massage", "spa", "chiropractor", "physio", "doctor", "lawyer", 
    "accountant", "bakery", "coffee", "tea", "burger", "pizza", 
    "sushi", "tacos", "bar", "club", "pub", "hotel", "motel", "hostel"
]
for c in categories:
    TEST_CASES.append({"input": f"find {c}", "expected_cat": c, "desc": f"Category: {c}"})

async def run_test():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"Starting Stress Test with {len(TEST_CASES)} cases...")
        
        passed = 0
        failed = 0
        
        for i, case in enumerate(TEST_CASES):
            print(f"\n[{i+1}/{len(TEST_CASES)}] {case['desc']}: '{case['input']}'")
            
            try:
                response = await client.post(
                    BASE_URL,
                    json={"session_id": SESSION_ID, "message": case['input']}
                )
                data = response.json()
                
                # Analyze Result
                actions = data.get("actions", [])
                response_text = data.get("response", "")
                
                # Check Intent
                if case.get("expected_intent") == "CONVERSATION":
                    if not actions:
                        print(f"  ✅ PASS (Conversation)")
                        passed += 1
                    else:
                        print(f"  ❌ FAIL: Expected Conversation, got Actions: {json.dumps(actions, indent=2)}")
                        failed += 1
                    continue
                
                # Check Action
                if not actions:
                     # Check if clarification
                     if "?" in response_text or "city" in response_text or "location" in response_text:
                         print(f"  ⚠️  Clarification asked: {response_text}")
                         if case.get("expected_city") is None: 
                             # If we expect no city, and it asks for city, that's fine/good?
                             pass
                         else:
                             print(f"  ❌ FAIL: No action triggered. Agent asked question: {response_text}")
                             failed += 1
                             continue
                     else:
                        print(f"  ❌ FAIL: No action actions triggered. Response: {response_text[:50]}...")
                        failed += 1
                        continue
                
                # Extract params from first action (search_shops)
                if actions:
                    params = actions[0].get("params", {})
                    cat = params.get("category")
                    city = params.get("city")
                    
                    failed_check = False
                    
                    # Check Category
                    exp_cat = case.get("expected_cat")
                    if exp_cat:
                        if cat and (exp_cat.lower() in cat.lower() or cat.lower() in exp_cat.lower()):
                             print(f"  ✅ Category Match: '{cat}'")
                        else:
                             print(f"  ❌ Category Mismatch: Got '{cat}', Expected '{exp_cat}'")
                             failed_check = True

                    # Check City
                    if "expected_city" in case: # Only check if specified
                        exp_city = case.get("expected_city")
                        if exp_city is None:
                            if city is None: 
                                print("  ✅ City Match: None")
                            else: 
                                print(f"  ❌ City Mismatch: Got '{city}', Expected None")
                                failed_check = True
                        else:
                            if city and exp_city.lower() in city.lower():
                                print(f"  ✅ City Match: '{city}'")
                            else:
                                print(f"  ❌ City Mismatch: Got '{city}', Expected '{exp_city}'")
                                failed_check = True
                    
                    if failed_check:
                        failed += 1
                    else:
                        passed += 1
                        print("  ✅ PASS")
            
            except Exception as e:
                print(f"  ❌ Error: {e}")
                failed += 1
            
            # small delay
            await asyncio.sleep(0.5)
            
        print(f"\n{'='*20}")
        print(f"Final Results: {passed} PASSED, {failed} FAILED")
        print(f"{'='*20}")

if __name__ == "__main__":
    asyncio.run(run_test())
