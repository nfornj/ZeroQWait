import os
import re
import json
import logging
import asyncio
import httpx
import base64
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

# --- Precompiled Regex for Hot Paths ---
_SENTENCE_BOUNDARY_RE = re.compile(r'(?<=[.?!])\s+')
_MARKDOWN_BOLD_RE = re.compile(r'\*\*(.*?)\*\*')
_MARKDOWN_ITALIC_RE = re.compile(r'\*(.*?)\*')
_MARKDOWN_HEADING_RE = re.compile(r'#{1,6}\s')
_MARKDOWN_CODE_RE = re.compile(r'`([^`]*)`')
_MARKDOWN_LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]+\)')
_EMOJI_RE = re.compile(
    r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
    r'\U0001F1E0-\U0001F1FF\U00002600-\U000026FF\U00002700-\U000027BF'
    r'\U0000FE00-\U0000FE0F\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F'
    r'\U0001FA70-\U0001FAFF\U0000200D\U000020E3\U000E0020-\U000E007F]'
)
_WHITESPACE_MULTI_RE = re.compile(r'\s{2,}')

# Fast greeting prefilter — skips analyzer LLM call for trivial messages
_GREETING_RE = re.compile(
    r'^(hi|hello|hey|hola|thanks|thank you|thx|ok|okay|sure|yes|no|yep|nope|bye|goodbye|cool|great|awesome|got it|sounds good)\b',
    re.IGNORECASE
)

# Shared httpx client for TTS (connection pooling)
_tts_client: Optional[httpx.AsyncClient] = None

def _get_tts_client() -> httpx.AsyncClient:
    global _tts_client
    if _tts_client is None or _tts_client.is_closed:
        _tts_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3)
        )
    return _tts_client

# --- Configuration ---
ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
model_name = os.getenv("MODEL_NAME", "llama3.2:latest")
model = OpenAIModel(
    model_name,
    provider=OpenAIProvider(base_url=ollama_url, api_key='ollama'),
)


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
            norm = np.linalg.norm(vec)
            if norm == 0:
                return None
            normed_vec = vec / norm
            
            # Batch cosine similarity — pre-normalized vectors
            cached_vecs = np.array([v for v, _ in self.local_cache])
            scores = cached_vecs @ normed_vec
            best_idx = int(np.argmax(scores))
            best_score = scores[best_idx]
                    
            if best_score >= self.threshold:
                logger.debug(f"Semantic Cache Hit! Score: {best_score:.3f}")
                return self.local_cache[best_idx][1]
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
            norm = np.linalg.norm(vec)
            if norm == 0:
                return
            normed_vec = vec / norm
            self.local_cache.append((normed_vec, result_dict))
            # Keep cache from growing infinitely
            if len(self.local_cache) > 1000:
                self.local_cache = self.local_cache[-1000:]
        except Exception as e:
            logger.error(f"Failed to set cache: {e}")

semantic_cache = SemanticCache()

# Eagerly initialize the embedder at module load time so the sentence-transformer model
# is downloaded before any request arrives (avoids a 60-90s stall on first request).
try:
    get_embedder()
    logger.info("Sentence-transformer embedder pre-loaded successfully.")
except Exception as _e:
    logger.warning(f"Embedder pre-load failed (non-fatal, will retry on first request): {_e}")


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
- CONVERSATION: The user is ANSWERING a question that ZeroQ asked (e.g. providing a name, address, email, shop details, confirmation). This is critical — look at the conversation history to see if ZeroQ asked for information.
- ACTION: The user is making a NEW search request for businesses, services, or locations.
- UNCLEAR: Ambiguous inputs.

CRITICAL — Follow-up detection:
If the conversation history shows ZeroQ just asked the user a question (e.g. "Could you share your shop name?", "What type of shop?", "What's your email?"), then the current message is a FOLLOW-UP ANSWER, NOT a new search.
Example:
  ZeroQ: "Could you share: 1. Shop name 2. Shop type 3. Address"
  User: "tutubaba is the shopname, shoptype is spa, address is 2570 bromus path, oshawa"
  → intent=CONVERSATION, terms="", city=null (the user is answering, NOT searching for a spa in oshawa)

Rules for 'terms':
- Extract the core business type or service ONLY when the user is making a NEW search request.
- Do NOT extract terms from follow-up answers to ZeroQ's questions.
- Do NOT hardcode categories. Dynamically extract the noun/service exactly as asked.
- Strip generic plural suffixes (shops, stores).
- If intent is CONVERSATION or UNCLEAR, terms MUST be empty "".

Rules for 'city':
- Extract city ONLY from NEW search requests, NOT from follow-up answers.
- If no new city is mentioned in a search context, leave it null.

Rules for 'near_me':
- True ONLY if user explicitly says "near me", "nearby", "around here" in a NEW search request.

Rules for 'context_updates':
- 'last_category': The LATEST business/service category from a search. Keep old if no new search.
- 'last_city': The LATEST city from a search. Keep old if no new search.
""",
            model_settings={'temperature': 0.1, 'max_tokens': 200}
        )
        
        self.conversation_agent = Agent(
            model,
            system_prompt="""You are ZeroQ, the AI receptionist for ZeroQwait — a queue management platform.

Your ONLY purpose is helping users with:
1. Registering a shop — Setting up their business on the ZeroQwait platform
2. Searching for shops — Finding services nearby and joining an AI-powered queue
3. Answering questions about our products — Pricing, features, and how the platform works

RULES:
- NEVER discuss topics outside ZeroQwait (no weather, no general knowledge, no recommendations unrelated to queue management)
- If the user says "hello" or greets you, introduce yourself and list what you can do: 1) Register a Shop, 2) Search for Shops and join an AI-powered queue, 3) Ask about our products
- Keep responses to 1-3 sentences maximum
- Always guide users toward these three core actions
""",
            model_settings={'temperature': 0.3}
        )

    async def analyze(self, user_msg: str, history_context: str = "") -> QueryAnalysis:
        # Check Semantic Cache First
        cached_dict = semantic_cache.get(user_msg)
        if cached_dict:
            return QueryAnalysis(**cached_dict)
            
        full_prompt = f"{history_context}\n\nCurrent message: {user_msg}" if history_context else user_msg
        
        try:
            result = await self.analyzer_agent.run(full_prompt)
            analysis = result.output
            
            # Write successful extraction backwards into Semantic Cache
            semantic_cache.set(user_msg, analysis.model_dump())
            return analysis
        except Exception as e:
            logger.error(f"Unified analyzer failed: {e}")
            # Degrade gracefully so the main agent can still attempt to answer
            return QueryAnalysis(
                intent='UNCLEAR',
                terms="",
                city=None,
                near_me="near" in user_msg.lower() or "nearby" in user_msg.lower(),
                context_updates=ContextUpdates(last_category=None, last_city=None)
            )
            
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
            return getattr(result, 'output', getattr(result, 'data', str(result)))
        except Exception:
            return "Hello! I'm ZeroQ. Here's what I can do for you:\n\n1. **Register a Shop** — Set up your business on our platform\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works\n\nWhat would you like to do?"

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
    """Generate system prompt dynamically from database knowledge (cached in Redis)."""
    available_categories = category_manager.get_available_categories_text()
    
    # Fetch knowledge from DB with Redis cache (5-min TTL)
    def get_knowledge(key, default):
        cache_key = f"agent_knowledge:{key}"
        cached = redis_client.get(cache_key)
        if cached is not None:
            return cached if cached else default
        item = db_interface.get_agent_knowledge(key)
        content = item['content'] if item else ""
        redis_client.set(cache_key, content, ttl=300)
        return content if content else default

    critical_instructions = get_knowledge("critical_instructions", "")
    about_zeroqwait = get_knowledge("about_zeroqwait", "")
    conversational_responses = get_knowledge("conversational_responses", "")
    search_guidance = get_knowledge("search_guidance", "")
    
    # Default fallbacks if DB is empty to ensure basics
    if not critical_instructions:
        critical_instructions = """
## CRITICAL INSTRUCTIONS
- If the user expressed intent to sign up, join, create account, or register (either as a customer or shop owner), you MUST call the `start_registration` tool.
- If the user explicitly or implicitly asks to find shops, see nearby businesses, or list options (e.g., "list shops near me", "find a barber"), you MUST call the `search_shops` tool immediately. Do not ask for their location first; the tool handles that.
- If the user asks about pricing or how much it costs, call `see_pricing`.
- If the user asks about features or what the app can do, call `see_features`.
- If the user asks for help or FAQ, call `see_faq`.
"""
    
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
        output_type=MasterResponse,  # <--- Essential for reliable tool coordination
        system_prompt=get_master_system_prompt(),
        retries=2,
        model_settings={'temperature': 0.3}
    )


master_pydantic_agent = create_master_agent()


# --- Tools ---

@master_pydantic_agent.tool
async def search_shops(
    ctx: RunContext[MasterAgentDeps], 
    category: Optional[str] = None,
    city: Optional[str] = None,
    query: Optional[str] = None
) -> str:
    """
    Search for local businesses or services.
    CRITICAL INSTRUCTION: If the user asks for anything related to "shops near me", "finding a business", or "looking for *", you MUST call this tool.
    DO NOT ATTEMPT TO ANSWER THEM CONVERSATIONALLY. DO NOT TELL THEM TO USE GOOGLE MAPS.
    Pass whatever keywords you have to 'query'. It is completely fine if 'city' or 'category' are null/empty.
    The system will automatically detect the user's location on the backend.
    """
    
    try:
        # Check if there's an original query; fallback to passed query
        original_query = ctx.deps.context.get("original_user_message", query or "")
        clean_terms = None
        user_wants_nearby = False
        extracted_city = city
        
        # Reuse cached analysis from stream_chat/chat — avoids redundant LLM call
        cached_analysis = ctx.deps.context.get("last_query_analysis")
        if cached_analysis:
            clean_terms = cached_analysis.get("terms") or None
            user_wants_nearby = cached_analysis.get("near_me", False)
            if not extracted_city and cached_analysis.get("city"):
                extracted_city = cached_analysis["city"]
        elif original_query:
            # Fallback: run analyzer only if no cached result
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
            
        # Stop the LLM from searching for "hey" or "hello"
        if check_term.strip() in ['hi', 'hello', 'hey', 'greetings', 'sup', 'yo']:
            return "Hello! How can I help you today?"
            
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
            return "I can help with that! What city or area are you looking in?"
        
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
            return f"I couldn't find {search_desc} in that area. Would you like to try a different location or category?"
        elif len(result) == 1:
            return f"I found 1 shop: {result[0].get('name', 'shop')}. Would you like to join the waitlist?"
        else:
            return f"I found {len(result)} options near you! I've displayed them on the screen."
    
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



@master_pydantic_agent.tool
async def start_registration(
    ctx: RunContext[MasterAgentDeps],
    account_type: Optional[str] = Field(
        default=None,
        description="The type of account the user wants: 'shop_owner' or 'customer'. Leave null if unknown."
    )
) -> str:
    """
    Start the interactive inline registration flow in the chat.
    Call this tool when:
    - User says they want to sign up, register, create an account
    - User asks how to get started as a shop owner
    - User wants to list their business
    - User says 'I want to join' or 'how do I start'
    
    Do NOT call this if the user is already logged in (context will indicate this).
    """
    from registration_agent import registration_agent

    # Start the registration session — returns the first form_step event
    form_event = registration_agent.start(
        session_id=ctx.deps.session_id,
        account_type=account_type if account_type in ("shop_owner", "customer") else None
    )

    ctx.deps.actions.append({
        "tool": "start_registration",
        "result": {"account_type": account_type or "unknown"},
        "form_event": form_event,
        "timestamp": datetime.now().isoformat()
    })

    logger.info(f"start_registration called | user={ctx.deps.user_id} | account_type={account_type} | first_step={form_event.get('step')}")

    if account_type == "shop_owner":
        return "Let's get your business registered! I'll walk you through it step by step."
    elif account_type == "customer":
        return "Let's create your account! I'll guide you through it."
    else:
        return "Let's get you registered! First, are you a shop owner or a customer?"


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
            
            # --- DIRECT SEARCH BYPASS ---
            # Only bypass when analyzer explicitly identifies a NEW search intent (ACTION).
            # If intent is CONVERSATION or UNCLEAR (e.g. user answering a follow-up question),
            # defer to the LLM — this is scalable across all conversational flows.
            is_search_intent = (
                analysis.intent == 'ACTION' 
                and (analysis.terms or analysis.near_me or analysis.city)
            )
            
            logger.info(f"Search bypass decision: intent={analysis.intent}, terms='{analysis.terms}', is_search={is_search_intent}")
            
            if is_search_intent:
                logger.info("Direct Search Bypass Triggered")
                final_text = await search_shops(
                    RunContext(deps=deps, model=model, usage=None, prompt=""),
                    category=analysis.context_updates.last_category,
                    city=analysis.city,
                    query=user_msg
                )
            else:
                self.metrics["llm_calls"] += 1
                result = await asyncio.wait_for(
                    self.agent.run(full_msg, message_history=message_history, deps=deps),
                    timeout=300.0
                )
                final_text = result.output.response
                        
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
            logger.error(f"MasterAgent error: {e}")
            
            # If output validation fails (e.g. LLM couldn't format a simple greeting as JSON),
            # try to fallback to a basic text conversation to prevent a hard crash on 'hello'.
            if "validation" in str(e).lower() or "timeout" in str(e).lower():
                logger.info("Falling back to pure conversational response due to formatting error")
                fallback_text = await unified_query_analyzer.get_conversational_response(user_msg, deps.context, history_context_str)
                return {
                    "response": fallback_text,
                    "actions": [],
                    "agent_name": "ZeroQ",
                    "processing_time_ms": (datetime.now().timestamp() - start_time) * 1000,
                    "metrics": {
                        "tools_called": 0,
                        "is_voice": is_voice,
                        "context_items": len(context_parts)
                    }
                }
                
            raise e

    @staticmethod
    def _strip_for_tts(text: str) -> str:
        """Strip markdown, emojis, and special characters for clean TTS input."""
        plain = text
        plain = _MARKDOWN_BOLD_RE.sub(r'\1', plain)
        plain = _MARKDOWN_ITALIC_RE.sub(r'\1', plain)
        plain = _MARKDOWN_HEADING_RE.sub('', plain)
        plain = _MARKDOWN_CODE_RE.sub(r'\1', plain)
        plain = _MARKDOWN_LINK_RE.sub(r'\1', plain)
        plain = _EMOJI_RE.sub('', plain)
        plain = plain.replace('\n', ' ')
        plain = _WHITESPACE_MULTI_RE.sub(' ', plain)
        return plain.strip()

    @staticmethod
    async def _generate_tts_audio(text: str) -> Tuple[Optional[str], Optional[str]]:
        """Generate TTS audio for a sentence, return (base64_audio, audio_format)."""
        tts_url = os.getenv("TTS_SERVICE_URL", "http://192.168.2.88:8880")
        clean_text = MasterAgent._strip_for_tts(text)
        if not clean_text or len(clean_text) < 2:
            return None, None
        
        try:
            client = _get_tts_client()
            response = await client.post(
                f"{tts_url}/v1/audio/speech",
                json={
                    "model": "tts-1",
                    "input": clean_text,
                    "voice": "Serena",
                    "speed": 1.25,
                    "response_format": "mp3"
                },
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                audio_bytes = response.content
                audio_format = "unknown"
                if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
                    audio_format = "wav"
                elif (len(audio_bytes) >= 3 and audio_bytes[:3] == b"ID3") or (len(audio_bytes) >= 2 and audio_bytes[:2] == b"\xff\xfb"):
                    audio_format = "mp3"
                return base64.b64encode(audio_bytes).decode('ascii'), audio_format
            else:
                logger.warning(f"TTS failed ({response.status_code}): {response.text[:100]}")
                return None, None
        except Exception as e:
            logger.warning(f"TTS generation error: {e}")
            return None, None

    @staticmethod
    def _split_into_sentences(text: str) -> List[str]:
        """Split text into sentences at . ? ! boundaries."""
        import re
        # Split on sentence-ending punctuation followed by a space or end-of-string
        parts = re.split(r'(?<=[.?!])\s+', text.strip())
        return [p for p in parts if p.strip()]

    async def stream_chat(
        self,
        session_id: str,
        user_msg: str,
        history: List[Dict[str, str]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        is_voice: bool = False
    ):
        """
        Paired-Streaming SSE: buffers LLM tokens into sentences, generates TTS audio
        concurrently, and yields paired {text, audio} events in order.

        Event types:
        - {type: 'sentence', text: str, audio: str|null}  → paired text + base64 MP3
        - {type: 'actions', actions: [...]}                → tool results
        - [DONE]                                           → stream end
        
        Strategy:
        - CONVERSATION intent → stream tokens, buffer sentences, TTS each sentence
        - Search intent → direct bypass (single sentence event)
        - ACTION/UNCLEAR → non-streaming run(), split result into sentence events
        """
        
        def _safe_json(obj):
            """JSON-serialize with fallback for Pydantic models and other non-serializable types."""
            if isinstance(obj, BaseModel):
                return obj.model_dump()
            if isinstance(obj, (datetime,)):
                return obj.isoformat()
            if isinstance(obj, set):
                return list(obj)
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
        
        async def _yield_sentences_with_tts(full_text: str):
            """Split text into sentences, generate TTS for each concurrently, yield in order."""
            sentences = self._split_into_sentences(full_text)
            if not sentences:
                yield f"data: {json.dumps({'type': 'sentence', 'text': full_text, 'audio': None, 'audio_format': None})}\n\n"
                return
            
            # Fire off all TTS tasks concurrently
            tts_tasks = [asyncio.create_task(self._generate_tts_audio(s)) for s in sentences]
            
            # Yield in order as each completes (but maintain sequence)
            for i, (sentence, task) in enumerate(zip(sentences, tts_tasks)):
                try:
                    audio_b64, audio_format = await asyncio.wait_for(task, timeout=30.0)
                except Exception as e:
                    logger.warning(f"TTS task {i} failed: {e}")
                    audio_b64 = None
                    audio_format = None
                yield f"data: {json.dumps({'type': 'sentence', 'text': sentence, 'audio': audio_b64, 'audio_format': audio_format})}\n\n"

        start_time = datetime.now().timestamp()
        self.metrics["total_requests"] += 1
        if is_voice:
            self.metrics["voice_requests"] += 1
            
        deps = MasterAgentDeps(
            session_id=session_id,
            latitude=latitude,
            longitude=longitude,
            context=context or {},
            user_id=user_id,
        )
        context_parts = []
        
        # Build history context for analyzer (was missing — caused context loss)
        history_context_str = ""
        if history:
            recent_msgs = [f"{'User' if h.get('role') == 'user' else 'ZeroQ'}: {h.get('content', '')[:200]}" for h in history[-6:]]
            history_context_str = "[CONVERSATION HISTORY]\n" + "\n".join(recent_msgs)
        
        # --- FAST GREETING PREFILTER ---
        # Skip the full LLM analyzer for trivial greetings → go straight to conversation agent
        if _GREETING_RE.match(user_msg.strip()):
            logger.info(f"Greeting prefilter matched: '{user_msg.strip()[:30]}' — skipping analyzer")
            greeting_response = "Hello! I'm ZeroQ, your queue management assistant. Here's what I can do for you:\n\n1. **Register a Shop** — Set up your business on our platform\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works\n\nWhat would you like to do?"
            async for event in _yield_sentences_with_tts(greeting_response):
                yield event
            yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        analysis = await unified_query_analyzer.analyze(
            user_msg, 
            history_context_str
        )
        deps.context["last_query_analysis"] = analysis.model_dump()
        
        if analysis.context_updates.last_category:
            deps.context["last_search_category"] = analysis.context_updates.last_category
        if analysis.context_updates.last_city:
            deps.context["last_search_city"] = analysis.context_updates.last_city
            
        # Build Context Parts
        message_history = []
        if history:
            for hp in history[-5:]:
                role = hp.get("role", "user")
                if role == "user":
                    message_history.append(ModelRequest(parts=[UserPromptPart(content=hp.get("content", ""))]))
                elif role == "assistant":
                    message_history.append(ModelResponse(parts=[TextPart(content=hp.get("content", ""))]))
            
            recent_msgs = [h.get("content", "") for h in history[-3:] if h.get("role") == "user"]
            history_context_str = " | ".join(recent_msgs)
        
        if deps.latitude and deps.longitude:
            context_parts.append(f"[LOCATION: {deps.latitude}, {deps.longitude}]")
        elif context and context.get("city"):
            context_parts.append(f"[LOCATION CONTEXT: {context['city']}]")
            
        if context and context.get("active_view"):
            context_parts.append(f"[ACTIVE VIEW: {context['active_view']}]")
            
        input_method = "voice" if is_voice else "text"
        context_parts.append(f"[INPUT: {input_method}]")
        
        full_context = "\n".join(context_parts)
        full_msg = f"{full_context}\n\nUser message: {user_msg}" if full_context else user_msg
        
        # --- DIRECT SEARCH BYPASS ---
        # Only bypass when analyzer explicitly identifies a NEW search intent (ACTION).
        # If intent is CONVERSATION or UNCLEAR (e.g. user answering a follow-up question),
        # defer to the LLM — scalable across all conversational flows.
        is_search_intent = (
            analysis.intent == 'ACTION'
            and (analysis.terms or analysis.near_me or analysis.city)
        )
        
        logger.info(f"Search bypass decision (stream): intent={analysis.intent}, terms='{analysis.terms}', is_search={is_search_intent}")
        
        if is_search_intent:
            logger.info("Direct Search Bypass Triggered (Streaming)")
            final_text = await search_shops(
                RunContext(deps=deps, model=model, usage=None, prompt=""),
                category=analysis.context_updates.last_category,
                city=analysis.city,
                query=user_msg
            )
            # Send search result as paired sentence events
            async for event in _yield_sentences_with_tts(final_text):
                yield event
            yield f"data: {json.dumps({'type': 'actions', 'actions': deps.actions}, default=_safe_json)}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        intent = analysis.intent
        
        # --- CONVERSATION INTENT: Token streaming + sentence-buffered TTS ---
        if intent == 'CONVERSATION':
            logger.info("Paired streaming via conversation agent")
            try:
                self.metrics["llm_calls"] += 1
                sentence_buffer = ""
                pending_tts_tasks: List[asyncio.Task] = []
                pending_sentences: List[str] = []
                
                async with unified_query_analyzer.conversation_agent.run_stream(
                    full_msg, message_history=message_history
                ) as stream_result:
                    async for text_delta in stream_result.stream_text(delta=True):
                        if not text_delta:
                            continue
                        sentence_buffer += text_delta
                        
                        # Check for sentence boundaries in buffer
                        while True:
                            match = _SENTENCE_BOUNDARY_RE.search(sentence_buffer)
                            if not match:
                                break
                            # Extract complete sentence
                            boundary_end = match.end()
                            complete_sentence = sentence_buffer[:boundary_end].strip()
                            sentence_buffer = sentence_buffer[boundary_end:]
                            
                            if complete_sentence and len(complete_sentence) > 2:
                                # Fire TTS immediately (don't wait)
                                tts_task = asyncio.create_task(
                                    self._generate_tts_audio(complete_sentence)
                                )
                                pending_tts_tasks.append(tts_task)
                                pending_sentences.append(complete_sentence)
                
                # Handle remaining buffer as final sentence
                if sentence_buffer.strip() and len(sentence_buffer.strip()) > 2:
                    final_sentence = sentence_buffer.strip()
                    tts_task = asyncio.create_task(
                        self._generate_tts_audio(final_sentence)
                    )
                    pending_tts_tasks.append(tts_task)
                    pending_sentences.append(final_sentence)
                
                # Now yield all sentence events in order (TTS tasks were fired concurrently)
                for i, (sentence, task) in enumerate(zip(pending_sentences, pending_tts_tasks)):
                    try:
                        audio_b64, audio_format = await asyncio.wait_for(task, timeout=30.0)
                    except Exception as e:
                        logger.warning(f"TTS task {i} failed: {e}")
                        audio_b64 = None
                        audio_format = None
                    yield f"data: {json.dumps({'type': 'sentence', 'text': sentence, 'audio': audio_b64, 'audio_format': audio_format})}\n\n"
                
                yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
                yield "data: [DONE]\n\n"
                return
            except Exception as e:
                logger.warning(f"Conversation paired-stream failed ({e}), falling back")
                try:
                    fallback_text = await unified_query_analyzer.get_conversational_response(
                        user_msg, deps.context, history_context_str
                    )
                except Exception:
                    fallback_text = "Hello! I'm ZeroQ. How can I help you today?"
                async for event in _yield_sentences_with_tts(fallback_text):
                    yield event
                yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
                yield "data: [DONE]\n\n"
                return
        
        # --- ACTION / UNCLEAR INTENT: Non-streaming run(), then sentence-split ---
        logger.info(f"Non-streaming master agent run (intent={intent})")
        try:
            self.metrics["llm_calls"] += 1
            result = await asyncio.wait_for(
                self.agent.run(full_msg, message_history=message_history, deps=deps),
                timeout=300.0
            )
            response_text = result.output.response
            
            # Send as paired sentence events
            async for event in _yield_sentences_with_tts(response_text):
                yield event
            
            # Check if any actions include a form_event (e.g. start_registration)
            for action in deps.actions:
                if "form_event" in action:
                    yield f"data: {json.dumps({'type': 'form_step', **action['form_event']})}\n\n"
            
            yield f"data: {json.dumps({'type': 'actions', 'actions': deps.actions}, default=_safe_json)}\n\n"
            yield "data: [DONE]\n\n"
                
        except Exception as e:
            self.metrics["errors"] += 1
            logger.error(f"Stream MasterAgent error: {e}")
            try:
                fallback_text = await unified_query_analyzer.get_conversational_response(
                    user_msg, deps.context, history_context_str
                )
            except Exception:
                fallback_text = "I'm sorry, I had trouble processing that. Could you try again?"
            async for event in _yield_sentences_with_tts(fallback_text):
                yield event
            yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
            yield "data: [DONE]\n\n"
        
        try:
            await self.category_manager.persist_learnings()
        except Exception:
            pass
    
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