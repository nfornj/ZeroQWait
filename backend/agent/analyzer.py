"""
ContextUpdates / IntentAnalysis models and UnifiedQueryAnalyzer.
"""
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

from agent.config import model
from agent.cache import semantic_cache
from agent.categories import category_manager

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
            system_prompt="""You are a single-pass intent classifier for ZeroQwait, an AI agent platform for service businesses.
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
            system_prompt="""You are ZeroQ, the AI receptionist for ZeroQwait — an AI agent platform for service businesses.

Your ONLY purpose is helping users with:
1. Registering a shop — Setting up their business and AI agent team
2. Searching for shops — Finding services nearby and joining an AI-powered queue
3. Answering questions about our products — Pricing, features, and how the product works

RULES:
- NEVER discuss topics outside ZeroQwait (no weather, no general knowledge, no unrelated recommendations)
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
    # Fast SEARCH detection — (service|shops) near/in (city), or service near me
    _FAST_SEARCH_CITY_RE = re.compile(
        r'\b(?:shops?|businesses?|places?|barbers?|barbershops?|salons?|spas?|clinics?|hospital|'
        r'dentist|dental|auto\s*shops?|mechanic|car\s*wash|gym|fitness|restaurant|cafe|'
        r'pharmacy|service|services|queue|queues)\s+(?:near|in|at|around)\s+'
        r'([A-Za-z][A-Za-z\s\-]{1,40})\b',
        re.IGNORECASE,
    )
    _FAST_SEARCH_FIND_RE = re.compile(
        r'\b(?:find|search|look\s*for|looking\s*for|show\s*me|list|get\s*me|any)\s+'
        r'(?:me\s+)?(?:for\s+)?(?:a\s+|an\s+|the\s+|some\s+)?'
        r'(?:nearby\s+|local\s+|near\s+(?:me\s+)?)?'
        r'(?:barbers?|barbershops?|salons?|spas?|clinics?|hospital|dentist|auto\s*shops?|mechanic|'
        r'car\s*wash|gym|fitness|restaurant|cafe|pharmacy|shops?|service|businesses?)',
        re.IGNORECASE,
    )
    _NON_CITY_PHRASES = frozenset({
        'my area', 'my city', 'my location', 'my neighborhood', 'my neighbourhood',
        'the area', 'this area', 'an area', 'my region', 'my town', 'my place',
        'my home', 'around here', 'here', 'me',
    })
    _FAST_SEARCH_NEAR_ME_RE = re.compile(
        r'\b(?:barbers?|barbershops?|salons?|spas?|clinics?|hospital|dentist|dental|'
        r'auto\s*shops?|mechanic|car\s*wash|gym|fitness|restaurant|cafe|pharmacy|'
        r'shops?|services?|businesses?|places?)\s+(?:near\s*me|nearby)\b'
        r'|'
        r'\b(?:near\s*me|nearby)\s+(?:barbers?|barbershops?|salons?|spas?|clinics?|hospital|'
        r'dentist|dental|auto\s*shops?|mechanic|car\s*wash|gym|services?|shops?|places?)\b',
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

        # SEARCH — "shops/service near/in CITY" pattern (most common query, skips LLM entirely)
        city_search_match = self._FAST_SEARCH_CITY_RE.search(msg)
        if city_search_match:
            city = city_search_match.group(1).strip()
            # Treat non-city phrases ("my area", "my city", etc.) as near_me instead
            if city.lower() in self._NON_CITY_PHRASES:
                svc_match = self._SERVICE_FALLBACK_RE.search(msg)
                search_terms = svc_match.group(1).strip().lower() if svc_match else ""
                return IntentAnalysis(
                    intent='SEARCH', search_terms=search_terms, city=None, near_me=True,
                    specificity="SPECIFIC", platform_target=None, registration_type=None,
                    context_updates=ContextUpdates(last_category=search_terms or None, last_city=None),
                )
            # Extract service type if present
            svc_match = self._SERVICE_FALLBACK_RE.search(msg)
            search_terms = svc_match.group(1).strip().lower() if svc_match else ""
            return IntentAnalysis(
                intent='SEARCH', search_terms=search_terms, city=city, near_me=False,
                specificity="SPECIFIC", platform_target=None, registration_type=None,
                context_updates=ContextUpdates(last_category=search_terms or None, last_city=city),
            )

        # SEARCH — "near me" / "nearby" with a service keyword
        if self._FAST_SEARCH_NEAR_ME_RE.search(msg):
            svc_match = self._SERVICE_FALLBACK_RE.search(msg)
            search_terms = svc_match.group(1).strip().lower() if svc_match else ""
            return IntentAnalysis(
                intent='SEARCH', search_terms=search_terms, city=None, near_me=True,
                specificity="SPECIFIC", platform_target=None, registration_type=None,
                context_updates=ContextUpdates(last_category=search_terms or None, last_city=None),
            )

        # SEARCH — "find/search for (service)" with optional city
        if self._FAST_SEARCH_FIND_RE.search(msg):
            city_match = self._CITY_HINT_RE.search(msg)
            city = city_match.group(1).strip() if city_match else None
            if city and city.lower() in self._NON_CITY_PHRASES:
                city = None
            svc_match = self._SERVICE_FALLBACK_RE.search(msg)
            search_terms = svc_match.group(1).strip().lower() if svc_match else ""
            near_me = bool(re.search(r'\b(near\s*me|nearby)\b', msg, re.IGNORECASE))
            specificity = "SPECIFIC" if (city or search_terms or near_me) else "VAGUE"
            return IntentAnalysis(
                intent='SEARCH', search_terms=search_terms, city=city, near_me=near_me,
                specificity=specificity, platform_target=None, registration_type=None,
                context_updates=ContextUpdates(last_category=search_terms or None, last_city=city),
            )

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
            return "Hello! I'm ZeroQ. Here's what I can do for you:\n\n1. **Register a Shop** — Set up your business and get your own AI agent team\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works\n\nWhat would you like to do?"

unified_query_analyzer = UnifiedQueryAnalyzer()



