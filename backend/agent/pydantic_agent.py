"""
Pydantic-AI MasterAgent: data models, system prompt, agent creation, and tools.
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
from agent.regex_constants import (
    _QUEUE_JOIN_REQUEST_RE, _APPOINTMENT_REQUEST_RE, _WAIT_TIME_REQUEST_RE,
    _CANCEL_REGISTRATION_RE, _REGISTRATION_INTERRUPT_INTENTS,
    _build_queue_join_form_event, _build_appointment_form_event,
    _extract_customer_details_for_join,
    _is_shop_queue_join_request, _is_appointment_request, _is_shop_wait_request,
)
from agent.categories import category_manager
from agent.analyzer import unified_query_analyzer, IntentAnalysis, ContextUpdates
from db_interface import db_interface
from redis_client import redis_client

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
    phone: Optional[str] = Field(default=None, description="Optional phone number for notifications"),
    service_name: Optional[str] = Field(default=None, description="Optional service name the customer wants")
) -> str:
    """Join a queue at a specific shop. Use when user wants to get in line."""
    logger.info(f"join_queue called | shop_id={shop_id} | customer={customer_name} | service={service_name}")
    
    result = await asyncio.to_thread(db_interface.join_queue_for_shop, shop_id, customer_name, phone, service_name)
    
    ctx.deps.actions.append({
        "tool": "join_queue",
        "result": result,
        "params": {"shop_id": shop_id, "customer_name": customer_name, "service_name": service_name},
        "timestamp": datetime.now().isoformat()
    })
    
    if result.get("error"):
        return f"Could not join queue: {result['error']}"
    
    svc_info = ""
    if result.get("service_name"):
        svc_info = f" for {result['service_name']} (${result.get('service_cost', 0):.2f})"
    
    return (
        f"Successfully added {result['customer_name']} to {result['shop_name']}{svc_info}! "
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


