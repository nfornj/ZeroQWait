import asyncio
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent_logic import IntentExtractor
from db_interface import db_interface

async def test_extraction():
    extractor = IntentExtractor()
    
    test_queries = [
        "hair cut shops",
        "find me a mechanic in Toronto",
        "where can I get my nails done?",
        "looking for pricing details",
        "what can ZeroQwait do?"
    ]
    
    print("--- Testing Intent Extraction ---")
    for q in test_queries:
        intent = await extractor.extract(q)
        print(f"Query: {q}")
        print(f"Result: {intent}")
        print("-" * 20)

async def test_db_search():
    print("\n--- Testing Database Search Logic ---")
    # Simulate extraction result for "hair cut shops"
    intent = {"query": "hair cut", "shop_type": "barber", "city": None}
    
    shops = db_interface.search_shops(
        query=intent["query"],
        shop_type=intent["shop_type"]
    )
    
    print(f"Search Results for {intent}:")
    for s in shops:
        print(f"- {s['name']} ({s['shop_type']})")

if __name__ == "__main__":
    asyncio.run(test_extraction())
    asyncio.run(test_db_search())
