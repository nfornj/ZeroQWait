import asyncio
from agent_logic import query_processor

async def test():
    queries = ["auto", "shops near me", "tire services", "auto repair"]
    for q in queries:
        res = await query_processor.extract_search_terms(q)
        print(f"Query: '{q}' -> {res.to_dict()}")

if __name__ == "__main__":
    asyncio.run(test())
