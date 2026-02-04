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

class QueryProcessor:
    """
    Intelligent query processing using pure LLM extraction.
    NO hardcoded noise words - fully dynamic and adaptive.
    """
    
    def __init__(self):
        # Lightweight LLM agent for query extraction
        self.extraction_agent = Agent(
            model,
            system_prompt="""You are a search query optimizer.

Your job: Extract ONLY the meaningful search terms from user input.

Rules:
1. Remove filler words (find, show, get, me, the, a, an, please, etc.)
2. Remove location words (near, nearby, around, close, local)
3. Remove verbs (looking, searching, wanting)
4. Keep ONLY: business types, services, specific names, descriptive words

Examples:
Input: "find me barber shops near me"
Output: "barber"

Input: "looking for italian restaurants around here"
Output: "italian restaurant"

Input: "show me places that do haircuts"
Output: "haircut"

Input: "i want to get a fade at a barbershop please"
Output: "fade barbershop"

Input: "find shops"
Output: ""

Input: "barber"
Output: "barber"

Input: "best nail salon for manicure"
Output: "nail salon manicure"

Input: "car repair shop that does oil changes"
Output: "car repair oil change"

Input: "yo where can i get a fresh cut"
Output: "fresh cut"

Input: "besoin d'un coiffeur" (French for "need a hairdresser")
Output: "coiffeur"

Input: "показать парикмахерские" (Russian for "show barbershops")
Output: "парикмахерские"

Return ONLY the extracted terms, nothing else. If no meaningful terms, return empty string.
""",
            model_settings={'temperature': 0.1, 'max_tokens': 50}
        )
        
        # Cache for common queries (performance optimization)
        self._extraction_cache: Dict[str, str] = {}
        self._cache_max_size = 1000
    
    async def extract_search_terms(self, user_query: str) -> Optional[str]:
        """
        Extract meaningful search terms from user query using pure LLM.
        
        Args:
            user_query: Raw user input
            
        Returns:
            Cleaned search terms or None if nothing meaningful
        """
        
        if not user_query or not user_query.strip():
            return None
        
        # Normalize
        normalized = user_query.lower().strip()
        
        # Check cache first (performance)
        cache_key = hashlib.md5(normalized.encode()).hexdigest()
        if cache_key in self._extraction_cache:
            logger.debug(f"Cache hit for query: {normalized}")
            return self._extraction_cache[cache_key]
        
        try:
            # Use LLM to extract meaningful terms
            result = await self.extraction_agent.run(normalized)
            
            extracted = result.output.strip() if hasattr(result, 'output') else str(result).strip()
            
            # Handle empty extraction
            if not extracted or extracted == '""' or extracted == "''":
                extracted = None
            
            # Cache the result
            if len(self._extraction_cache) < self._cache_max_size:
                self._extraction_cache[cache_key] = extracted
            
            logger.debug(f"Query extracted: '{normalized}' -> '{extracted}'")
            
            return extracted
        
        except Exception as e:
            logger.error(f"Query extraction failed: {e}", exc_info=True)
            # Let the error propagate - no fallback
            raise

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
            system_prompt="""You are an intent classifier for a queue management assistant.

Classify user messages into ONE of these categories:

CONVERSATION - Greetings, small talk, general questions, thanks
Examples:
- "hello" → CONVERSATION
- "hi there" → CONVERSATION  
- "thanks" → CONVERSATION
- "how are you" → CONVERSATION
- "what is zeroqwait" → CONVERSATION
- "who are you" → CONVERSATION
- "cool" → CONVERSATION
- "okay" → CONVERSATION

ACTION - User wants to DO something specific that requires tools
Examples:
- "find me a barber" → ACTION
- "show pricing" → ACTION  
- "search for salons" → ACTION
- "looking for restaurants" → ACTION
- "what are the features" → ACTION

Rules:
1. If user is greeting or being social → CONVERSATION
2. If user mentions specific business types (barber, salon, restaurant, etc.) → ACTION
3. If user asks to "find", "search", "show me" + shops/businesses → ACTION
4. If user asks about pricing, features, FAQ → ACTION
5. If unsure, lean towards CONVERSATION

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
    
    async def classify_intent(self, user_msg: str) -> str:
        """Classify user intent using pure LLM."""
        try:
            result = await self.router_agent.run(user_msg)
            intent = result.output.strip().upper() if hasattr(result, 'output') else str(result).strip().upper()
            
            # Normalize response
            if 'CONVERSATION' in intent:
                return 'CONVERSATION'
            elif 'ACTION' in intent:
                return 'ACTION'
            else:
                # Default to conversation if unclear
                logger.debug(f"Unclear intent response: {intent}, defaulting to CONVERSATION")
                return 'CONVERSATION'
        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            return 'CONVERSATION'  # Safe default
    
    async def get_conversational_response(self, user_msg: str, context: Dict[str, Any] = None) -> str:
        """Get a conversational response without tools."""
        try:
            # Add any relevant context
            context_str = ""
            if context:
                if context.get('active_view'):
                    context_str += f"User is viewing: {context['active_view']} page. "
                if context.get('city'):
                    context_str += f"User is in: {context['city']}. "
            
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

## WHEN TO USE TOOLS

**ONLY call search_shops when user:**
- Mentions a specific business type (barber, salon, restaurant, etc.)
- Says "find", "search", "show me", "looking for" + business/shop context
- Asks about shops "near me" or in a specific location

**Examples that REQUIRE tools:**
- "find me a barber" → search_shops(category="barber")
- "show me salons nearby" → search_shops(category="salon")
- "restaurants in Toronto" → search_shops(category="restaurant", city="Toronto")
- "how much does it cost" → check_pricing()
- "show pricing" → check_pricing()

**Examples that DON'T need tools (respond directly):**
- "hello" → Greet back warmly
- "thanks" → You're welcome!
- "what is this" → Explain ZeroQwait
- "cool" → Glad you like it! Need anything else?
- "okay" → Great! Let me know if you need help.

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

Use this to personalize responses when relevant.

Remember: Be conversational FIRST. Only use tools when the user is clearly asking for something that requires them.
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
        description="Shop category (e.g., 'barber', 'salon', 'restaurant'). Leave empty to search all."
    ),
    city: Optional[str] = Field(
        default=None, 
        description="City name if user mentioned one. Leave empty to use location."
    ),
    query: Optional[str] = Field(
        default=None, 
        description="User's search query - will be automatically cleaned and optimized."
    )
) -> str:
    """
    Search for local businesses. 
    Query cleaning is automatic - just pass the user's input.
    """
    
    try:
        # Smart query extraction (pure LLM, no hardcoded patterns)
        clean_query = None
        if query:
            clean_query = await query_processor.extract_search_terms(query)
            logger.debug(f"Query processing: '{query}' → '{clean_query}'")
        
        # Execute search
        result = db_interface.search_shops(
            query=clean_query,
            shop_type=category,
            city=city,
            latitude=ctx.deps.latitude,
            longitude=ctx.deps.longitude,
            limit=10
        )
        
        # Store results
        ctx.deps.actions.append({
            "tool": "search_shops",
            "result": result,
            "params": {
                "category": category,
                "city": city,
                "original_query": query,
                "cleaned_query": clean_query
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
            f"query='{query}' → '{clean_query}' | results={len(result)} | "
            f"voice={ctx.deps.is_voice}"
        )
        
        # Guidance for LLM
        if len(result) == 0:
            return (
                "No shops found. Suggest: (1) different category, "
                "(2) broader search, or (3) different area. Stay helpful and positive."
            )
        elif len(result) == 1:
            return (
                f"Found 1 shop: {result[0].get('name', 'shop')}. "
                f"Voice: 'Found 1 shop nearby!' | Text: 'I found 1 shop!'"
            )
        else:
            return (
                f"Found {len(result)} shops. They're visible as cards in UI. "
                f"Voice: 'Found {len(result)} shops nearby!' | "
                f"Text: 'I found {len(result)} shops near you!'"
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
            
            if history and len(history) > 0:
                last_user_msg = next((h for h in reversed(history) if h.get('role') == 'user'), None)
                if last_user_msg:
                    snippet = last_user_msg.get('content', '')[:50]
                    context_parts.append(f"[RECENT HISTORY: '{snippet}...']")
            
            # LLM processing
            self.metrics["llm_calls"] += 1
            
            full_context = "\n".join(context_parts)
            full_msg = f"{full_context}\n\nUser message: {user_msg}" if full_context else user_msg
            
            logger.info(
                f"LLM Request | user={user_id} | voice={is_voice} | "
                f"msg='{user_msg[:50]}...' | context_items={len(context_parts)}"
            )
            
            # Step 1: Classify intent using LLM (no hardcoded patterns)
            intent = await intent_router.classify_intent(user_msg)
            logger.info(f"Intent classified as: {intent}")
            
            # Step 2: Route based on intent
            if intent == 'CONVERSATION':
                # Use conversational agent (no tools)
                final_text = await intent_router.get_conversational_response(user_msg, context)
                logger.info(f"Conversational response generated (no tools)")
            else:
                # Use tool-enabled agent for actions
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