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
from redis_client import redis_client
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

logger = logging.getLogger(__name__)

# --- Configuration ---
ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
model = OpenAIModel(
    'gpt-oss:20b',
    provider=OpenAIProvider(base_url=ollama_url, api_key='ollama'),
)


# --- Circuit Breaker for LLM Resilience ---

class CircuitBreaker:
    """
    Circuit breaker pattern for LLM calls.
    If the LLM fails too many times, switch to fallback mode for a period.
    This prevents hanging on an overloaded Ollama server.
    """
    
    def __init__(self, failure_threshold: int = 3, reset_timeout: int = 30):
        self.failures = 0
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure = None
        self.is_open = False
        self._lock = asyncio.Lock()
    
    async def call(self, func, fallback_func, *args, **kwargs):
        """
        Execute func with circuit breaker protection.
        If circuit is open, use fallback_func instead.
        """
        async with self._lock:
            # Check if circuit should reset
            if self.is_open:
                import time
                if time.time() - self.last_failure > self.reset_timeout:
                    logger.info("Circuit breaker reset - trying LLM again")
                    self.is_open = False
                    self.failures = 0
                else:
                    logger.warning("Circuit breaker OPEN - using fallback")
                    return await fallback_func(*args, **kwargs)
        
        try:
            # Use timeout to prevent hanging
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=15.0)
            
            async with self._lock:
                self.failures = 0
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning("LLM call timed out")
            await self._record_failure()
            return await fallback_func(*args, **kwargs)
            
        except Exception as e:
            logger.warning(f"LLM call failed: {e}")
            await self._record_failure()
            return await fallback_func(*args, **kwargs)
    
    async def _record_failure(self):
        import time
        async with self._lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self.is_open = True
                self.last_failure = time.time()
                logger.error(f"Circuit breaker OPENED after {self.failures} failures")


# Global circuit breaker instance
llm_circuit_breaker = CircuitBreaker()

# --- Smart Query Processor ---

from dataclasses import dataclass
import numpy as np

embedder = None

def get_embedder():
    global embedder
    if embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            embedder = SentenceTransformer('all-MiniLM-L6-v2')
        except KeyError:
            import os
            from sentence_transformers import SentenceTransformer
            os.environ["SENTENCE_TRANSFORMERS_HOME"] = "/tmp/st_home"
            embedder = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.error(f"Failed to load embedder: {e}")
    return embedder

class SemanticCache:
    """Lightweight semantic cache using sentence-transformers."""
    def __init__(self, threshold=0.92):
        self.threshold = threshold
        self.local_cache = []  # List of (embedding_vector, QueryAnalysis_dict)
    
    def get(self, query: str) -> Optional[dict]:
        if not query.strip() or not self.local_cache:
            return None
        try:
            embedder_inst = get_embedder()
            if not embedder_inst:
                return None
            vec = embedder_inst.encode([query.strip().lower()])[0]
            best_score = 0
            best_match = None
            
            # Pure local fast evaluation
            for (v, res) in self.local_cache:
                score = np.dot(vec, v) / (np.linalg.norm(vec) * np.linalg.norm(v))
                if score > best_score:
                    best_score = score
                    best_match = res
                    
            if best_score >= self.threshold:
                logger.debug(f"Semantic Cache Hit! Score: {best_score:.3f}")
                return best_match
            return None
        except Exception as e:
            logger.error(f"Semantic cache error: {e}")
            return None
            
    def set(self, query: str, result_dict: dict):
        try:
            embedder_inst = get_embedder()
            if not embedder_inst:
                return
            vec = embedder_inst.encode([query.strip().lower()])[0]
            self.local_cache.append((vec, result_dict))
            # Keep cache from growing infinitely in demo
            if len(self.local_cache) > 1000:
                self.local_cache = self.local_cache[-1000:]
        except Exception as e:
            logger.error(f"Failed to set cache: {e}")
            if len(self.local_cache) > 1000:
                self.local_cache.pop(0)
        except Exception as e:
            pass

semantic_cache = SemanticCache()

# --- Unified Query Analyzer ---

class ContextUpdates(BaseModel):
    last_category: Optional[str] = Field(default=None, description="The most recent business category/service.")
    last_city: Optional[str] = Field(default=None, description="The most recent city/location.")

class QueryAnalysis(BaseModel):
    intent: str = Field(description="Must be 'CONVERSATION', 'ACTION', or 'UNCLEAR'.")
    terms: str = Field(description="Extracted search terms, business type, or service keywords (e.g. 'alien pet groomer'). Empty string if not searching.")
    city: Optional[str] = Field(default=None, description="Explicit city mentioned in query.")
    near_me: bool = Field(default=False, description="True if user wants proximity search (near me, nearby).")
    context_updates: ContextUpdates

class UnifiedQueryAnalyzer:
    """Single-pass Pydantic LLM extractor. Replaces IntentRouter, QueryProcessor, ContextExtractor."""
    
    def __init__(self):
        self.analyzer_agent = Agent(
            model,
            output_type=QueryAnalysis,
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
- If intent is CONVERSATION or UNCLEAR, terms should be empty "".

Rules for 'city':
- Explicitly extract any city name mentioned in the current query (e.g., 'Toronto', 'Austin').
- If no new city is mentioned, leave it null.

Rules for 'near_me':
- True ONLY if user explicitly says "near me", "nearby", "around here".

Rules for 'context_updates':
- 'last_category': The LATEST business/service category discovered. Keep old if user only changed location.
- 'last_city': The LATEST city mentioned. Keep old if user only changed category.
""",
            model_settings={'temperature': 0.1, 'max_tokens': 200}
        )
        
        self.conversation_agent = Agent(
            model,
            system_prompt="""You are ZeroQ, a friendly AI assistant for ZeroQwait.
Help find local shops and join queues remotely. Pricing: Free ($0/mo), Premium ($29/mo), Enterprise.
Respond naturally, warm, and concise (1-2 sentences).
""",
            model_settings={'temperature': 0.7}
        )

    async def analyze(self, user_msg: str, history_context: str = "") -> QueryAnalysis:
        # Check Semantic Cache First
        cached_dict = semantic_cache.get(user_msg)
        if cached_dict:
            return QueryAnalysis(**cached_dict)
            
        full_prompt = f"{history_context}\n\nCurrent message: {user_msg}" if history_context else user_msg
        
        async def _fallback(prompt):
            mock_data = QueryAnalysis(
                intent='ACTION',
                terms=user_msg if len(user_msg) < 50 else "",
                city=None,
                near_me="near" in user_msg.lower() or "nearby" in user_msg.lower(),
                context_updates=ContextUpdates(last_category=None, last_city=None)
            )
            return type('MockResult', (), {'data': mock_data})()
            
        try:
            result = await llm_circuit_breaker.call(
                self.analyzer_agent.run,
                _fallback,
                full_prompt
            )
            analysis = result.data
            
            # Write successful extraction backwards into Semantic Cache
            semantic_cache.set(user_msg, analysis.model_dump())
            return analysis
        except Exception as e:
            logger.error(f"Unified analyzer failed: {e}")
            return await _fallback(full_prompt).data
            
    async def get_conversational_response(self, user_msg: str, context: Dict[str, Any] = None, history_context: str = "") -> str:
        context_parts = []
        if history_context:
            context_parts.append(history_context)
        if context and context.get('active_view'):
            context_parts.append(f"Viewing: {context['active_view']} page.")
            
        context_str = "\n".join(context_parts)
        full_msg = f"{context_str}\n\nUser: {user_msg}" if context_str else user_msg
        
        try:
            result = await self.conversation_agent.run(full_msg)
            return result.data if hasattr(result, 'data') else str(result)
        except Exception:
            return "Hello! 👋 I'm ZeroQ. How can I help you today? I can help you find shops, check pricing, or answer questions!"

unified_query_analyzer = UnifiedQueryAnalyzer()



# --- Category Manager ---

class CategoryManager:
    """
    Dynamic category system with smart query processing and Redis caching.
    Zero hardcoded categories - pure database-driven.
    """
    
    def __init__(self):
        self._synonym_map = {}
        self._learning_queue = []
        # We rely on Redis for category cache now
    
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
                        "aliases": [shop_type],  # Use list for JSON serialization
                        "count": 0,
                        "keywords": [], # Use list for JSON serialization
                        "example_shops": []
                    }
                
                category_stats[shop_type]["count"] += 1
                
                if len(category_stats[shop_type]["example_shops"]) < 3:
                    category_stats[shop_type]["example_shops"].append(shop.get('name', ''))
                
                if shop.get('name'):
                    name_words = [w.lower() for w in shop['name'].split() if len(w) > 3]
                    # keywords is list now
                    for w in name_words[:5]:
                        if w not in category_stats[shop_type]["keywords"]:
                            category_stats[shop_type]["keywords"].append(w)
                
                if shop.get('description'):
                    desc_words = [w.lower() for w in shop['description'].split() if len(w) > 3]
                     # keywords is list now
                    for w in desc_words[:5]:
                        if w not in category_stats[shop_type]["keywords"]:
                            category_stats[shop_type]["keywords"].append(w)
            
            # Load explicit aliases from database
            try:
                db_aliases = db_interface.get_category_aliases()
                for alias_row in db_aliases:
                    cat_key = alias_row['category_key']
                    alias = alias_row['alias']
                    
                    if cat_key in category_stats and alias not in category_stats[cat_key]["aliases"]:
                        category_stats[cat_key]["aliases"].append(alias)
            except Exception as e:
                logger.warning(f"Could not load category aliases: {e}")
            
            # Load learned synonyms
            try:
                learned = db_interface.get_learned_synonyms()
                for syn_row in learned:
                    query_term = syn_row['query_term']
                    category = syn_row['category']
                    
                    if category in category_stats:
                        if query_term not in category_stats[category]["aliases"]:
                            category_stats[category]["aliases"].append(query_term)
                        self._synonym_map[query_term] = category
            except Exception as e:
                logger.warning(f"Could not load learned synonyms: {e}")
            
            return category_stats
        
        except Exception as e:
            logger.error(f"Error loading categories from DB: {e}", exc_info=True)
            return {}
    
    def get_categories(self, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """Get categories with Redis caching."""
        cache_key = "all_categories"
        
        if not force_refresh:
            cached = redis_client.get(cache_key)
            if cached:
                return cached
        
        logger.info("Refreshing category cache from database")
        categories = self._load_categories_from_db()
        
        # Cache for 5 minutes
        redis_client.set(cache_key, categories, ttl=300)
        
        return categories
    
    async def detect_category(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Detect category from user input.
        """
        if not user_input:
            if context and context.get("preferred_category"):
                return context["preferred_category"]
            return None
        
        normalized = user_input.lower()
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
    reasoning: str = Field(description="Internal thought process regarding tools and decision making.")
    response: str = Field(description="The friendly response to show the user.")


# --- Dynamic System Prompt ---

def get_master_system_prompt() -> str:
    """Generate system prompt dynamically from database knowledge."""
    available_categories = category_manager.get_available_categories_text()
    
    # Fetch knowledge from DB with fallbacks
    def get_knowledge(key, default):
        item = db_interface.get_agent_knowledge(key)
        return item['content'] if item else default

    critical_instructions = get_knowledge("critical_instructions", "")
    about_zeroqwait = get_knowledge("about_zeroqwait", "")
    conversational_responses = get_knowledge("conversational_responses", "")
    search_guidance = get_knowledge("search_guidance", "")
    
    # Default fallback if DB is empty for about section only to ensure basics
    if not about_zeroqwait:
        about_zeroqwait = """
## ABOUT ZEROQWAIT

ZeroQwait is a queue management platform that helps customers find shops and join queues remotely.
"""

    return f"""You are ZeroQ, the friendly AI Assistant for ZeroQwait.

{critical_instructions}

{about_zeroqwait}

## AVAILABLE SHOP CATEGORIES
{available_categories}

{conversational_responses}

{search_guidance}
"""


# --- Create Agent ---

def create_master_agent():
    """Create agent with current system prompt."""
    return Agent(
        model,
        deps_type=MasterAgentDeps,
        output_type=MasterResponse,  # <--- CRITICAL: Enforce structured output
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
    
    DO NOT use this tool for: pricing, features, faq, or testimonials.
    """
    
    try:
        # Check if there's an original query; fallback to passed query
        original_query = ctx.deps.context.get("original_user_message", query or "")
        clean_terms = None
        user_wants_nearby = False
        extracted_city = city
        
        if original_query:
            # Use unified query analyzer to keep extraction consistent
            analysis = await unified_query_analyzer.analyze(original_query)
            clean_terms = analysis.terms if analysis.terms else None
            user_wants_nearby = analysis.near_me
            if not extracted_city and analysis.city:
                extracted_city = analysis.city
        
        # --- INTENT MANIPULATION SAFETY NET ---
        # If the agent mistakenly called search_shops for specific pages, handle it here.
        # FIX: Check raw query as well, since terms might be empty for non-search queries
        check_term = ((query or "") + " " + (category or "") + " " + (clean_terms or "")).lower()
        
        if any(x in check_term for x in ['testimonial', 'review', 'story']):
            ctx.deps.actions.append({
                "tool": "navigate_to_page_section",
                "result": {"target": "testimonials"},
                "timestamp": datetime.now().isoformat()
            })
            return "Testimonials section visible. Mention that many shop owners and customers love the platform."
            
        if any(x in check_term for x in ['pricing', 'cost', 'plan', 'price']):
            ctx.deps.actions.append({
                "tool": "navigate_to_page_section",
                "result": {"target": "pricing"},
                "timestamp": datetime.now().isoformat()
            })
            return "Pricing page now visible. Plans: Free ($0/mo), Premium ($29/mo), Enterprise (custom)."

        if any(x in check_term for x in ['feature', 'capability']):
            ctx.deps.actions.append({
                "tool": "navigate_to_page_section",
                "result": {"target": "features"},
                "timestamp": datetime.now().isoformat()
            })
            return "Features page visible. Highlight: Queue management, SMS, Analytics."

        if any(x in check_term for x in ['faq', 'help', 'support']):
            ctx.deps.actions.append({
                "tool": "navigate_to_page_section",
                "result": {"target": "faq"},
                "timestamp": datetime.now().isoformat()
            })
            return "FAQ section visible."
        # ----------------------------------------

        
        # ONE CLARIFICATION GATE: Only ask if near_me=true but no location info
        has_exact_coords = ctx.deps.latitude is not None and ctx.deps.longitude is not None
        has_location = (
            has_exact_coords or 
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
        # Run DB query in thread pool to prevent blocking event loop
        result = await asyncio.to_thread(
            db_interface.search_shops,
            clean_terms,      # query
            category,         # shop_type
            extracted_city,   # city
            ctx.deps.latitude,# latitude
            ctx.deps.longitude,# longitude
            10                # limit
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
            search_desc = category or clean_terms or "any shops"
            return (
                f"No shops found for '{search_desc}'. "
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


@master_pydantic_agent.tool
async def see_testimonials(ctx: RunContext[MasterAgentDeps]) -> str:
    """Show testimonials/reviews section."""
    ctx.deps.actions.append({
        "tool": "navigate_to_page_section",
        "result": {"target": "testimonials"},
        "timestamp": datetime.now().isoformat()
    })
    
    logger.info(f"Testimonials viewed | user={ctx.deps.user_id} | voice={ctx.deps.is_voice}")
    
    return "Testimonials section visible. Mention that many shop owners and customers love the platform."


# --- ACTIVE SERVICE TOOLS ---

@master_pydantic_agent.tool
async def join_queue(
    ctx: RunContext[MasterAgentDeps],
    shop_id: int = Field(description="ID of the shop to join queue at"),
    customer_name: str = Field(description="Name of the customer joining"),
    phone: Optional[str] = Field(default=None, description="Optional phone number for notifications")
) -> str:
    """Join a queue at a specific shop. Use when user wants to get in line."""
    logger.info(f"join_queue called | shop_id={shop_id} | customer={customer_name}")
    
    result = await asyncio.to_thread(db_interface.join_queue_for_shop, shop_id, customer_name, phone)
    
    ctx.deps.actions.append({
        "tool": "join_queue",
        "result": result,
        "params": {"shop_id": shop_id, "customer_name": customer_name},
        "timestamp": datetime.now().isoformat()
    })
    
    if result.get("error"):
        return f"Could not join queue: {result['error']}"
    
    return (
        f"Successfully added {result['customer_name']} to {result['shop_name']}! "
        f"Position #{result['position']}, estimated wait: {result['estimated_wait_minutes']} minutes. "
        f"Queue ticket ID: {result['queue_item_id']}."
    )


@master_pydantic_agent.tool
async def get_wait_time(
    ctx: RunContext[MasterAgentDeps],
    shop_id: int = Field(description="ID of the shop to check wait time for")
) -> str:
    """Get estimated wait time for a shop's queue. Use when user asks about wait times."""
    logger.info(f"get_wait_time called | shop_id={shop_id}")
    
    result = await asyncio.to_thread(db_interface.get_shop_wait_time, shop_id)
    
    ctx.deps.actions.append({
        "tool": "get_wait_time",
        "result": result,
        "params": {"shop_id": shop_id},
        "timestamp": datetime.now().isoformat()
    })
    
    if result.get("error"):
        return f"Could not get wait time: {result['error']}"
    
    if result['wait_minutes'] == 0:
        return f"No wait at {result['shop_name']}! The queue is empty."
    
    return (
        f"{result['shop_name']} has {result['queue_length']} people waiting. "
        f"Estimated wait: about {result['wait_minutes']} minutes."
    )


@master_pydantic_agent.tool
async def check_queue_status(
    ctx: RunContext[MasterAgentDeps],
    queue_item_id: int = Field(description="Queue ticket ID to check status for")
) -> str:
    """Check current position and wait time for a queue ticket. Use when user wants to check their place in line."""
    logger.info(f"check_queue_status called | queue_item_id={queue_item_id}")
    
    result = await asyncio.to_thread(db_interface.get_queue_position, queue_item_id)
    
    ctx.deps.actions.append({
        "tool": "check_queue_status",
        "result": result,
        "params": {"queue_item_id": queue_item_id},
        "timestamp": datetime.now().isoformat()
    })
    
    if result.get("error"):
        return f"Could not find queue status: {result['error']}"
    
    if result['status'] != 'waiting':
        return f"{result['customer_name']}'s status at {result['shop_name']}: {result['status'].upper()}"
    
    return (
        f"{result['customer_name']} is #{result['position']} at {result['shop_name']}. "
        f"{result['people_ahead']} people ahead, about {result['estimated_wait_minutes']} minutes wait."
    )


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
        """Format conversation history as string for analyzers."""
        if not history:
            return ""
        recent = history[-6:]
        formatted = [f"{'User' if m.get('role') == 'user' else 'ZeroQ'}: {m.get('content', '')[:200]}" for m in recent]
        return "[CONVERSATION HISTORY]\n" + "\n".join(formatted)

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
        """Process user message using native Pydantic ModelMessage arrays."""
        
        self.metrics["total_requests"] += 1
        if is_voice:
            self.metrics["voice_requests"] += 1
        else:
            self.metrics["text_requests"] += 1
            
        start_time = datetime.now().timestamp()
        
        try:
            deps = MasterAgentDeps(
                session_id=session_id, latitude=latitude, longitude=longitude,
                context=context or {}, actions=[], user_id=user_id,
                is_voice=is_voice, request_timestamp=start_time
            )
            deps.context["original_user_message"] = user_msg
            
            # Load from fast Redis store
            conversation_history = redis_client.get_session_history(session_id, limit=10)
            history_context_str = self._format_history_for_llm(conversation_history)
            
            # --- Pydantic AI History Mapping ---
            from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart
            message_history = []
            for msg in conversation_history:
                if msg.get('role') == 'user':
                    message_history.append(ModelRequest(parts=[UserPromptPart(content=msg.get('content', ''))]))
                elif msg.get('role') == 'assistant':
                    message_history.append(ModelResponse(parts=[TextPart(content=msg.get('content', ''))]))
            
            # --- Single Pass Unified Extraction ---
            analysis = await unified_query_analyzer.analyze(user_msg, history_context_str)
            intent = analysis.intent
            
            # Keep Session Context Live
            if analysis.context_updates.last_category:
                deps.context["last_search_category"] = analysis.context_updates.last_category
            if analysis.context_updates.last_city:
                deps.context["last_search_city"] = analysis.context_updates.last_city
                
            logger.info(f"Analyzer: intent={intent}, terms='{analysis.terms}', city={analysis.city}, near_me={analysis.near_me}")
            
            # Build Context Parts
            context_parts = []
            if context and context.get("active_view"):
                context_parts.append(f"[USER VIEWING: {context['active_view']} page]")
            if latitude and longitude:
                city_name = context.get("city", "unknown location") if context else "unknown location"
                context_parts.append(f"[LOCATION: {city_name} ({latitude}, {longitude})]")
            elif context and context.get("city"):
                context_parts.append(f"[CITY: {context['city']}]")
            if context and context.get("last_action"):
                context_parts.append(f"[PREVIOUS ACTION: {context['last_action']}]")
            
            input_method = "voice" if is_voice else "text"
            context_parts.append(f"[INPUT: {input_method}]")
            
            if analysis.context_updates.last_category:
                context_parts.append(f"[LAST CATEGORY: {analysis.context_updates.last_category}]")
                if analysis.context_updates.last_city:
                    context_parts[-1] += f" [LAST CITY: {analysis.context_updates.last_city}]"
                    
            full_context = "\n".join(context_parts)
            full_msg = f"{full_context}\n\nUser message: {user_msg}" if full_context else user_msg
            
            # --- Decision Routing ---
            if intent == 'CONVERSATION':
                final_text = await unified_query_analyzer.get_conversational_response(user_msg, deps.context, history_context_str)
            elif intent == 'UNCLEAR':
                final_text = "I'm not sure if you'd like to chat or find a shop. Could you clarify? 🤔"
            else:
                has_search_terms = bool(analysis.terms)
                has_city_only = bool(analysis.city) and not analysis.terms
                has_near_me_only = analysis.near_me and not analysis.terms
                
                if has_search_terms or has_city_only or has_near_me_only:
                    logger.info("Direct Search Path")
                    search_category = analysis.terms if analysis.terms else analysis.context_updates.last_category
                    search_city = analysis.city or analysis.context_updates.last_city
                    if not search_city and context:
                        search_city = context.get("city")
                    
                    has_exact_coords = latitude is not None and longitude is not None
                    has_location = (has_exact_coords or search_city or (context and context.get("city")))
                    
                    if analysis.near_me and not has_location:
                        term_display = search_category if search_category else "shops"
                        final_text = f"I can help you find {term_display} nearby! 🔍 What city or area are you in?"
                        deps.context["pending_search_category"] = search_category
                    else:
                        results = await asyncio.to_thread(
                            db_interface.search_shops,
                            analysis.terms if analysis.terms else None,
                            search_category,
                            search_city,
                            latitude,
                            longitude,
                            10
                        )
                        deps.actions.append({"tool": "search_shops", "result": results})
                        if len(results) == 0:
                            cat_display = search_category or analysis.terms or "shops"
                            final_text = f"No results found for '{cat_display}'. Try a different category or area?"
                        elif len(results) == 1:
                            final_text = f"Found one option: {results[0].get('name', 'a shop')}! 🎯"
                        else:
                            final_text = f"Found {len(results)} options near you! 🎉"
                else:
                    self.metrics["llm_calls"] += 1
                    result = await self.agent.run(full_msg, message_history=message_history, deps=deps)
                    # Extract response natively from pydantic-ai
                    if hasattr(result, 'data') and hasattr(result.data, 'response'):
                        final_text = result.data.response
                    else:
                        final_text = str(result.data) if hasattr(result, 'data') else str(result)
                        
            # Voice optimization
            if is_voice and len(final_text) > 150:
                sentences = final_text.split('. ')
                if len(sentences) > 1:
                    final_text = sentences[0]
                    if len(sentences) > 1 and len(sentences[1]) < 40:
                        final_text += ". " + sentences[1]
                    if not final_text.endswith('.'):
                        final_text += '.'
            
            processing_time = (datetime.now().timestamp() - start_time) * 1000
            
            return {
                "response": final_text,
                "actions": deps.actions,
                "agent_name": "ZeroQ",
                "processing_time_ms": processing_time,
                "metrics": {
                    "tools_called": len(deps.actions),
                    "is_voice": is_voice,
                    "context_items": len(context_parts)
                }
            }
            
        except Exception as e:
            self.metrics["errors"] += 1
            logger.error(f"MasterAgent error: {e}", exc_info=True)
            processing_time = (datetime.now().timestamp() - start_time) * 1000
            return {
                "response": "I'm having trouble. Try: 'find barbers' or 'show pricing'",
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
        "cache": "redis",
        "message": "Using Redis for caching (metrics not available via this endpoint)",
        "size": 0
    }