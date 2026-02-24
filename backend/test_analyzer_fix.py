import asyncio
from pydantic_ai import Agent
import json
import re
from agent_logic import QueryAnalysis, ContextUpdates, model

# Simplified analyzer
analyzer_agent = Agent(
    model,
    system_prompt="""You are a single-pass query analyzer for a local business search assistant.
Extract the user's intent, search terms, and update context in ONE pass reading the conversation history.

Rules for 'intent':
- CONVERSATION: Greetings, thanks, acknowledgments, meta questions, testing.
- ACTION: Search requests, business types, services, locations.
- UNCLEAR: Ambiguous inputs.

Rules for 'terms':
- Extract the core business type or service (e.g. 'barber', 'oil change').
- Do NOT hardcode categories. Dynamically extract the noun/service exactly as asked (e.g., 'alien pet groomer').
- Strip generic plural suffixes (shops, stores).
- If intent is CONVERSATION or UNCLEAR, terms should be "".

Rules for 'city':
- Explicitly extract any city name mentioned in the current query (e.g., 'Toronto', 'Austin').
- If no new city is mentioned, leave it empty or null.

Rules for 'near_me':
- true ONLY if user explicitly says "near me", "nearby", "around here".

Rules for 'context_updates.last_category' and 'context_updates.last_city':
- The LATEST business/category or city mentioned. Keep old if user only changed one.

CRITICAL INSTRUCTION: You MUST output ONLY valid JSON matching this schema exactly:
{
  "intent": "ACTION" | "CONVERSATION" | "UNCLEAR",
  "terms": "string",
  "city": "string" | null,
  "near_me": boolean,
  "context_updates": {
    "last_category": "string" | null,
    "last_city": "string" | null
  }
}
DO NOT output any markdown blocks, comments, or extra text. JUST JSON.
""",
    model_settings={'temperature': 0.1, 'max_tokens': 200}
)

async def test():
    res = await analyzer_agent.run("can you list shops near me in New York?")
    text = str(res.data)
    print("Raw Output:", text)
    
    # Try to parse
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            print("Parsed:", parsed)
            qa = QueryAnalysis(
                intent=parsed.get('intent', 'UNCLEAR'),
                terms=parsed.get('terms', ''),
                city=parsed.get('city'),
                near_me=parsed.get('near_me', False),
                context_updates=ContextUpdates(
                    last_category=parsed.get('context_updates', {}).get('last_category'),
                    last_city=parsed.get('context_updates', {}).get('last_city')
                )
            )
            print("Pydantic:", qa)
        except Exception as e:
            print("Failed to parse", e)
            
asyncio.run(test())
