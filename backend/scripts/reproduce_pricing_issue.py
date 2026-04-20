
import asyncio
import sys
import os

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent_logic import MasterAgent

# Mock DB Interface to avoid actual DB calls if needed, 
# but MasterAgent uses db_interface directly. 
# We'll assume the environment is set up correctly as verified in previous steps.


async def test_pricing_context_override():
    print("--- Starting Reproduction Test: Pricing Context Override ---")
    
    agent = MasterAgent()
    ui_context = {"view": "Pricing", "details": "User is viewing the pricing page."}
    
    scenarios = [
        ("show me some shops", "search_shops"),
        ("find cheap barbers", "search_shops"),
        ("what is the cost of subscription", "check_pricing"), # This SHOULD be pricing
        ("how much for a haircut", "search_shops") # Ambiguous, but user likely wants a shop service price, so search_shops is better than app pricing
    ]
    
    for query, expected_tool in scenarios:
        print(f"\nScanning Query: '{query}' with Context: Pricing")
        response = await agent.chat(
            session_id=f"test_repro_{query.replace(' ', '_')}",
            user_msg=query,
            history=[], 
            context=ui_context,
            latitude=43.65,
            longitude=-79.38
        )
        actions = response.get('actions', [])
        tool_names = [a.get('tool') for a in actions]
        print(f"Tools Called: {tool_names}")
        
        if expected_tool in tool_names:
            print(f"✅ SUCCESS for '{query}'")
        else:
            print(f"❌ FAILURE for '{query}'. Expected {expected_tool}, got {tool_names}")

if __name__ == "__main__":
    asyncio.run(test_pricing_context_override())

if __name__ == "__main__":
    asyncio.run(test_pricing_context_override())
