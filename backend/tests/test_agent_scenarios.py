import requests
import json
import time

BASE_URL = "http://localhost:8000/api/agent"

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
YELLOW = "\033[93m"

TEST_SCENARIOS = [
    # --- Category 1: Direct Category Search ---
    {"msg": "Find me a barber", "context": {"active_view": "home"}, "expected_tool": "search_shops", "desc": "Simple Barber Search"},
    {"msg": "I look for a hair salon", "context": {"active_view": "home"}, "expected_tool": "search_shops", "desc": "Simple Salon Search"},
    {"msg": "Is there an auto repair shop?", "context": {"active_view": "home"}, "expected_tool": "search_shops", "desc": "Auto Repair Search"},
    {"msg": "nail spas nearby", "context": {"active_view": "home"}, "expected_tool": "search_shops", "desc": "Nail Spa Search"},
    
    # --- Category 2: Location Based ---
    {"msg": "Barbers in San Francisco", "context": {"active_view": "home"}, "expected_tool": "search_shops", "desc": "Location Search (SF)"},
    {"msg": "Shops in Detroit", "context": {"active_view": "home"}, "expected_tool": "search_shops", "desc": "Location Search (Detroit)"},
    
    # --- Category 3: Broad / Generic (The User's specific concern) ---
    {"msg": "list of shops", "context": {"active_view": "home"}, "expected_tool": "search_shops", "desc": "Generic 'List shops'"},
    {"msg": "what shops do you have?", "context": {"active_view": "home"}, "expected_tool": "search_shops", "desc": "Generic 'What shops?'"},
    {"msg": "show me stores", "context": {"active_view": "home"}, "expected_tool": "search_shops", "desc": "Generic 'Show stores'"},
    
    # --- Category 4: Context Switching (Proving the Fix) ---
    {"msg": "find me a barber", "context": {"active_view": "pricing"}, "expected_tool": "search_shops", "desc": "Context Switch: Pricing -> Barber"},
    {"msg": "list shops", "context": {"active_view": "features"}, "expected_tool": "search_shops", "desc": "Context Switch: Features -> Shops"},
    {"msg": "do you have mechanic?", "context": {"active_view": "faq"}, "expected_tool": "search_shops", "desc": "Context Switch: FAQ -> Mechanic"},
    
    # --- Category 5: Pricing Context (Should NOT search shops) ---
    {"msg": "how much does it cost?", "context": {"active_view": "pricing"}, "expected_tool": "check_pricing", "desc": "Pricing Question (in Pricing View)"},
    {"msg": "subscription plans", "context": {"active_view": "home"}, "expected_tool": "check_pricing", "desc": "Pricing Question (General)"},
    
    # --- Category 6: Specific Shop Names ---
    {"msg": "Is Downtown Barbershop open?", "context": {"active_view": "home"}, "expected_tool": "search_shops", "desc": "Specific Shop Name Search"},
    
    # --- Category 7: Conversational / Edge Cases ---
    {"msg": "hello", "context": {"active_view": "home"}, "expected_tool": None, "desc": "Greeting (No Tool)"},
    {"msg": "who are you?", "context": {"active_view": "home"}, "expected_tool": None, "desc": "Identity (No Tool)"},
]

def run_tests():
    print(f"Starting {len(TEST_SCENARIOS)} Test Scenarios...\n")
    passed = 0
    failed = 0
    
    for i, test in enumerate(TEST_SCENARIOS):
        print(f"--- Test {i+1}: {test['desc']} ---")
        print(f"Input: '{test['msg']}' [Context: {test['context']['active_view']}]")
        
        payload = {
            "message": test['msg'],
            "context": test['context'],
            "session_id": f"test_session_{i}"
        }
        
        try:
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/master/chat", json=payload)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                actions = result.get('actions', [])
                
                # Analyze Actions
                tools_used = [a.get('tool') for a in actions]
                
                # Check expectation
                expected = test['expected_tool']
                success = False
                
                if expected is None:
                    # Expect NO tool
                    if not tools_used:
                        success = True
                    else:
                        print(f"{RED}FAIL: Expected no tool, but got {tools_used}{RESET}")
                else:
                    # Expect specific tool
                    if expected in tools_used:
                        success = True
                    else:
                        print(f"{RED}FAIL: Expected '{expected}', but got {tools_used}{RESET}")
                        if "navigate_to_page_section" in tools_used and expected == "search_shops":
                             print(f"{YELLOW}Analysis: Agent likely got confused and navigated instead of searching.{RESET}")

                if success:
                    print(f"{GREEN}PASS{RESET} (Time: {duration:.2f}s)")
                    passed += 1
                else:
                    print(f"Agent Response: {response_text[:100]}...")
                    failed += 1
            else:
                print(f"{RED}ERROR: HTTP {response.status_code}{RESET}")
                failed += 1
                
        except Exception as e:
            print(f"{RED}EXCEPTION: {e}{RESET}")
            failed += 1
        print("")
        
    print(f"\nResults: {passed} PASSED, {failed} FAILED")
    print(f"Total Success Rate: {(passed/len(TEST_SCENARIOS))*100:.1f}%")

if __name__ == "__main__":
    run_tests()
