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
# Split on sentence-ending punctuation, but NOT after digit-dot (e.g. "1." "2." "3.")
_SENTENCE_BOUNDARY_RE = re.compile(r'(?<!\d[.])(?<=[.?!])\s+')
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

# Registration cancellation — used inside active-registration block (Redis state check)
_CANCEL_REGISTRATION_RE = re.compile(
    r'(?:cancel|stop|quit|abort|nevermind|never\s*mind|start\s*over)',
    re.IGNORECASE
)
_REGISTRATION_INTERRUPT_INTENTS = {'SEARCH', 'PLATFORM_INFO', 'CONVERSATION'}

_QUEUE_JOIN_REQUEST_RE = re.compile(
    r'\b(join\s+(the\s+)?queue|check\s*in|enqueue|book\s+me|add\s+me)\b',
    re.IGNORECASE,
)
_WAIT_TIME_REQUEST_RE = re.compile(
    r'\b(wait\s*time|how\s+long|eta|queue\s+status|position)\b',
    re.IGNORECASE,
)
_NAME_CAPTURE_RE = re.compile(
    r"(?:my\s+name\s+is|name\s+is|i\s+am|i'm)\s+([A-Za-z][A-Za-z\s'\-]{1,60}?)(?=\s+(?:and\s+)?phone\b|[.,;]|$)",
    re.IGNORECASE,
)
_PHONE_CAPTURE_RE = re.compile(
    r'(?:phone(?:\s+number)?\s*(?:is|:)?\s*)?([+]?\d[\d\s\-()]{6,20}\d)',
    re.IGNORECASE,
)

_TTS_TIMEOUT_SECONDS = 60.0


def _extract_customer_details_for_join(user_msg: str) -> Tuple[Optional[str], Optional[str]]:
    """Best-effort extraction for queue join details from free text."""
    name: Optional[str] = None
    phone: Optional[str] = None

    name_match = _NAME_CAPTURE_RE.search(user_msg)
    if name_match:
        name = _WHITESPACE_MULTI_RE.sub(' ', name_match.group(1)).strip(" .,")

    phone_match = _PHONE_CAPTURE_RE.search(user_msg)
    if phone_match:
        raw_phone = phone_match.group(1)
        phone = _WHITESPACE_MULTI_RE.sub(' ', raw_phone).strip()

    return name, phone


def _is_shop_queue_join_request(user_msg: str) -> bool:
    return bool(_QUEUE_JOIN_REQUEST_RE.search(user_msg))


def _is_shop_wait_request(user_msg: str) -> bool:
    return bool(_WAIT_TIME_REQUEST_RE.search(user_msg))


def _build_queue_join_form_event(shop_id: int, shop_name: str, city: Optional[str] = None, shop_type: Optional[str] = None) -> Dict[str, Any]:
    """Generate a queue_join_form SSE event for inline form rendering in frontend."""
    return {
        "type": "queue_join_form",
        "shop_id": shop_id,
        "shop_name": shop_name,
        "city": city,
        "shop_type": shop_type,
        "status": "collecting",
    }

# Shared httpx client for TTS (connection pooling)
_tts_client: Optional[httpx.AsyncClient] = None
_tts_cache: Dict[str, Tuple[str, str]] = {}
_TTS_CACHE_MAX_ITEMS = 256

def _get_tts_client() -> httpx.AsyncClient:
    global _tts_client
    if _tts_client is None or _tts_client.is_closed:
        _tts_client = httpx.AsyncClient(
            timeout=httpx.Timeout(_TTS_TIMEOUT_SECONDS, connect=10.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=3)
        )
    return _tts_client

# --- Configuration ---
ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
model_name = os.getenv("MODEL_NAME", "qwen3:14b-q4_K_M")
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
        self.local_cache = []  # List of (embedding_vector, IntentAnalysis_dict)
    
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

class IntentAnalysis(BaseModel):
    intent: str = Field(description="One of: GREETING, REGISTRATION, SEARCH, PLATFORM_INFO, CONVERSATION, UNCLEAR")
    search_terms: str = Field(default="", description="Extracted search keywords (e.g. 'barber', 'salon'). Only for SEARCH intent.")
    city: Optional[str] = Field(default=None, description="City/location for SEARCH intent.")
    near_me: bool = Field(default=False, description="True if user wants nearby search.")
    specificity: str = Field(default="SPECIFIC", description="VAGUE or SPECIFIC — for SEARCH intent only.")
    platform_target: Optional[str] = Field(default=None, description="pricing, features, faq, or testimonials — for PLATFORM_INFO intent.")
    registration_type: Optional[str] = Field(default=None, description="shop_owner, customer, or null — for REGISTRATION intent.")
    context_updates: ContextUpdates


class SearchRecoveryAnalysis(BaseModel):
    is_search: bool = Field(description="True if the message is a request to find a service/shop/business.")
    search_terms: str = Field(default="", description="Service/category terms such as 'salon' or 'barber'.")
    city: Optional[str] = Field(default=None, description="City/location if explicitly mentioned.")
    near_me: bool = Field(default=False, description="True if user asks for nearby/near me.")

class UnifiedQueryAnalyzer:
    """Single-pass Pydantic LLM extractor. Replaces IntentRouter, QueryProcessor, ContextExtractor."""
    
    def __init__(self):
        self.analyzer_agent = Agent(
            model,
            output_type=IntentAnalysis,
            system_prompt="""You are a single-pass intent classifier for ZeroQwait, a queue management platform.
Classify the user's message into exactly ONE intent and extract relevant fields.

## Intents

GREETING — Simple greetings, thanks, goodbyes.
  Examples: "hi", "hello", "hey there", "thanks", "bye", "good morning"

REGISTRATION — User wants to sign up, register, create account, list their business.
  Examples: "I want to register", "sign up", "create an account", "set up my shop", "get started", "list my business"
  - registration_type: "shop_owner" if mentions shop/business/store/owner, "customer" if mentions customer/join, null if unclear.

SEARCH — User wants to find shops, businesses, or services.
  Examples: "find barbers near me", "any salons in Toronto?", "search shops", "look for a clinic"
    IMPORTANT: Treat short/shorthand requests as SEARCH even without explicit verbs like "find" or "search".
    Examples: "salon at oshawa", "barber oshawa", "clinic in scarborough", "dentist near toronto", "spa downtown".
    If a service/category and location are present, this is SEARCH with specificity=SPECIFIC.
  - specificity=VAGUE if NO service type is mentioned (e.g. "search shops", "find stores", "show me businesses")
  - specificity=SPECIFIC if a service type, category, or query is given (e.g. "find barbers", "salons near me")
  - search_terms: extract core service type ONLY for SPECIFIC searches. Empty string otherwise.
  - city: only if a city is explicitly named in a search request.
  - near_me: true only if user says "near me", "nearby", "around here".

PLATFORM_INFO — User asks about ZeroQwait itself: pricing, features, FAQ, testimonials, products.
  Examples: "what are your prices?", "tell me about features", "how does it work?", "show me testimonials", "I want to know about the products"
  - platform_target: "pricing" for price/cost/plan/subscription/product, "features" for features/capabilities, "faq" for FAQ/help, "testimonials" for reviews/testimonials.
  - CRITICAL: "products", "pricing", "how much does it cost" → PLATFORM_INFO, NOT SEARCH.

CONVERSATION — General conversation, answering a question ZeroQ asked, follow-up discussion.
  If conversation history shows ZeroQ asked a question about registration details (e.g. "Could you share your shop name?", "What's your email?"), the current message is an ANSWER → CONVERSATION.
  Example:
    ZeroQ: "Could you share: 1. Shop name 2. Shop type 3. Address"
    User: "tutubaba is the shopname, shoptype is spa, address is 2570 bromus path, oshawa"
    → intent=CONVERSATION (user is answering registration questions, NOT searching)

  EXCEPTION — Search follow-ups are SEARCH, not CONVERSATION:
  If ZeroQ asked "What type of service are you looking for?" or "What city?" and the user replies with a service type or location, this is a SEARCH with specificity=SPECIFIC.
  Examples:
    ZeroQ: "What type of service are you looking for?"
    User: "auto shop" → intent=SEARCH, specificity=SPECIFIC, search_terms="auto shop"
    User: "barber in Toronto" → intent=SEARCH, specificity=SPECIFIC, search_terms="barber", city="Toronto"
    User: "salon" → intent=SEARCH, specificity=SPECIFIC, search_terms="salon"
    User: "salon at oshawa" → intent=SEARCH, specificity=SPECIFIC, search_terms="salon", city="Oshawa"

UNCLEAR — Ambiguous message that doesn't clearly fit other intents.
  Examples: "ok", "maybe", "hmm", single characters, random text

Do NOT classify as UNCLEAR if the message contains a recognizable service/business category and/or location request.

Decision priority:
1) If the message plausibly asks to find a service/shop (even tersely), choose SEARCH.
2) Use UNCLEAR only for filler/acknowledgement text with no actionable search meaning.
3) Between SEARCH and UNCLEAR, prefer SEARCH.

## Field Rules
- search_terms, city, near_me, specificity: only meaningful for SEARCH intent. Use defaults for other intents.
- platform_target: only meaningful for PLATFORM_INFO intent.
- registration_type: only meaningful for REGISTRATION intent.
- For non-applicable intents, use default values (empty string, null, false).
- context_updates.last_category / last_city: track latest search category and city across conversation turns.
""",
            model_settings={'temperature': 0.0, 'max_tokens': 250}
        )

        self.search_recovery_agent = Agent(
            model,
            output_type=SearchRecoveryAnalysis,
            system_prompt="""You are a search-intent disambiguator for ZeroQwait.

Your task: decide whether the user message is actually a request to find a service/shop/business,
especially when phrasing is short or telegraphic.

Treat these as SEARCH:
- "salon at oshawa"
- "barber toronto"
- "dentist in mississauga"
- "spa near me"
- "clinic scarborough"

If a message contains a recognizable service/category term (such as salon, barber, spa, clinic, dentist, auto shop, pharmacy, restaurant), it should be treated as SEARCH unless the user is clearly discussing registration or platform pricing/features.

If it is search:
- is_search=true
- extract search_terms (service/category) when present
- extract city when present
- near_me=true only for nearby/near me style wording

If it is not search, set is_search=false and leave other fields empty/default.
""",
            model_settings={'temperature': 0.0, 'max_tokens': 120}
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

    # Compiled regex patterns for fast intent detection (skip LLM for obvious intents)
    _GREETING_RE = re.compile(
        r'^(hi|hello|hey|howdy|greetings|good\s*(morning|afternoon|evening|day)|'
        r'thanks|thank\s*you|bye|goodbye|see\s*you|take\s*care|yo|sup|hiya|hola|'
        r'what\'?s\s*up|whats\s*up)[!?.,\s]*$',
        re.IGNORECASE
    )
    _PLATFORM_PRICING_RE = re.compile(
        r'\b(pric(e|es|ing)|cost|how\s*much|subscription|plan[s]?|products?)\b',
        re.IGNORECASE
    )
    _PLATFORM_FEATURES_RE = re.compile(
        r'\b(features?|capabilities|what\s*(can|do)\s*(you|it)\s*(do|offer))\b',
        re.IGNORECASE
    )
    _PLATFORM_FAQ_RE = re.compile(
        r'\b(faq|frequently\s*asked|help\s*page|how\s*does\s*it\s*work)\b',
        re.IGNORECASE
    )
    _PLATFORM_TESTIMONIALS_RE = re.compile(
        r'\b(testimonials?|reviews?|what\s*(people|users|customers)\s*say)\b',
        re.IGNORECASE
    )
    _REGISTRATION_RE = re.compile(
        r'\b(register|sign\s*up|create\s*(an?\s*)?account|get\s*started|'
        r'list\s*my\s*business|set\s*up\s*(my\s*)?(shop|business|store))\b',
        re.IGNORECASE
    )
    _CITY_HINT_RE = re.compile(r'\b(?:in|at|near)\s+([A-Za-z][A-Za-z\s\-]{1,40})\b', re.IGNORECASE)
    _SERVICE_FALLBACK_RE = re.compile(
        r'\b(barber|barbers|barbershop|salon|spa|clinic|hospital|dentist|dental|'
        r'auto\s*shop|mechanic|car\s*wash|gym|fitness|restaurant|cafe|pharmacy)\b',
        re.IGNORECASE,
    )
    def _fast_intent_check(self, user_msg: str) -> Optional[IntentAnalysis]:
        """Regex-based fast path for obvious intents. Returns None if unsure (falls through to LLM)."""
        msg = user_msg.strip()
        lower_msg = msg.lower()
        defaults = dict(search_terms="", city=None, near_me=False, specificity="SPECIFIC",
                        platform_target=None, registration_type=None,
                        context_updates=ContextUpdates(last_category=None, last_city=None))

        # Greeting — only match short messages (< 30 chars) to avoid false positives
        if len(msg) < 30 and self._GREETING_RE.match(msg):
            return IntentAnalysis(intent='GREETING', **defaults)

        # Platform info
        for regex, target in [
            (self._PLATFORM_PRICING_RE, 'pricing'),
            (self._PLATFORM_FEATURES_RE, 'features'),
            (self._PLATFORM_FAQ_RE, 'faq'),
            (self._PLATFORM_TESTIMONIALS_RE, 'testimonials'),
        ]:
            if regex.search(msg):
                return IntentAnalysis(intent='PLATFORM_INFO', platform_target=target,
                                     search_terms="", city=None, near_me=False, specificity="SPECIFIC",
                                     registration_type=None,
                                     context_updates=ContextUpdates(last_category=None, last_city=None))

        # Registration
        if self._REGISTRATION_RE.search(msg):
            reg_type = None
            if re.search(r'\b(shop|business|store|owner)\b', msg, re.IGNORECASE):
                reg_type = 'shop_owner'
            elif re.search(r'\b(customer|join)\b', msg, re.IGNORECASE):
                reg_type = 'customer'
            return IntentAnalysis(intent='REGISTRATION', registration_type=reg_type,
                                 search_terms="", city=None, near_me=False, specificity="SPECIFIC",
                                 platform_target=None,
                                 context_updates=ContextUpdates(last_category=None, last_city=None))

        return None  # Not obvious — fall through to LLM

    async def analyze(self, user_msg: str, history_context: str = "") -> IntentAnalysis:
        # Fast regex prefilter — skip 10-13s LLM call for obvious intents
        fast_result = self._fast_intent_check(user_msg)
        if fast_result:
            logger.info(f"Fast intent match: {fast_result.intent} (skipped LLM)")
            return fast_result

        # Query-only semantic cache can be misleading for contextual follow-ups,
        # so use it only when there is no conversation context.
        use_query_cache = not bool((history_context or "").strip())
        if use_query_cache:
            cached_dict = semantic_cache.get(user_msg)
            if cached_dict and cached_dict.get("intent") != "UNCLEAR":
                return IntentAnalysis(**cached_dict)
            
        full_prompt = f"{history_context}\n\nCurrent message: {user_msg}" if history_context else user_msg
        
        try:
            result = await self.analyzer_agent.run(full_prompt)
            analysis = result.output

            if analysis.intent == "UNCLEAR":
                recovery_result = await self.search_recovery_agent.run(full_prompt)
                recovered = recovery_result.output
                recovered_terms = (recovered.search_terms or "").strip().lower()
                recovered_city = (recovered.city or "").strip() or None

                # Dynamic category fallback from DB-driven category manager for terse queries.
                category_fallback = await category_manager.detect_category(user_msg)

                if recovered.is_search or category_fallback:
                    final_terms = recovered_terms or (category_fallback or "")
                    return IntentAnalysis(
                        intent="SEARCH",
                        search_terms=final_terms,
                        city=recovered_city,
                        near_me=bool(recovered.near_me),
                        specificity="SPECIFIC" if final_terms else "VAGUE",
                        platform_target=None,
                        registration_type=None,
                        context_updates=ContextUpdates(
                            last_category=final_terms or None,
                            last_city=recovered_city,
                        ),
                    )
            
            # Store only stable, non-ambiguous query-only classifications.
            if use_query_cache and analysis.intent != "UNCLEAR":
                semantic_cache.set(user_msg, analysis.model_dump())
            return analysis
        except Exception as e:
            logger.error(f"Unified analyzer failed: {e}")
            # LLM unavailable fallback: infer SEARCH from dynamic categories + basic location hints.
            fallback_category = await category_manager.detect_category(user_msg)
            if not fallback_category:
                service_match = self._SERVICE_FALLBACK_RE.search(user_msg or "")
                if service_match:
                    fallback_category = service_match.group(1).strip().lower()
                    if fallback_category == "barbers":
                        fallback_category = "barber"
                    elif fallback_category == "barbershop":
                        fallback_category = "barber"
                    elif fallback_category == "dental":
                        fallback_category = "dentist"
            city_match = self._CITY_HINT_RE.search(user_msg or "")
            fallback_city = city_match.group(1).strip() if city_match else None
            fallback_near_me = "near me" in user_msg.lower() or "nearby" in user_msg.lower()

            if fallback_category or fallback_city or fallback_near_me:
                return IntentAnalysis(
                    intent='SEARCH',
                    search_terms=fallback_category or "",
                    city=fallback_city,
                    near_me=fallback_near_me,
                    specificity="SPECIFIC" if fallback_category else "VAGUE",
                    platform_target=None,
                    registration_type=None,
                    context_updates=ContextUpdates(
                        last_category=fallback_category,
                        last_city=fallback_city,
                    )
                )

            # Last resort fallback
            return IntentAnalysis(
                intent='UNCLEAR',
                search_terms="",
                city=None,
                near_me=fallback_near_me,
                specificity="SPECIFIC",
                platform_target=None,
                registration_type=None,
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
            clean_terms = cached_analysis.get("search_terms") or None
            user_wants_nearby = cached_analysis.get("near_me", False)
            if not extracted_city and cached_analysis.get("city"):
                extracted_city = cached_analysis["city"]
        elif original_query:
            # Fallback: run analyzer only if no cached result
            analysis = await unified_query_analyzer.analyze(original_query)
            clean_terms = analysis.search_terms if analysis.search_terms else None
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
            
        if any(x in check_term for x in ['pricing', 'cost', 'plan', 'price', 'product', 'subscription', 'how much']):
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

            # Active registration state gate (same policy as streaming path).
            from registration_agent import registration_agent as reg_agent
            precomputed_analysis = None
            active_reg = reg_agent.get_session(session_id)
            if active_reg and not active_reg.get("completed"):
                current_step = active_reg.get("step", "unknown")
                if _CANCEL_REGISTRATION_RE.search(user_msg.strip()):
                    reg_agent._clear_session(session_id)
                    cancel_msg = "Registration cancelled. How else can I help you?\n\n1. **Register a Shop** — Set up your business on our platform\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works"
                    processing_time = (datetime.now().timestamp() - start_time) * 1000
                    return {
                        "response": cancel_msg,
                        "actions": [],
                        "agent_name": "ZeroQ",
                        "processing_time_ms": processing_time,
                        "metrics": {
                            "tools_called": 0,
                            "is_voice": is_voice,
                            "context_items": 0
                        }
                    }

                active_analysis = await unified_query_analyzer.analyze(user_msg, history_context_str)
                if active_analysis.intent in _REGISTRATION_INTERRUPT_INTENTS:
                    reg_agent._clear_session(session_id)
                    deps.context["registration_interrupted"] = True
                    deps.context["registration_interrupted_step"] = current_step
                    precomputed_analysis = active_analysis
                    logger.info(
                        f"Active registration interrupted at step={current_step}; switching to intent={active_analysis.intent}"
                    )
                else:
                    reminder_msg = (
                        f"Continuing your registration (step: **{current_step}**). "
                        "Please complete the form below, or say **cancel registration** to start over."
                    )
                    form_event = reg_agent._build_form_event(active_reg)
                    processing_time = (datetime.now().timestamp() - start_time) * 1000
                    return {
                        "response": reminder_msg,
                        "actions": [
                            {
                                "tool": "start_registration",
                                "result": {
                                    "account_type": active_reg.get("account_type", "unknown")
                                },
                                "form_event": form_event,
                                "timestamp": datetime.now().isoformat()
                            }
                        ],
                        "agent_name": "ZeroQ",
                        "processing_time_ms": processing_time,
                        "metrics": {
                            "tools_called": 1,
                            "is_voice": is_voice,
                            "context_items": 0
                        }
                    }
            
            # --- Pydantic AI History Mapping ---
            from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart
            message_history = []
            for msg in conversation_history:
                if msg.get('role') == 'user':
                    message_history.append(ModelRequest(parts=[UserPromptPart(content=msg.get('content', ''))]))
                elif msg.get('role') == 'assistant':
                    message_history.append(ModelResponse(parts=[TextPart(content=msg.get('content', ''))]))
            
            # --- Single Pass Unified Extraction ---
            analysis = precomputed_analysis or await unified_query_analyzer.analyze(user_msg, history_context_str)
            intent = analysis.intent
            
            # Keep Session Context Live
            if analysis.context_updates.last_category:
                deps.context["last_search_category"] = analysis.context_updates.last_category
            if analysis.context_updates.last_city:
                deps.context["last_search_city"] = analysis.context_updates.last_city
                
            logger.info(f"Analyzer: intent={intent}, search_terms='{analysis.search_terms}', city={analysis.city}, near_me={analysis.near_me}, platform_target={analysis.platform_target}, specificity={analysis.specificity}")
            
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
            
            # --- INTENT-BASED ROUTING (non-streaming) ---
            intent = analysis.intent
            logger.info(f"Intent routing (non-stream): intent={intent}, platform_target={analysis.platform_target}, reg_type={analysis.registration_type}")

            shop_id = (context or {}).get("shop_id")
            shop_name = (context or {}).get("shop_name", "this shop")
            has_join_signal = _is_shop_queue_join_request(user_msg)
            has_wait_signal = _is_shop_wait_request(user_msg)
            extracted_name, extracted_phone = _extract_customer_details_for_join(user_msg)

            # Shop landing override: avoid generic location/category search when shop is already known.
            if shop_id and (has_join_signal or has_wait_signal or extracted_name):
                if has_wait_signal:
                    final_text = await get_wait_time(
                        RunContext(deps=deps, model=model, usage=None, prompt=""),
                        shop_id=int(shop_id),
                    )
                elif not extracted_name:
                    # Emit inline queue join form instead of text prompt
                    final_text = f"You're joining the queue for **{shop_name}**. Please provide your details below:"
                    
                    # Build and append queue_join_form event to actions
                    city = (context or {}).get("city")
                    shop_type_val = (context or {}).get("shop_type")
                    form_event = _build_queue_join_form_event(
                        shop_id=int(shop_id),
                        shop_name=shop_name,
                        city=city,
                        shop_type=shop_type_val
                    )
                    deps.actions.append({
                        "tool": "queue_join_form",
                        "form_event": form_event,
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    final_text = await join_queue(
                        RunContext(deps=deps, model=model, usage=None, prompt=""),
                        shop_id=int(shop_id),
                        customer_name=extracted_name,
                        phone=extracted_phone,
                    )
            
            elif intent == 'GREETING':
                final_text = "Hello! I'm ZeroQ, your queue management assistant. Here's what I can do for you:\n\n1. **Register a Shop** — Set up your business on our platform\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works\n\nWhat would you like to do?"
            
            elif intent == 'REGISTRATION':
                final_text = await start_registration(
                    RunContext(deps=deps, model=model, usage=None, prompt=""),
                    account_type=analysis.registration_type
                )
            
            elif intent == 'SEARCH':
                if shop_id:
                    if _is_shop_wait_request(user_msg):
                        final_text = await get_wait_time(
                            RunContext(deps=deps, model=model, usage=None, prompt=""),
                            shop_id=int(shop_id),
                        )
                    elif _is_shop_queue_join_request(user_msg):
                        customer_name, customer_phone = _extract_customer_details_for_join(user_msg)
                        if not customer_name:
                            # Emit inline queue join form instead of text prompt
                            final_text = f"You're joining the queue for **{shop_name}**. Please provide your details below:"
                            
                            # Build and append queue_join_form event to actions
                            city = (context or {}).get("city")
                            shop_type_val = (context or {}).get("shop_type")
                            form_event = _build_queue_join_form_event(
                                shop_id=int(shop_id),
                                shop_name=shop_name,
                                city=city,
                                shop_type=shop_type_val
                            )
                            deps.actions.append({
                                "tool": "queue_join_form",
                                "form_event": form_event,
                                "timestamp": datetime.now().isoformat()
                            })
                        else:
                            final_text = await join_queue(
                                RunContext(deps=deps, model=model, usage=None, prompt=""),
                                shop_id=int(shop_id),
                                customer_name=customer_name,
                                phone=customer_phone,
                            )
                    else:
                        final_text = (
                            f"I can help you with **{shop_name}** right away. "
                            "If you want to join the queue, share your **name** and **phone number**. "
                            "Or ask for **wait time**."
                        )
                elif analysis.specificity == 'VAGUE':
                    final_text = "Sure! What type of service are you looking for? For example: barber, salon, clinic, auto shop. And if you share your city or say 'near me', I'll find the closest options!"
                else:
                    logger.info("Direct Search (intent-based, non-stream)")
                    final_text = await search_shops(
                        RunContext(deps=deps, model=model, usage=None, prompt=""),
                        category=analysis.context_updates.last_category,
                        city=analysis.city,
                        query=user_msg
                    )
            
            elif intent == 'PLATFORM_INFO':
                # Normalize LLM output variations to expected keys
                _target_aliases = {'product': 'pricing', 'products': 'pricing', 'price': 'pricing', 'plan': 'pricing', 'plans': 'pricing', 'cost': 'pricing', 'subscription': 'pricing', 'feature': 'features', 'review': 'testimonials', 'reviews': 'testimonials', 'testimonial': 'testimonials', 'help': 'faq'}
                raw_target = analysis.platform_target or 'pricing'
                target = _target_aliases.get(raw_target, raw_target)
                responses = {
                    'pricing': "Here's our pricing! We offer three plans: Free ($0/mo), Premium ($29/mo), and Enterprise (custom).",
                    'features': "Here are our features! Real-time queue management, AI wait times, SMS, analytics, and more.",
                    'faq': "Here are our frequently asked questions!",
                    'testimonials': "Here's what our users are saying!"
                }
                final_text = responses.get(target, "ZeroQwait is a universal queue management platform. Check out our pricing and features!")
                if target not in responses:
                    target = 'pricing'
                deps.actions.append({'tool': 'navigate_to_page_section', 'result': {'target': target}, 'timestamp': datetime.now().isoformat()})
            
            elif intent == 'CONVERSATION':
                final_text = await unified_query_analyzer.get_conversational_response(user_msg, deps.context, history_context_str)
            
            elif intent == 'UNCLEAR':
                final_text = "I'm not quite sure what you're looking for. Could you tell me more? I can help you:\n\n1. **Register a Shop** — Set up your business\n2. **Search for Shops** — Find services nearby\n3. **Ask about our Products** — Pricing, features, and more"
            
            else:
                # Fallback to master agent LLM
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

        # Fast in-memory cache to avoid regenerating common repeated prompts.
        cache_key = hashlib.sha256(clean_text.encode('utf-8')).hexdigest()
        cached = _tts_cache.get(cache_key)
        if cached:
            return cached
        
        try:
            client = _get_tts_client()
            response = await client.post(
                f"{tts_url}/v1/audio/speech",
                json={
                    "model": "tts-1-en",
                    "input": clean_text,
                    "voice": "Vivian",
                    "speed": 1.0,
                    "language": "English",
                    "instruct": "Speak clearly and naturally with a warm, confident North American English accent. Keep a steady, professional tone and consistent pacing. Enunciate each word precisely.",
                    "response_format": "wav"
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
                audio_b64 = base64.b64encode(audio_bytes).decode('ascii')
                _tts_cache[cache_key] = (audio_b64, audio_format)
                if len(_tts_cache) > _TTS_CACHE_MAX_ITEMS:
                    # Drop oldest inserted key (dict is insertion-ordered in Python 3.9+).
                    oldest_key = next(iter(_tts_cache))
                    _tts_cache.pop(oldest_key, None)
                return audio_b64, audio_format
            else:
                logger.warning(f"TTS failed ({response.status_code}): {response.text[:100]}")
                return None, None
        except Exception as e:
            logger.warning(f"TTS generation error: {e}")
            return None, None

    @staticmethod
    def _split_into_sentences(text: str) -> List[str]:
        """Split text into display-ready segments for paired text+TTS delivery.
        
        Preserves markdown formatting — TTS stripping happens in _generate_tts_audio.
        Splits on paragraph boundaries first, then sentence boundaries within paragraphs.
        """
        import re
        stripped = text.strip()
        if not stripped:
            return []
        
        # 1. Split on paragraph breaks (double newline) — these are natural boundaries
        paragraphs = re.split(r'\n{2,}', stripped)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # 2. Within each paragraph, apply sentence splitting
        #    But skip sentence-splitting for numbered/bulleted lists
        segments = []
        for para in paragraphs:
            # If paragraph looks like a list (starts with number or bullet), keep it whole
            if re.match(r'^[\d]+[.)]\s|^[-*•]\s', para):
                segments.append(para)
                continue
            
            # Split on sentence-ending punctuation, but NOT after digit-dot (e.g. "1." "2.")
            parts = re.split(r'(?<!\d[.])(?<=[.?!])\s+', para)
            parts = [p for p in parts if p.strip()]
            
            # Merge tiny fragments (< 30 chars) with neighbors
            merged = []
            for s in parts:
                if merged and len(s) < 30:
                    merged[-1] = merged[-1] + " " + s
                else:
                    merged.append(s)
            if len(merged) > 1 and len(merged[0]) < 30:
                merged[1] = merged[0] + " " + merged[1]
                merged = merged[1:]
            segments.extend(merged)
        
        # 3. Sub-split very long segments (> 200 chars) at clause boundaries
        result = []
        for s in segments:
            # Use plain-text length for threshold (markdown adds chars)
            plain_len = len(re.sub(r'\*\*(.+?)\*\*', r'\1', s))
            if plain_len <= 200:
                result.append(s)
            else:
                chunks = re.split(r'(?<=[,;:])\s+', s)
                buf = ""
                for chunk in chunks:
                    if buf and len(buf) + len(chunk) + 1 > 150 and len(buf) >= 40:
                        result.append(buf)
                        buf = chunk
                    else:
                        buf = f"{buf} {chunk}" if buf else chunk
                if buf:
                    result.append(buf)
        return result

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
            """Split text into sentences, generate TTS one-at-a-time for progressive delivery.
            In chat mode (is_voice=False), skip TTS entirely for instant response."""
            sentences = self._split_into_sentences(full_text)
            if not sentences:
                yield f"data: {json.dumps({'type': 'sentence', 'text': full_text, 'audio': None, 'audio_format': None})}\n\n"
                return
            
            if not is_voice:
                # Chat mode: yield text immediately, no TTS calls
                for sentence in sentences:
                    yield f"data: {json.dumps({'type': 'sentence', 'text': sentence, 'audio': None, 'audio_format': None})}\n\n"
                return
            
            # Voice mode: pipeline — start next TTS while yielding current sentence
            next_task = asyncio.create_task(self._generate_tts_audio(sentences[0]))
            for i, sentence in enumerate(sentences):
                task = next_task
                # Pre-fire next sentence's TTS while we await current
                if i + 1 < len(sentences):
                    next_task = asyncio.create_task(self._generate_tts_audio(sentences[i + 1]))
                try:
                    audio_b64, audio_format = await asyncio.wait_for(task, timeout=_TTS_TIMEOUT_SECONDS)
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
        
        # --- ACTIVE REGISTRATION CHECK ---
        # If a registration session is active, remind user to complete the form
        # (prevents greeting prefilter from resetting mid-registration)
        from registration_agent import registration_agent as reg_agent
        active_reg = reg_agent.get_session(session_id)
        precomputed_analysis = None
        if active_reg and not active_reg.get("completed"):
            current_step = active_reg.get("step", "unknown")
            # Check if user wants to cancel
            if _CANCEL_REGISTRATION_RE.search(user_msg.strip()):
                reg_agent._clear_session(session_id)
                logger.info(f"Registration cancelled by user at step={current_step}")
                cancel_msg = "Registration cancelled. How else can I help you?\n\n1. **Register a Shop** — Set up your business on our platform\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works"
                async for event in _yield_sentences_with_tts(cancel_msg):
                    yield event
                yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # If user clearly asks for a non-registration task, switch context instead of forcing form continuation.
            active_analysis = await unified_query_analyzer.analyze(user_msg, history_context_str)
            if active_analysis.intent in _REGISTRATION_INTERRUPT_INTENTS:
                reg_agent._clear_session(session_id)
                logger.info(
                    f"Active registration interrupted at step={current_step}; switching to intent={active_analysis.intent}"
                )
                deps.context["registration_interrupted"] = True
                deps.context["registration_interrupted_step"] = current_step
                precomputed_analysis = active_analysis
            else:
                logger.info(f"Active registration session found at step={current_step}, reminding user")
                reminder_msg = f"Continuing your registration (step: **{current_step}**). Please complete the form below, or say **cancel registration** to start over."
                async for event in _yield_sentences_with_tts(reminder_msg):
                    yield event
                # Re-emit form_step so frontend can render the form again (e.g. after page refresh)
                form_event = reg_agent._build_form_event(active_reg)
                yield f"data: {json.dumps(form_event)}\n\n"
                yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
                yield "data: [DONE]\n\n"
                return
        
        # --- LLM INTENT CLASSIFICATION ---
        analysis = precomputed_analysis or await unified_query_analyzer.analyze(
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
        
        # --- PRE-ANALYZER SHOP QUEUE OVERRIDE ---
        # Check for shop context + queue join signals BEFORE calling expensive analyzer
        shop_id = (context or {}).get("shop_id")
        shop_name = (context or {}).get("shop_name", "this shop")
        has_join_signal = _is_shop_queue_join_request(user_msg)
        has_wait_signal = _is_shop_wait_request(user_msg)
        extracted_name, extracted_phone = _extract_customer_details_for_join(user_msg)

        if shop_id and (has_join_signal or has_wait_signal or extracted_name):
            if has_wait_signal:
                final_text = await get_wait_time(
                    RunContext(deps=deps, model=model, usage=None, prompt=""),
                    shop_id=int(shop_id),
                )
                async for event in _yield_sentences_with_tts(final_text):
                    yield event
                yield f"data: {json.dumps({'type': 'actions', 'actions': deps.actions}, default=_safe_json)}\n\n"
                yield "data: [DONE]\n\n"
                return
            elif not extracted_name:
                # Emit inline queue join form instead of text prompt
                intro_text = f"You're joining the queue for **{shop_name}**. Please provide your details below:"
                async for event in _yield_sentences_with_tts(intro_text):
                    yield event
                
                # Build and emit queue_join_form event
                city = (context or {}).get("city")
                shop_type_val = (context or {}).get("shop_type")
                form_event = _build_queue_join_form_event(
                    shop_id=int(shop_id),
                    shop_name=shop_name,
                    city=city,
                    shop_type=shop_type_val
                )
                yield f"data: {json.dumps(form_event)}\n\n"
                yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
                yield "data: [DONE]\n\n"
                return
            else:
                final_text = await join_queue(
                    RunContext(deps=deps, model=model, usage=None, prompt=""),
                    shop_id=int(shop_id),
                    customer_name=extracted_name,
                    phone=extracted_phone,
                )
                async for event in _yield_sentences_with_tts(final_text):
                    yield event
                yield f"data: {json.dumps({'type': 'actions', 'actions': deps.actions}, default=_safe_json)}\n\n"
                yield "data: [DONE]\n\n"
                return
        
        # --- INTENT-BASED ROUTING ---
        intent = analysis.intent
        logger.info(f"Intent routing (stream): intent={intent}, search_terms='{analysis.search_terms}', city={analysis.city}")
        
        # GREETING
        if intent == 'GREETING':
            greeting_response = "Hello! I'm ZeroQ, your queue management assistant. Here's what I can do for you:\n\n1. **Register a Shop** — Set up your business on our platform\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works\n\nWhat would you like to do?"
            async for event in _yield_sentences_with_tts(greeting_response):
                yield event
            yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        # REGISTRATION
        if intent == 'REGISTRATION':
            account_type = analysis.registration_type
            logger.info(f"Registration intent (stream): account_type={account_type}")
            form_event = reg_agent.start(session_id=session_id, account_type=account_type)
            if account_type == "shop_owner":
                intro_text = "Let's get your business registered! I'll walk you through it step by step."
            elif account_type == "customer":
                intro_text = "Let's create your account! I'll guide you through it."
            else:
                intro_text = "Let's get you registered! First, are you a shop owner or a customer?"
            async for event in _yield_sentences_with_tts(intro_text):
                yield event
            yield f"data: {json.dumps(form_event)}\n\n"
            yield f"data: {json.dumps({'type': 'actions', 'actions': [{'tool': 'start_registration', 'result': {'account_type': account_type or 'unknown'}}]})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        # SEARCH
        if intent == 'SEARCH':
            if shop_id:
                if _is_shop_wait_request(user_msg):
                    final_text = await get_wait_time(
                        RunContext(deps=deps, model=model, usage=None, prompt=""),
                        shop_id=int(shop_id),
                    )
                elif _is_shop_queue_join_request(user_msg):
                    customer_name, customer_phone = _extract_customer_details_for_join(user_msg)
                    if not customer_name:
                        final_text = (
                            f"You're joining the queue for **{shop_name}**. "
                            "Please share your **name** and **phone number** (and service if you want)."
                        )
                    else:
                        final_text = await join_queue(
                            RunContext(deps=deps, model=model, usage=None, prompt=""),
                            shop_id=int(shop_id),
                            customer_name=customer_name,
                            phone=customer_phone,
                        )
                else:
                    final_text = (
                        f"I can help you with **{shop_name}** right away. "
                        "If you want to join the queue, share your **name** and **phone number**. "
                        "Or ask for **wait time**."
                    )

                async for event in _yield_sentences_with_tts(final_text):
                    yield event
                yield f"data: {json.dumps({'type': 'actions', 'actions': deps.actions}, default=_safe_json)}\n\n"
                yield "data: [DONE]\n\n"
                return

            if analysis.specificity == 'VAGUE':
                logger.info("Vague search — asking for details")
                prompt_text = "Sure! I can help you find services nearby. What type of service are you looking for? For example: *barber*, *salon*, *clinic*, *auto shop*, etc. And if you share your city or say **near me**, I'll find the closest options!"
                async for event in _yield_sentences_with_tts(prompt_text):
                    yield event
                yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
                yield "data: [DONE]\n\n"
                return
            else:
                logger.info("Direct Search (intent-based, stream)")
                final_text = await search_shops(
                    RunContext(deps=deps, model=model, usage=None, prompt=""),
                    category=analysis.context_updates.last_category,
                    city=analysis.city,
                    query=user_msg
                )
                async for event in _yield_sentences_with_tts(final_text):
                    yield event
                yield f"data: {json.dumps({'type': 'actions', 'actions': deps.actions}, default=_safe_json)}\n\n"
                yield "data: [DONE]\n\n"
                return
        
        # PLATFORM_INFO
        if intent == 'PLATFORM_INFO':
            # Normalize LLM output variations to expected keys
            _target_aliases = {'product': 'pricing', 'products': 'pricing', 'price': 'pricing', 'plan': 'pricing', 'plans': 'pricing', 'cost': 'pricing', 'subscription': 'pricing', 'feature': 'features', 'review': 'testimonials', 'reviews': 'testimonials', 'testimonial': 'testimonials', 'help': 'faq'}
            raw_target = analysis.platform_target or 'pricing'
            target = _target_aliases.get(raw_target, raw_target)
            logger.info(f"Platform info intent (stream): raw={raw_target}, target={target}")
            responses = {
                'pricing': "Here's our pricing! We offer three plans: **Free** ($0/mo) for basic queue management, **Premium** ($29/mo) with analytics and SMS notifications, and **Enterprise** (custom pricing) for multi-location businesses. Take a look below!",
                'features': "Here are our features! ZeroQwait offers real-time queue management, AI-powered wait time estimates, SMS notifications, analytics dashboards, and more. Check them out below!",
                'faq': "Here are our frequently asked questions! Take a look below for answers to common questions about ZeroQwait.",
                'testimonials': "Here's what our users are saying! Check out the testimonials below."
            }
            response_text = responses.get(target, "Great question! ZeroQwait is a universal queue management platform. Check out our pricing and features below!")
            if target not in responses:
                target = 'pricing'
            async for event in _yield_sentences_with_tts(response_text):
                yield event
            action = {'tool': 'navigate_to_page_section', 'result': {'target': target}, 'timestamp': datetime.now().isoformat()}
            yield f"data: {json.dumps({'type': 'actions', 'actions': [action]}, default=_safe_json)}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        # CONVERSATION — Token streaming + sentence-buffered TTS
        if intent == 'CONVERSATION':
            logger.info("Paired streaming via conversation agent")
            try:
                self.metrics["llm_calls"] += 1
                sentence_buffer = ""
                voice_chunk_buffer = ""
                voice_chunks_emitted = 0
                # Voice mode: pipeline TTS concurrently with LLM streaming
                pending_voice: List[Tuple[str, asyncio.Task]] = []
                voice_yield_index = 0
                
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
                            boundary_end = match.end()
                            complete_sentence = sentence_buffer[:boundary_end].strip()
                            sentence_buffer = sentence_buffer[boundary_end:]
                            
                            if complete_sentence and len(complete_sentence) > 2:
                                if is_voice:
                                    # First chunk streams quickly, then aggregate to reduce
                                    # per-sentence voice drift and TTS round trips.
                                    if voice_chunks_emitted == 0:
                                        chunk = complete_sentence
                                        tts_task = asyncio.create_task(
                                            self._generate_tts_audio(chunk)
                                        )
                                        pending_voice.append((chunk, tts_task))
                                        voice_chunks_emitted += 1
                                    else:
                                        voice_chunk_buffer = (
                                            f"{voice_chunk_buffer} {complete_sentence}".strip()
                                            if voice_chunk_buffer else complete_sentence
                                        )
                                        should_flush = (
                                            len(voice_chunk_buffer) >= 140
                                            or voice_chunk_buffer.count('.') >= 2
                                            or voice_chunk_buffer.count('?') >= 1
                                            or voice_chunk_buffer.count('!') >= 1
                                        )
                                        if should_flush:
                                            chunk = voice_chunk_buffer
                                            voice_chunk_buffer = ""
                                            tts_task = asyncio.create_task(
                                                self._generate_tts_audio(chunk)
                                            )
                                            pending_voice.append((chunk, tts_task))
                                            voice_chunks_emitted += 1
                                else:
                                    # Chat mode: yield text immediately, no TTS
                                    yield f"data: {json.dumps({'type': 'sentence', 'text': complete_sentence, 'audio': None, 'audio_format': None})}\n\n"
                        
                        # Voice mode: yield any sentences whose TTS has completed (in order)
                        if is_voice:
                            while voice_yield_index < len(pending_voice):
                                sent, task = pending_voice[voice_yield_index]
                                if task.done():
                                    try:
                                        audio_b64, audio_format = task.result()
                                    except Exception as e:
                                        logger.warning(f"TTS task {voice_yield_index} failed: {e}")
                                        audio_b64, audio_format = None, None
                                    yield f"data: {json.dumps({'type': 'sentence', 'text': sent, 'audio': audio_b64, 'audio_format': audio_format})}\n\n"
                                    voice_yield_index += 1
                                else:
                                    break
                
                # Handle remaining buffer as final sentence
                remaining = sentence_buffer.strip()
                if remaining and len(remaining) > 2:
                    if is_voice:
                        voice_chunk_buffer = (
                            f"{voice_chunk_buffer} {remaining}".strip()
                            if voice_chunk_buffer else remaining
                        )
                    else:
                        yield f"data: {json.dumps({'type': 'sentence', 'text': remaining, 'audio': None, 'audio_format': None})}\n\n"

                # Flush any buffered voice chunk after stream ends.
                if is_voice and voice_chunk_buffer:
                    tts_task = asyncio.create_task(
                        self._generate_tts_audio(voice_chunk_buffer)
                    )
                    pending_voice.append((voice_chunk_buffer, tts_task))
                
                # Voice mode: yield any remaining sentences (await their TTS)
                if is_voice:
                    while voice_yield_index < len(pending_voice):
                        sent, task = pending_voice[voice_yield_index]
                        try:
                            audio_b64, audio_format = await asyncio.wait_for(task, timeout=_TTS_TIMEOUT_SECONDS)
                        except Exception as e:
                            logger.warning(f"TTS task {voice_yield_index} failed: {e}")
                            audio_b64, audio_format = None, None
                        yield f"data: {json.dumps({'type': 'sentence', 'text': sent, 'audio': audio_b64, 'audio_format': audio_format})}\n\n"
                        voice_yield_index += 1
                
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
        
        # UNCLEAR — Ask the user for clarification
        if intent == 'UNCLEAR':
            unclear_response = "I'm not quite sure what you're looking for. Could you tell me more? I can help you:\n\n1. **Register a Shop** — Set up your business\n2. **Search for Shops** — Find services nearby\n3. **Ask about our Products** — Pricing, features, and more"
            async for event in _yield_sentences_with_tts(unclear_response):
                yield event
            yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        # FALLBACK — Unrecognized intent, use master agent LLM
        logger.info(f"Fallback: non-streaming master agent run (intent={intent})")
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
        ]
    }


def get_learnings_admin():
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