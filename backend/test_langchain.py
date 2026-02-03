import asyncio
import logging
import sys
from agent_logic import MasterAgent

# Setup basic logging to see tool usage
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_agent():
    print("Initializing MasterAgent...")
    agent = MasterAgent()
    
    print("\n--- Test 1: Greeting ---")
    response = await agent.chat(
        session_id="test_script_1",
        user_msg="Hello, I'm verifying your new brain.",
        latitude=43.65,
        longitude=-79.38
    )
    print(f"Response: {response['response']}")
    print(f"Actions: {response['actions']}")

    print("\n--- Test 2: Tool Call (Search) ---")
    response = await agent.chat(
        session_id="test_script_1",
        user_msg="Find me a barber shop nearby.",
        latitude=43.65,
        longitude=-79.38,
        context={"active_view": "home"}
    )
    print(f"Response: {response['response']}")
    print(f"Actions: {response['actions']}")
    
    # Verify Search Action Exists
    has_search = any(a['tool'] == 'search_shops' for a in response['actions'])
    if has_search:
        print("✅ SUCCESS: Search tool was called.")
    else:
        print("❌ FAILURE: Search tool was NOT called.")

if __name__ == "__main__":
    asyncio.run(test_agent())
