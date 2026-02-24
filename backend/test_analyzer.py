import asyncio
from agent_logic import unified_query_analyzer

async def main():
    res = await unified_query_analyzer.analyze("can you list shops near me in New York?")
    print(res)

import sys
import logging
logging.basicConfig(level=logging.INFO)
asyncio.run(main())
