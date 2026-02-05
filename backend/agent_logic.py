import os
import json
import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from db_interface import db_interface
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

logger = logging.getLogger(__name__)

# --- Configuration ---
ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
model = OpenAIModel(
    'llama3.2',
    provider=OpenAIProvider(base_url=ollama_url, api_key='ollama'),
)

# --- Smart Query Processor ---

from dataclasses import dataclass
from typing import Optional
import json as json_lib

@dataclass
class ParsedQuery:
    """Structured query result with location intent preserved."""
    terms: str  # Extracted search terms
    near_me: bool  # User wants proximity search
    city: Optional[str]  # Explicit city mentioned
    
    def to_dict(self) -> dict:
        return {"terms": self.terms, "near_me": self.near_me, "city": self.city}



# --- Context Extractor ---

@dataclass
class SearchContext:
    """Structured search context extracted from history."""
    last_category: Optional[str]
    last_city: Optional[str]

class ContextExtractor:
    """LLM-based context extractor ensuring scalability."""
    
    def __init__(self):
        self.agent = Agent(
            model,
            system_prompt="""Analyze conversation history to find the ACTIVE search context.
            
Return a JSON object with:
- "last_category": The most recent business category/service (e.g. "auto repair", "nail salon"). Null if none.
- "last_city": The most recent city/location (e.g. "Toronto"). PERSIST the last known city unless the user explicitly mentions a NEW city or says "near me".

Prioritize the LATEST intent. If user changed topic (e.g. from "auto" to "nail") but didn't mention city, KEEP the old city.

Examples:
History: User: "find auto" -> ZeroQ: "no results" -> User: "nail salon"
Output: {"last_category": "nail salon", "last_city": null}

History: User: "auto repair" -> ZeroQ: "no results" -> User: "toronto"
Output: {"last_category": "auto repair", "last_city": "Toronto"}

Return ONLY valid JSON. NO markdown.
""",
            model_settings={'temperature': 0.1, 'max_tokens': 100}
        )
        
    async def extract(self, history: List[Dict]) -> SearchContext:
        if not history:
            return SearchContext(None, None)
            
        # Format (last 6 messages)
        recent = history[-6:]
        history_str = json_lib.dumps([{"role": m["role"], "content": m["content"]} for m in recent])
        
        try:
            result = await self.agent.run(history_str)
            raw = result.output.strip() if hasattr(result, 'output') else str(result).strip()
            
            # Sanitize response (remove markdown)
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()
            
            parsed = json_lib.loads(raw)
            return SearchContext(
                last_category=parsed.get("last_category"),
                last_city=parsed.get("last_city")
            )
        except Exception as e:
            # Safe fallback
            logger.error(f"Context extraction failed: {e}")
            return SearchContext(None, None)

# Initialize global instance
context_extractor = ContextExtractor()


class QueryProcessor:
    """
    Intelligent query processing using pure LLM extraction.
    Returns structured JSON with location intent preserved.
    """
    
    def __init__(self):
        # Lightweight LLM agent for query extraction
        self.extraction_agent = Agent(
            model,
            system_prompt="""You are a search query parser. Extract structured info from user input.

Return a JSON object with exactly these fields:
- "terms": business type or service keywords (string)
- "near_me": ONLY set to true if user EXPLICITLY says "near me", "nearby", "around here", "close by". Default is false!
- "city": city name if user mentions one, otherwise null (string or null)

**CRITICAL: near_me should be FALSE unless the exact words "near me" or "nearby" appear in the input!**

Examples:
Input: "find me barber shops near me"
Output: {"terms": "barber", "near_me": true, "city": null}

Input: "tire rotation near me"
Output: {"terms": "tire rotation", "near_me": true, "city": null}

Input: "oil change"
Output: {"terms": "oil change", "near_me": false, "city": null}

Input: "restaurants in Toronto"
Output: {"terms": "restaurant", "near_me": false, "city": "Toronto"}

Input: "auto repair shops around here"
Output: {"terms": "auto repair", "near_me": true, "city": null}

Input: "salons in vancouver"
Output: {"terms": "salon", "near_me": false, "city": "vancouver"}

Input: "shops near me"
Output: {"terms": "", "near_me": true, "city": null}

Input: "auto"
Output: {"terms": "auto", "near_me": false, "city": null}

Input: "find massage"
Output: {"terms": "massage", "near_me": false, "city": null}

Input: "nails"
Output: {"terms": "nails", "near_me": false, "city": null}

Input: "canada"
Output: {"terms": "", "near_me": false, "city": "canada"}

Input: "wheel alignment"
Output: {"terms": "wheel alignment", "near_me": false, "city": null}

Input: "brakes"
Output: {"terms": "brakes", "near_me": false, "city": null}

Return ONLY valid JSON, no other text.
""",
            model_settings={'temperature': 0.1, 'max_tokens': 100}
        )
        
        # Cache for common queries (performance optimization)
        self._extraction_cache: Dict[str, ParsedQuery] = {}
        self._cache_max_size = 1000
    
    async def extract_search_terms(self, user_query: str) -> ParsedQuery:
        """
        Extract structured query info from user input.
        
        Args:
            user_query: Raw user input
            
        Returns:
            ParsedQuery with terms, near_me flag, and city
        """
        
        if not user_query or not user_query.strip():
            return ParsedQuery(terms="", near_me=False, city=None)
        
        # Normalize
        normalized = user_query.lower().strip()
        
        # Check cache first (performance)
        cache_key = hashlib.md5(normalized.encode()).hexdigest()
        if cache_key in self._extraction_cache:
            logger.debug(f"Cache hit for query: {normalized}")
            return self._extraction_cache[cache_key]
        
        try:
            # Use LLM to extract structured query
            result = await self.extraction_agent.run(normalized)
            raw_output = result.output.strip() if hasattr(result, 'output') else str(result).strip()
            
            # Parse JSON response
            try:
                parsed = json_lib.loads(raw_output)
                query_result = ParsedQuery(
                    terms=parsed.get("terms", "").strip(),
                    near_me=parsed.get("near_me", False),
                    city=parsed.get("city")
                )
            except json_lib.JSONDecodeError:
                # Fallback: treat entire output as terms
                logger.warning(f"Failed to parse JSON from: {raw_output}")
                query_result = ParsedQuery(
                    terms=raw_output,
                    near_me="near" in normalized or "nearby" in normalized,
                    city=None
                )
            
            # Cache the result
            if len(self._extraction_cache) < self._cache_max_size:
                self._extraction_cache[cache_key] = query_result
            
            logger.debug(f"Query extracted: '{normalized}' -> {query_result.to_dict()}")
            
            return query_result
        
        except Exception as e:
            logger.error(f"Query extraction failed: {e}", exc_info=True)
            # Return basic fallback
            return ParsedQuery(
                terms=normalized,
                near_me="near" in normalized,
                city=None
            )

# --- Global Query Processor ---
query_processor = QueryProcessor()


# --- LLM-based Intent Router ---

class IntentRouter:
    """
    LLM-based intent classification.
    NO hardcoded patterns - pure LLM decision making.
    Routes to: CONVERSATION (no tools) or ACTION (needs tools)
    """
    
    def __init__(self):
        self.router_agent = Agent(
            model,
            system_prompt="""You are an intent classifier for a local business search assistant.

Classify user messages into ONE of these categories:

**CONVERSATION** - ONLY for these:
- Greetings: "hello", "hi", "hey", "good morning"
- Thanks: "thanks", "thank you", "thx"
- Acknowledgments: "okay", "cool", "got it", "nice"
- Meta questions: "what is zeroqwait", "who are you", "how does this work"

**ACTION** - For EVERYTHING else, including:
- Business types: "barber", "salon", "restaurant", "auto shop"
- Services: "tire rotation", "oil change", "haircut", "brakes", "wheel alignment"
- Search requests: "find me...", "show me...", "looking for..."
- Locations: "near me", "in toronto", "canada" (when following a search)
- Short nouns that could be search terms
- Pricing/features/help requests

Examples:
- "hello" → CONVERSATION
- "thanks" → CONVERSATION
- "what is zeroqwait" → CONVERSATION
- "tire rotation" → ACTION
- "oil change" → ACTION
- "barber" → ACTION
- "find me auto shops" → ACTION
- "near me" → ACTION
- "canada" → ACTION (could be location refinement)
- "brakes" → ACTION
- "wheel alignment" → ACTION

**CRITICAL RULE: If unsure, default to ACTION.**
Short noun phrases (1-3 words) that aren't greetings are almost always search terms.

Respond with ONLY one word: CONVERSATION or ACTION
""",
            model_settings={'temperature': 0.1, 'max_tokens': 10}
        )
        
        # Conversational agent (no tools)
        self.conversation_agent = Agent(
            model,
            system_prompt="""You are ZeroQ, the friendly AI assistant for ZeroQwait - a queue management platform.

You help customers discover local businesses and join queues remotely.

**About ZeroQwait:**
- Helps customers find local businesses
- Allows remote queue joining
- Real-time wait time estimates
- SMS notifications when it's your turn

**Pricing Plans:**
- Free: Basic queue management, up to 50 customers/month
- Premium ($29/mo): Unlimited customers, analytics, SMS
- Enterprise: Custom solutions

**Your capabilities:**
1. Help find local shops (barbers, salons, restaurants, etc.)
2. Explain pricing plans
3. Describe platform features
4. Answer questions

**Response style:**
- Be warm, friendly, and concise (2-3 sentences max)
- Use 1-2 emojis sparingly
- For greetings, offer to help with shops, pricing, or questions
- Don't be robotic, be human-like

Respond naturally to the user's message.
""",
            model_settings={'temperature': 0.7}
        )
    
    async def classify_intent(self, user_msg: str, history_context: str = "") -> str:
        """Classify user intent using pure LLM, considering conversation history."""
        try:
            # Include history context for follow-up detection
            if history_context:
                full_prompt = f"{history_context}\n\nCurrent message: {user_msg}"
            else:
                full_prompt = user_msg
            
            result = await self.router_agent.run(full_prompt)
            intent = result.output.strip().upper() if hasattr(result, 'output') else str(result).strip().upper()
            
            # Normalize response - DEFAULT TO ACTION if unclear
            if 'CONVERSATION' in intent:
                return 'CONVERSATION'
            else:
                # Default to ACTION for anything unclear or explicitly ACTION
                if 'ACTION' not in intent:
                    logger.debug(f"Unclear intent response: {intent}, defaulting to ACTION")
                return 'ACTION'
        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            return 'ACTION'  # Default to action - let the agent try to help
    
    async def get_conversational_response(self, user_msg: str, context: Dict[str, Any] = None, history_context: str = "") -> str:
        """Get a conversational response without tools, context-aware."""
        try:
            # Add any relevant context
            context_parts = []
            
            if history_context:
                context_parts.append(history_context)
            
            if context:
                if context.get('active_view'):
                    context_parts.append(f"User is viewing: {context['active_view']} page.")
                if context.get('city'):
                    context_parts.append(f"User is in: {context['city']}.")
                if context.get('last_search_category'):
                    context_parts.append(f"Last search was for: {context['last_search_category']}.")
            
            context_str = "\n".join(context_parts)
            full_msg = f"{context_str}\n\nUser: {user_msg}" if context_str else user_msg
            
            result = await self.conversation_agent.run(full_msg)
            return result.output if hasattr(result, 'output') else str(result)
        except Exception as e:
            logger.error(f"Conversation error: {e}")
            return "Hello! 👋 I'm ZeroQ. How can I help you today? I can help you find shops, check pricing, or answer questions!"


# --- Global Intent Router ---
intent_router = IntentRouter()



# --- Category Manager ---

class CategoryManager:
    """
    Dynamic category system with smart query processing.
    Zero hardcoded categories - pure database-driven.
    """
    
    def __init__(self):
        self._category_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 300  # 5 minutes
        self._synonym_map = {}
        self._learning_queue = []
    
    def _load_categories_from_db(self) -> Dict[str, Dict[str, Any]]:
        """Load categories dynamically from database."""
        try:
            shops = db_interface.get_all_shops()
            
            category_stats = {}
            for shop in shops:
                shop_type = shop.get('shop_type') or shop.get('category')
                if not shop_type:
                    continue
                
                shop_type = shop_type.lower().strip()
                
                if shop_type not in category_stats:
                    category_stats[shop_type] = {
                        "key": shop_type,
                        "display_name": shop.get('category_display_name', shop_type.replace('_', ' ').title()),
                        "aliases": set([shop_type]),
                        "count": 0,
                        "keywords": set(),
                        "example_shops": []
                    }
                
                category_stats[shop_type]["count"] += 1
                
                if len(category_stats[shop_type]["example_shops"]) < 3:
                    category_stats[shop_type]["example_shops"].append(shop.get('name', ''))
                
                if shop.get('name'):
                    name_words = [w.lower() for w in shop['name'].split() if len(w) > 3]
                    category_stats[shop_type]["keywords"].update(name_words[:5])
                
                if shop.get('description'):
                    desc_words = [w.lower() for w in shop['description'].split() if len(w) > 3]
                    category_stats[shop_type]["keywords"].update(desc_words[:5])
            
            # Load explicit aliases from database
            try:
                db_aliases = db_interface.get_category_aliases()
                for alias_row in db_aliases:
                    cat_key = alias_row['category_key']
                    alias = alias_row['alias']
                    
                    if cat_key in category_stats:
                        category_stats[cat_key]["aliases"].add(alias)
            except Exception as e:
                logger.warning(f"Could not load category aliases: {e}")
            
            # Load learned synonyms
            try:
                learned = db_interface.get_learned_synonyms()
                for syn_row in learned:
                    query_term = syn_row['query_term']
                    category = syn_row['category']
                    
                    if category in category_stats:
                        category_stats[category]["aliases"].add(query_term)
                        self._synonym_map[query_term] = category
            except Exception as e:
                logger.warning(f"Could not load learned synonyms: {e}")
            
            return category_stats
        
        except Exception as e:
            logger.error(f"Error loading categories from DB: {e}", exc_info=True)
            return {}
    
    def get_categories(self, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """Get categories with caching."""
        now = datetime.now().timestamp()
        
        if (not force_refresh and 
            self._category_cache is not None and 
            self._cache_timestamp is not None and 
            (now - self._cache_timestamp) < self._cache_ttl):
            return self._category_cache
        
        logger.info("Refreshing category cache from database")
        self._category_cache = self._load_categories_from_db()
        self._cache_timestamp = now
        
        return self._category_cache
    
    async def detect_category(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Detect category from user input using smart extraction.
        """
        # First, extract meaningful search terms
        extracted_terms = await query_processor.extract_search_terms(user_input)
        
        if not extracted_terms:
            # No meaningful terms, check context
            if context and context.get("preferred_category"):
                return context["preferred_category"]
            return None
        
        # Now search for category matches in extracted terms
        normalized = extracted_terms.lower()
        categories = self.get_categories()
        
        # Direct match in extracted terms
        for cat_key, cat_data in categories.items():
            aliases = cat_data["aliases"]
            for alias in aliases:
                if alias in normalized:
                    self._learn_from_query(user_input, cat_key)
                    return cat_key
        
        # Check learned synonyms
        if normalized in self._synonym_map:
            return self._synonym_map[normalized]
        
        # Fuzzy match on extracted terms
        best_match = None
        best_score = 0
        
        for cat_key, cat_data in categories.items():
            for alias in cat_data["aliases"]:
                similarity = self._fuzzy_match(normalized, alias)
                if similarity > best_score and similarity > 0.75:
                    best_score = similarity
                    best_match = cat_key
        
        if best_match:
            self._learn_from_query(user_input, best_match)
            return best_match
        
        # Context fallback
        if context and context.get("preferred_category"):
            return context["preferred_category"]
        
        return None
    
    def _fuzzy_match(self, s1: str, s2: str) -> float:
        """Simple fuzzy matching for typo tolerance."""
        if not s1 or not s2:
            return 0.0
        
        set1 = set(s1.lower())
        set2 = set(s2.lower())
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def _learn_from_query(self, query: str, category: str):
        """Learn from successful queries."""
        normalized = query.lower().strip()
        
        # Don't learn very short terms
        if len(normalized) < 3:
            return
        
        # Extract words
        words = normalized.split()
        
        for word in words:
            if len(word) >= 3 and word not in self._synonym_map:
                self._synonym_map[word] = category
                logger.info(f"Learned: '{word}' → {category}")
                
                self._learning_queue.append({
                    "query_term": word,
                    "category": category,
                    "full_query": query,
                    "timestamp": datetime.now().isoformat()
                })
    
    async def persist_learnings(self):
        """Persist learned patterns to database."""
        if not self._learning_queue:
            return
        
        try:
            for learning in self._learning_queue:
                db_interface.add_learned_synonym(
                    query_term=learning["query_term"],
                    category=learning["category"],
                    full_query=learning.get("full_query"),
                    timestamp=learning["timestamp"]
                )
            
            logger.info(f"Persisted {len(self._learning_queue)} learned patterns")
            self._learning_queue.clear()
        
        except Exception as e:
            logger.error(f"Error persisting learnings: {e}", exc_info=True)
    
    def get_available_categories_text(self) -> str:
        """Get human-readable list of categories."""
        categories = self.get_categories()
        
        if not categories:
            return "No categories available currently"
        
        sorted_cats = sorted(
            categories.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
        
        cat_list = []
        for cat_key, cat_data in sorted_cats:
            if cat_data["count"] > 0:
                examples = ", ".join(cat_data["example_shops"][:2]) if cat_data["example_shops"] else ""
                cat_str = f"{cat_data['display_name']} ({cat_data['count']} shops"
                if examples:
                    cat_str += f", e.g., {examples}"
                cat_str += ")"
                cat_list.append(cat_str)
        
        return ", ".join(cat_list[:10])
    
    def get_category_details_for_llm(self) -> str:
        """Get detailed category information for LLM."""
        categories = self.get_categories()
        
        if not categories:
            return "Categories will be loaded from database"
        
        details = []
        for cat_key, cat_data in categories.items():
            aliases = list(cat_data["aliases"])[:5]
            detail = f"- {cat_data['display_name']} (key: '{cat_key}')"
            if aliases:
                detail += f" - also: {', '.join(aliases)}"
            details.append(detail)
        
        return "\n".join(details[:15])
    
    def add_category(self, category_key: str, display_name: str, aliases: List[str] = None):
        """Admin function to add categories."""
        try:
            db_interface.add_category(
                category_key=category_key,
                display_name=display_name,
                aliases=aliases or []
            )
            
            self.get_categories(force_refresh=True)
            logger.info(f"Added new category: {category_key}")
        
        except Exception as e:
            logger.error(f"Error adding category: {e}", exc_info=True)


# --- Global Category Manager ---
category_manager = CategoryManager()


# --- Data Models ---

@dataclass
class MasterAgentDeps:
    session_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    context: Optional[Dict[str, Any]] = None
    actions: List[Dict[str, Any]] = field(default_factory=list)
    user_id: Optional[str] = None
    is_voice: bool = False
    request_timestamp: float = field(default_factory=lambda: datetime.now().timestamp())


class MasterResponse(BaseModel):
    response: str = Field(description="The friendly response to show the user.")


# --- Dynamic System Prompt ---

def get_master_system_prompt() -> str:
    """Generate system prompt dynamically with current categories."""
    available_categories = category_manager.get_available_categories_text()
    category_details = category_manager.get_category_details_for_llm()
    
    return f"""You are ZeroQ, the friendly AI Assistant for ZeroQwait - a queue management platform that helps customers find local businesses and join queues.

## CRITICAL: RESPONSE PRIORITY

**FIRST, determine the user's intent:**

1. **GREETING/SOCIAL** → Respond conversationally, NO tools
   - "hello", "hi", "hey", "good morning", "what's up"
   - "thanks", "thank you", "cool", "okay", "nice"
   - "how are you", "who are you", "what can you do"
   
2. **ABOUT ZEROQWAIT** → Answer from your knowledge, NO tools
   - "what is zeroqwait", "how does this work", "tell me about yourself"
   - Questions about the platform's purpose
   
3. **SHOP/BUSINESS SEARCH** → Use search_shops tool
   - Mentions specific business types: "barber", "salon", "restaurant"
   - "find me a...", "looking for...", "show me shops"
   - "near me" + business type
   
4. **PRICING INQUIRY** → Use check_pricing tool
   - "price", "pricing", "cost", "how much", "plans", "subscription"
   
5. **FEATURES INFO** → Use see_features tool
   - "features", "what can zeroqwait do", "capabilities"
   
6. **HELP/FAQ** → Use see_faq tool
   - "help", "support", "faq", "how do I..."

## ABOUT ZEROQWAIT (answer from this knowledge)

ZeroQwait is a queue management platform that:
- Helps customers discover local businesses
- Allows customers to join queues remotely
- Provides real-time wait time estimates
- Sends SMS notifications when it's your turn
- Helps shop owners manage their queues efficiently

**Plans:**
- Free: Basic queue management, up to 50 customers/month
- Premium ($29/mo): Unlimited customers, analytics, SMS notifications
- Enterprise: Custom solutions for large businesses

## AVAILABLE SHOP CATEGORIES
{available_categories}

## CONVERSATIONAL RESPONSES (NO TOOLS)

For greetings and casual conversation, respond naturally:

- "hello" → "Hello! 👋 I'm ZeroQ, your assistant for ZeroQwait. I can help you find local businesses, check our pricing, or answer questions. What would you like to do?"

- "hi" → "Hi there! How can I help you today? Looking for a shop, or have questions about ZeroQwait?"

- "thanks" / "thank you" → "You're welcome! Is there anything else I can help with?"

- "who are you" → "I'm ZeroQ, the AI assistant for ZeroQwait! I help customers find local businesses like barbers, salons, and restaurants, and I can answer questions about our platform."

- "what can you do" → "I can help you: 1) Find local shops (barbers, salons, etc.) 2) Check our pricing plans 3) Learn about ZeroQwait features 4) Answer your questions. What interests you?"

- "how are you" → "I'm doing great, thanks for asking! Ready to help you find what you need. 😊"

## WHEN TO USE search_shops

**ALWAYS call search_shops for:**
- Business types: barber, salon, restaurant, auto shop, vet, clinic, etc.
- Services: tire rotation, oil change, haircut, brakes, wheel alignment, inspection, tune-up
- Anything that looks like a search term (short noun phrases 1-3 words)
- Follow-ups with location refinement ("canada", "toronto", "near me")

**Examples that REQUIRE search_shops:**
- "find me a barber" → search_shops(category="barber")
- "tire rotation" → search_shops(query="tire rotation")  
- "oil change" → search_shops(query="oil change")
- "brakes" → search_shops(query="brakes")
- "canada" (after a search) → search_shops(category=prev_category, city="canada")
- "restaurants in Toronto" → search_shops(category="restaurant", city="Toronto")

**ONLY these DON'T need tools (respond directly):**
- "hello", "hi" → Greet warmly
- "thanks", "thank you" → You're welcome!
- "what is zeroqwait", "who are you" → Explain platform
- "okay", "cool", "got it" → Acknowledgment

**CRITICAL: When in doubt, call search_shops.** It's better to search and find nothing than to ask clarifying questions.

## RESPONSE STYLE

- Be warm and friendly, like a helpful concierge
- Keep responses concise (2-3 sentences max)
- Use emojis sparingly for friendliness
- For voice users, be extra brief (1-2 sentences)
- Don't over-explain or be robotic

## CONTEXT AWARENESS

You may receive context like:
- [USER LOCATION: city, coordinates]
- [USER IS VIEWING: page name]
- [INPUT METHOD: voice/text]
- [LAST SEARCH: category='barber', city='toronto']
- [NEAR_ME: true/false] - whether user wants proximity-based search
- [CONVERSATION HISTORY] with recent messages

Use this to personalize responses when relevant.

## FOLLOW-UP HANDLING

When you see [LAST SEARCH: ...], the user may be refining:
- "canada" after "auto repair" → search_shops(category="auto repair", city="canada")
- "in toronto" after "barber" → search_shops(category="barber", city="toronto")
- "tire rotation" → NEW search with query="tire rotation"

**ONE CLARIFICATION RULE:** Only ask for location if:
1. User said "near me" AND we have no lat/long AND no city
2. Ask exactly ONE question: "What city are you in?"
3. Otherwise, just call search_shops immediately
"""


# --- Create Agent ---

def create_master_agent():
    """Create agent with current system prompt."""
    return Agent(
        model,
        deps_type=MasterAgentDeps,
        system_prompt=get_master_system_prompt(),
        retries=2,
        model_settings={'temperature': 0.3}
    )


master_pydantic_agent = create_master_agent()


# --- Tools ---

@master_pydantic_agent.tool
async def search_shops(
    ctx: RunContext[MasterAgentDeps], 
    category: Optional[str] = Field(
        default=None, 
        description="Shop category (e.g., 'barber', 'salon', 'restaurant', 'auto repair'). Can also be a service like 'tire rotation'."
    ),
    city: Optional[str] = Field(
        default=None, 
        description="City name if user mentioned one. Leave empty to use location."
    ),
    query: Optional[str] = Field(
        default=None, 
        description="User's search query - will be automatically parsed for terms, location intent, and city."
    )
) -> str:
    """
    Search for local businesses or services.
    ALWAYS call this for any business/service-related query.
    If category is unknown, just pass the query and we'll search across all categories.
    """
    
    try:
        # Smart query extraction returns structured ParsedQuery
        parsed_query = None
        clean_terms = None
        user_wants_nearby = False
        extracted_city = city  # Start with explicit city
        
        if query:
            parsed_query = await query_processor.extract_search_terms(query)
            clean_terms = parsed_query.terms if parsed_query.terms else None
            user_wants_nearby = parsed_query.near_me
            # Use extracted city if none provided
            if not extracted_city and parsed_query.city:
                extracted_city = parsed_query.city
            logger.debug(f"Query processing: '{query}' → {parsed_query.to_dict()}")
        
        # ONE CLARIFICATION GATE: Only ask if near_me=true but no location info
        has_location = (
            ctx.deps.latitude is not None or 
            extracted_city or 
            (ctx.deps.context and ctx.deps.context.get('city'))
        )
        
        if user_wants_nearby and not has_location:
            # Store the pending search for when user provides location
            ctx.deps.context["pending_search_category"] = category or clean_terms
            return "Ask the user exactly once: 'What city or area are you in?' Then call search_shops with their response."
        
        # If we have city from context, use it
        if not extracted_city and ctx.deps.context:
            extracted_city = ctx.deps.context.get('city') or ctx.deps.context.get('last_search_city')
        
        # Execute search - ALWAYS try even with minimal info
        result = db_interface.search_shops(
            query=clean_terms,
            shop_type=category,
            city=extracted_city,
            latitude=ctx.deps.latitude,
            longitude=ctx.deps.longitude,
            limit=10
        )
        
        # Store results and action
        ctx.deps.actions.append({
            "tool": "search_shops",
            "result": result,
            "params": {
                "category": category,
                "city": extracted_city,
                "original_query": query,
                "cleaned_terms": clean_terms,
                "near_me": user_wants_nearby
            },
            "timestamp": datetime.now().isoformat()
        })
        
        # Learn from successful searches
        if category and result and len(result) > 0:
            original_query = ctx.deps.context.get("original_user_message", "")
            if original_query:
                category_manager._learn_from_query(original_query, category)
        
        # Log
        logger.info(
            f"Search | user={ctx.deps.user_id} | category={category} | "
            f"terms='{clean_terms}' | city={extracted_city} | results={len(result)} | "
            f"voice={ctx.deps.is_voice}"
        )
        
        # Guidance for LLM
        if len(result) == 0:
            return (
                f"No shops found for '{category or clean_terms}'. "
                "Briefly say 'No results found' and suggest trying a different category or area."
            )
        elif len(result) == 1:
            return (
                f"Found 1 shop: {result[0].get('name', 'shop')}. "
                f"Say 'I found one option!' Keep it brief."
            )
        else:
            return (
                f"Found {len(result)} shops. They're visible as cards in UI. "
                f"Say 'Found {len(result)} options near you!' Keep it brief."
            )
    
    except Exception as e:
        logger.error(f"search_shops error: {e}", exc_info=True)
        return "Search encountered a technical error. Tell user to try again."


@master_pydantic_agent.tool
async def check_pricing(ctx: RunContext[MasterAgentDeps]) -> str:
    """Show pricing page with subscription plans."""
    ctx.deps.actions.append({
        "tool": "navigate_to_page_section",
        "result": {"target": "pricing"},
        "timestamp": datetime.now().isoformat()
    })
    
    logger.info(f"Pricing viewed | user={ctx.deps.user_id} | voice={ctx.deps.is_voice}")
    
    return (
        "Pricing page now visible. Plans: Free ($0/mo), Premium ($29/mo), Enterprise (custom). "
        "Provide brief friendly summary. Voice users: keep it to 1 sentence."
    )


@master_pydantic_agent.tool
async def see_features(ctx: RunContext[MasterAgentDeps]) -> str:
    """Show features page."""
    ctx.deps.actions.append({
        "tool": "navigate_to_page_section",
        "result": {"target": "features"},
        "timestamp": datetime.now().isoformat()
    })
    
    logger.info(f"Features viewed | user={ctx.deps.user_id} | voice={ctx.deps.is_voice}")
    
    return (
        "Features page visible. Highlight: Queue management, Real-time updates, "
        "SMS notifications, Analytics, Multi-location support. Keep brief."
    )


@master_pydantic_agent.tool
async def see_faq(ctx: RunContext[MasterAgentDeps]) -> str:
    """Show FAQ section."""
    ctx.deps.actions.append({
        "tool": "navigate_to_page_section",
        "result": {"target": "faq"},
        "timestamp": datetime.now().isoformat()
    })
    
    logger.info(f"FAQ viewed | user={ctx.deps.user_id} | voice={ctx.deps.is_voice}")
    
    return "FAQ section visible. Tell user they can find answers there."


# --- Master Agent ---

class MasterAgent:
    """
    Production-grade master agent.
    - Pure LLM-driven (no hardcoded patterns)
    - Smart query extraction
    - Dynamic categories
    - Full context awareness
    """
    
    def __init__(self):
        self.agent = master_pydantic_agent
        self.category_manager = category_manager
        self.query_processor = query_processor
        
        self.metrics = {
            "total_requests": 0,
            "llm_calls": 0,
            "tool_calls": 0,
            "errors": 0,
            "search_calls": 0,
            "query_extractions": 0,
            "cache_hits": 0,
            "voice_requests": 0,
            "text_requests": 0
        }
    
    def _format_history_for_llm(self, history: List[Dict]) -> str:
        """Format conversation history as context for LLM."""
        if not history:
            return ""
        
        # Take last 6 messages (3 exchanges)
        recent = history[-6:]
        formatted = []
        for msg in recent:
            role = "User" if msg.get('role') == 'user' else "ZeroQ"
            content = msg.get('content', '')[:200]  # Limit length
            formatted.append(f"{role}: {content}")
        
        return "[CONVERSATION HISTORY]\n" + "\n".join(formatted)
    
    def _extract_last_search_context(self, history: List[Dict]) -> Dict[str, str]:
        """Extract last search context (category, city) from conversation history."""
        context = {"last_category": None, "last_city": None}
        
        if not history:
            return context
        
    async def _extract_last_search_context(self, history: List[Dict]) -> Dict[str, str]:
        """Extract last search context (category, city) using LLM."""
        
        # Use scalable, LLM-based extraction
        search_ctx = await context_extractor.extract(history)
        
        return {
            "last_category": search_ctx.last_category,
            "last_city": search_ctx.last_city
        }
    
    async def chat(
        self,
        session_id: str,
        user_msg: str,
        latitude: float = None,
        longitude: float = None,
        history: List[Dict[str, str]] = None,
        context: Dict[str, Any] = None,
        user_id: Optional[str] = None,
        is_voice: bool = False
    ) -> Dict[str, Any]:
        """Process user message with pure LLM intelligence."""
        
        self.metrics["total_requests"] += 1
        if is_voice:
            self.metrics["voice_requests"] += 1
        else:
            self.metrics["text_requests"] += 1
        
        start_time = datetime.now().timestamp()
        
        try:
            # Build context
            actions = []
            deps = MasterAgentDeps(
                session_id=session_id,
                latitude=latitude,
                longitude=longitude,
                context=context or {},
                actions=actions,
                user_id=user_id,
                is_voice=is_voice,
                request_timestamp=start_time
            )
            
            # Store original message for learning
            deps.context["original_user_message"] = user_msg
            
            # Load conversation history from database for context
            conversation_history = db_interface.get_conversation_history(session_id, limit=10)
            history_context = self._format_history_for_llm(conversation_history)
            search_context = await self._extract_last_search_context(conversation_history)
            
            # Store search context for follow-up queries
            if search_context["last_category"]:
                deps.context["last_search_category"] = search_context["last_category"]
            if search_context["last_city"]:
                deps.context["last_search_city"] = search_context["last_city"]
            
            # Build context parts
            context_parts = []
            
            if context and context.get("active_view"):
                context_parts.append(f"[USER IS VIEWING: {context['active_view']} page]")
            
            if latitude and longitude:
                city_name = context.get("city", "unknown location") if context else "unknown location"
                context_parts.append(f"[USER LOCATION: {city_name} ({latitude}, {longitude})]")
            elif context and context.get("city"):
                context_parts.append(f"[USER CITY: {context['city']}]")
            
            if context and context.get("last_action"):
                context_parts.append(f"[PREVIOUS ACTION: {context['last_action']}]")
                
                if context.get("last_search_category"):
                    context_parts.append(f"[LAST SEARCH CATEGORY: {context['last_search_category']}]")
            
            if context and context.get("preferred_category"):
                context_parts.append(f"[USER PREFERENCE: category={context['preferred_category']}]")
            
            input_method = "voice" if is_voice else "text"
            context_parts.append(f"[INPUT METHOD: {input_method}]")
            
            # Add conversation history context
            if history_context:
                context_parts.append(history_context)
            
            # Add last search context for follow-ups
            if search_context["last_category"]:
                context_parts.append(f"[LAST SEARCH: category='{search_context['last_category']}'")
                if search_context["last_city"]:
                    context_parts[-1] = context_parts[-1] + f", city='{search_context['last_city']}']"
                else:
                    context_parts[-1] = context_parts[-1] + "]"
            
            # LLM processing
            self.metrics["llm_calls"] += 1
            
            full_context = "\n".join(context_parts)
            full_msg = f"{full_context}\n\nUser message: {user_msg}" if full_context else user_msg
            
            logger.info(
                f"LLM Request | user={user_id} | voice={is_voice} | "
                f"msg='{user_msg[:50]}...' | context_items={len(context_parts)}"
            )
            
            # Step 1: Classify intent using LLM (with conversation history)
            intent = await intent_router.classify_intent(user_msg, history_context)
            logger.info(f"Intent classified as: {intent}")
            
            # Step 2: Route based on intent
            if intent == 'CONVERSATION':
                # Use conversational agent (no tools)
                final_text = await intent_router.get_conversational_response(user_msg, deps.context, history_context)
                logger.info(f"Conversational response generated (no tools)")
            else:
                # ACTION intent - be aggressive about calling search_shops
                # First, parse the query to understand what user wants
                parsed_query = await query_processor.extract_search_terms(user_msg)
                logger.info(f"Parsed query: {parsed_query.to_dict()}")
                
                # Determine if we should directly call search_shops
                has_search_terms = bool(parsed_query.terms)
                has_city_only = bool(parsed_query.city) and not parsed_query.terms
                has_near_me_only = parsed_query.near_me and not parsed_query.terms
                
                # Case 1: Query has search terms (tire rotation, barber, auto, etc.) -> call search
                # Case 2: Query is just a city (follow-up) -> use previous category + city
                # Case 3: Query is just "near me" / "shops near me" -> search all
                
                if has_search_terms or has_city_only or has_near_me_only:
                    # DETERMINISTIC: Call search_shops directly
                    logger.info(f"Direct search_shops call for: terms='{parsed_query.terms}', city='{parsed_query.city}', near_me={parsed_query.near_me}")
                    
                    # Use previous category if this is a location-only follow-up
                    search_category = None
                    if has_city_only and search_context.get("last_category"):
                        search_category = search_context["last_category"]
                    elif parsed_query.terms:
                        search_category = parsed_query.terms  # Use terms as category
                    
                    # Determine city
                    search_city = parsed_query.city or search_context.get("last_city")
                    if not search_city and context:
                        search_city = context.get("city")
                    
                    # Check if we need to ask for location (one clarification rule)
                    has_location = (
                        latitude is not None or 
                        search_city or 
                        (context and context.get("city"))
                    )
                    
                    if parsed_query.near_me and not has_location:
                        # ONE CLARIFICATION: Ask for city
                        term_display = parsed_query.terms if parsed_query.terms else "shops"
                        final_text = f"I can help you find {term_display} nearby! 🔍 What city or area are you in?"
                        deps.context["pending_search_category"] = search_category
                    else:
                        # Execute search directly
                        results = db_interface.search_shops(
                            query=parsed_query.terms if parsed_query.terms else None,
                            shop_type=search_category,
                            city=search_city,
                            latitude=latitude,
                            longitude=longitude,
                            limit=10
                        )
                        
                        # Record action
                        actions.append({
                            "tool": "search_shops",
                            "result": results,
                            "params": {
                                "category": search_category,
                                "city": search_city,
                                "terms": parsed_query.terms,
                                "near_me": parsed_query.near_me
                            },
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        logger.info(f"Direct search | category={search_category} | city={search_city} | results={len(results)}")
                        
                        # Generate brief response based on results
                        if len(results) == 0:
                            cat_display = search_category or parsed_query.terms or "shops"
                            final_text = f"No results found for '{cat_display}'. Try a different category or area?"
                        elif len(results) == 1:
                            shop_name = results[0].get('name', 'a shop')
                            final_text = f"Found one option: {shop_name}! 🎯"
                        else:
                            final_text = f"Found {len(results)} options near you! 🎉"
                else:
                    # Let LLM decide for unclear queries (pricing, features, etc.)
                    full_context = "\n".join(context_parts)
                    full_msg = f"{full_context}\n\nUser message: {user_msg}" if full_context else user_msg
                    
                    result = await self.agent.run(full_msg, deps=deps)
                    
                    # Extract response
                    if hasattr(result, 'data') and hasattr(result.data, 'response'):
                        final_text = result.data.response
                    elif hasattr(result, 'output'):
                        final_text = result.output
                    else:
                        final_text = str(result)
            
            # Voice optimization
            if is_voice and len(final_text) > 150:
                sentences = final_text.split('. ')
                if len(sentences) > 1:
                    final_text = sentences[0]
                    if len(sentences) > 1 and len(sentences[1]) < 40:
                        final_text += ". " + sentences[1]
                    
                    if not final_text.endswith('.'):
                        final_text += '.'
            
            # Update metrics
            for action in actions:
                tool_name = action.get("tool")
                if tool_name == "search_shops":
                    self.metrics["search_calls"] += 1
                    self.metrics["query_extractions"] += 1
            
            if actions:
                self.metrics["tool_calls"] += len(actions)
            
            # Track cache
            self.metrics["cache_hits"] = len(query_processor._extraction_cache)
            
            # Log conversation
            try:
                db_interface.add_message_to_history(session_id, "user", user_msg)
                db_interface.add_message_to_history(session_id, "assistant", final_text)
            except Exception as e:
                logger.warning(f"Failed to log conversation: {e}")
            
            processing_time = (datetime.now().timestamp() - start_time) * 1000
            
            logger.info(
                f"Response | user={user_id} | time={processing_time:.0f}ms | "
                f"tools={len(actions)} | response_len={len(final_text)}"
            )
            
            return {
                "response": final_text,
                "actions": actions,
                "agent_name": "ZeroQ",
                "processing_time_ms": processing_time,
                "metrics": {
                    "tools_called": len(actions),
                    "is_voice": is_voice,
                    "context_items": len(context_parts)
                }
            }
        
        except Exception as e:
            self.metrics["errors"] += 1
            logger.error(f"MasterAgent error: {e}", exc_info=True)
            
            processing_time = (datetime.now().timestamp() - start_time) * 1000
            
            fallback_response = (
                "I'm having trouble. Try: 'find barbers' or 'show pricing'" 
                if not is_voice 
                else "Sorry, please try again."
            )
            
            return {
                "response": fallback_response,
                "actions": [],
                "agent_name": "ZeroQ",
                "error": str(e),
                "processing_time_ms": processing_time
            }
    
    async def persist_learnings(self):
        """Persist learned patterns."""
        await self.category_manager.persist_learnings()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Return comprehensive metrics."""
        return {
            **self.metrics,
            "error_rate": self.metrics["errors"] / max(self.metrics["total_requests"], 1),
            "tools_per_request": self.metrics["tool_calls"] / max(self.metrics["total_requests"], 1),
            "voice_percentage": self.metrics["voice_requests"] / max(self.metrics["total_requests"], 1),
            "extraction_cache_size": len(query_processor._extraction_cache),
            "categories_count": len(category_manager.get_categories())
        }
    
    async def refresh_agent(self):
        """Refresh agent with updated categories."""
        global master_pydantic_agent
        
        self.category_manager.get_categories(force_refresh=True)
        master_pydantic_agent = create_master_agent()
        self.agent = master_pydantic_agent
        
        logger.info("Agent refreshed with updated categories")


# --- Background Tasks ---

async def start_background_tasks():
    """Start production background tasks."""
    
    # Refresh agent every 5 minutes
    async def refresh_loop():
        while True:
            await asyncio.sleep(300)
            try:
                category_manager.get_categories(force_refresh=True)
                
                global master_pydantic_agent
                master_pydantic_agent = create_master_agent()
                
                logger.info("Background: Agent refreshed")
            except Exception as e:
                logger.error(f"Background: Refresh error: {e}", exc_info=True)
    
    asyncio.create_task(refresh_loop())
    
    # Persist learnings every minute
    async def persist_loop():
        while True:
            await asyncio.sleep(60)
            try:
                await category_manager.persist_learnings()
                logger.info("Background: Learnings persisted")
            except Exception as e:
                logger.error(f"Background: Persist error: {e}", exc_info=True)
    
    asyncio.create_task(persist_loop())
    
    logger.info("Background tasks started")


# --- Admin Functions ---

def add_category_admin(category_key: str, display_name: str, aliases: List[str] = None):
    """Admin: Add new category."""
    category_manager.add_category(category_key, display_name, aliases or [])
    return {"success": True, "category": category_key}


def get_categories_admin():
    """Admin: View all categories."""
    categories = category_manager.get_categories()
    return {
        "categories": [
            {
                "key": cat_key,
                "display_name": cat_data["display_name"],
                "shop_count": cat_data["count"],
                "aliases": list(cat_data["aliases"])[:10],
                "example_shops": cat_data.get("example_shops", [])
            }
            for cat_key, cat_data in sorted(
                categories.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )
        ],
        "total": len(categories)
    }


def get_learned_synonyms_admin():
    """Admin: View learned patterns."""
    return {
        "synonyms": category_manager._synonym_map,
        "count": len(category_manager._synonym_map)
    }


def get_extraction_cache_admin():
    """Admin: View query extraction cache."""
    return {
        "cache": query_processor._extraction_cache,
        "size": len(query_processor._extraction_cache),
        "max_size": query_processor._cache_max_size
    }