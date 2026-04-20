import asyncio
import sys
import os
import json

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent_logic import ToolCallingAgent
from db_interface import db_interface

async def test_agent():
    print("--- Testing Llama 3.2 Tool Calling Agent ---")
    
    # Initialize Agent
    agent = ToolCallingAgent()
    session_id = "test_session_v2"
    
    # Test 1: Search Request (Should trigger search_shops)
    print("\nQUERY: Find me a barber shop in Toronto")
    response = await agent.chat(session_id, "Find me a barber shop in Toronto")
    
    print(f"AGENT RESPONSE: {response['response']}")
    print("ACTIONS:", json.dumps(response['actions'], indent=2))
    
    # Test 2: History Check
    print("\n--- Verifying History Persistence ---")
    history = db_interface.get_conversation_history(session_id)
    print(f"History Length: {len(history)} messages")
    for msg in history:
        print(f"[{msg['role'].upper()}] {msg['content'][:50]}...")

if __name__ == "__main__":
    asyncio.run(test_agent())
