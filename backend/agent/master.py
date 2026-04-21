"""
MasterAgent — orchestrates intent routing, chat, and streaming responses.
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
    _SENTENCE_BOUNDARY_RE, _MARKDOWN_BOLD_RE, _MARKDOWN_ITALIC_RE,
    _MARKDOWN_HEADING_RE, _MARKDOWN_CODE_RE, _MARKDOWN_LINK_RE,
    _EMOJI_RE, _WHITESPACE_MULTI_RE,
    _CANCEL_REGISTRATION_RE, _REGISTRATION_INTERRUPT_INTENTS,
    _QUEUE_JOIN_REQUEST_RE, _APPOINTMENT_REQUEST_RE, _WAIT_TIME_REQUEST_RE,
    _TTS_TIMEOUT_SECONDS, _tts_cache, _TTS_CACHE_MAX_ITEMS, _get_tts_client,
    _extract_customer_details_for_join,
    _is_shop_queue_join_request, _is_appointment_request, _is_shop_wait_request,
    _build_queue_join_form_event, _build_appointment_form_event,
)
from agent.cache import semantic_cache
from agent.analyzer import (
    unified_query_analyzer, ContextUpdates, IntentAnalysis, SearchRecoveryAnalysis,
)
from agent.categories import category_manager
from agent.pydantic_agent import (
    master_pydantic_agent, MasterAgentDeps, MasterResponse,
    get_master_system_prompt, create_master_agent,
    search_shops, join_queue, get_wait_time, check_queue_status,
    start_registration, check_pricing, see_features, see_faq, see_testimonials,
)
from db_interface import db_interface
from redis_client import redis_client

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
                    cancel_msg = "Registration cancelled. How else can I help you?\n\n1. **Register a Shop** — Set up your business and get your own AI agent team\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works"
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
            has_appointment_signal = _is_appointment_request(user_msg)
            extracted_name, extracted_phone, extracted_service = _extract_customer_details_for_join(user_msg)

            # Shop landing override: avoid generic location/category search when shop is already known.
            if shop_id and (has_join_signal or has_wait_signal or has_appointment_signal or extracted_name):
                if has_appointment_signal:
                    # Emit inline appointment booking form
                    final_text = f"Let's schedule an appointment at **{shop_name}**. Pick a date and time below:"
                    form_event = _build_appointment_form_event(
                        shop_id=int(shop_id),
                        shop_name=shop_name,
                    )
                    deps.actions.append({
                        "tool": "appointment_form",
                        "form_event": form_event,
                        "timestamp": datetime.now().isoformat()
                    })
                elif has_wait_signal:
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
                        service_name=extracted_service,
                    )
            
            elif intent == 'GREETING':
                final_text = "Hello! I'm ZeroQ, your AI operations assistant. Here's what I can do for you:\n\n1. **Register a Shop** — Set up your business and get your own AI agent team\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works\n\nWhat would you like to do?"
            
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
                        customer_name, customer_phone, customer_service = _extract_customer_details_for_join(user_msg)
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
                                service_name=customer_service,
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
                    'pricing': "Here's our pricing! Free gives you 1 shop and an AI receptionist, Premium unlocks the full AI agent team for $29/mo, and Enterprise is custom.",
                    'features': "Here are our features! AI receptionist flows, live queue and appointment experiences, owner approvals, analytics, and voice interaction.",
                    'faq': "Here are our frequently asked questions!",
                    'testimonials': "Here's what our users are saying!"
                }
                final_text = responses.get(target, "ZeroQwait gives service businesses an AI receptionist for customers and an AI workspace for owners. Check out our pricing and features!")
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

        # --- FEEDBACK COMMAND PREFILTER ---
        # Intercept /feedback or natural feedback phrases before any other processing
        _FEEDBACK_TRIGGER_RE = re.compile(
            r'^/feedback\b'
            r'|^(report\s+(a\s+)?(bug|issue|problem)|submit\s+(a\s+)?feedback|give\s+(a\s+)?feedback'
            r'|i\s+have\s+(a\s+)?feedback|i\s+want\s+to\s+(give|report|submit)\s+(a\s+)?feedback'
            r'|found\s+(a\s+)?(bug|issue))',
            re.IGNORECASE,
        )
        if _FEEDBACK_TRIGGER_RE.match(user_msg.strip()):
            intro = (
                "Of course! I've opened a feedback form for you. "
                "Please describe the issue and attach a screenshot if it helps — "
                "we really appreciate your input!"
            )
            async for event in _yield_sentences_with_tts(intro):
                yield event
            yield f"data: {json.dumps({'type': 'feedback_form', 'session_id': session_id})}\n\n"
            yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
            yield "data: [DONE]\n\n"
            return

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
                cancel_msg = "Registration cancelled. How else can I help you?\n\n1. **Register a Shop** — Set up your business and get your own AI agent team\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works"
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
        
        # --- PRE-ANALYZER PAYMENT OVERRIDE ---
        # Check for shop context + payment signals BEFORE calling expensive analyzer
        shop_id = (context or {}).get("shop_id")
        shop_name = (context or {}).get("shop_name", "this shop")
        _pay_lower = user_msg.lower()
        _PAY_SIGNALS = ["pay", "payment", "checkout", "pay for", "make a payment", "pay online", "card payment", "pay now", "pay bill"]
        _has_pay_signal = shop_id and any(sig in _pay_lower for sig in _PAY_SIGNALS)

        if _has_pay_signal:
            # Extract amount if mentioned (e.g. "pay $50" or "pay 25 dollars")
            import re as _pay_re
            _amt_match = _pay_re.search(r'\$\s*(\d+(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s*(?:dollars?|usd)', _pay_lower)
            _pay_amount = float(_amt_match.group(1) or _amt_match.group(2)) if _amt_match else None

            try:
                from integrations.stripe_client import is_configured as _stripe_ok, create_payment_intent as _create_pi
                if _stripe_ok():
                    if _pay_amount and _pay_amount > 0:
                        _pi = _create_pi(
                            amount_cents=int(round(_pay_amount * 100)),
                            currency="usd",
                            description=f"Payment at {shop_name}",
                            metadata={"shop_id": str(shop_id)},
                        )
                        intro = f"Great! Here's your payment form for **${_pay_amount:.2f}** at **{shop_name}**. Please enter your card details below:"
                        async for event in _yield_sentences_with_tts(intro):
                            yield event
                        yield f"data: {json.dumps({'type': 'payment_form', 'client_secret': _pi['client_secret'], 'payment_intent_id': _pi['id'], 'amount': _pay_amount, 'currency': 'usd', 'shop_name': shop_name, 'shop_id': shop_id})}\n\n"
                        yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    else:
                        # No amount specified — ask for it
                        ask_text = f"I can process your payment at **{shop_name}**. How much would you like to pay? (e.g. \"$50\" or \"25 dollars\")"
                        async for event in _yield_sentences_with_tts(ask_text):
                            yield event
                        yield f"data: {json.dumps({'type': 'actions', 'actions': []})}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                else:
                    logger.warning("Stripe not configured, falling through to normal chat")
            except Exception as pay_err:
                logger.error("Payment intent creation failed: %s", pay_err)

        # --- PRE-ANALYZER SHOP QUEUE OVERRIDE ---
        # Check for shop context + queue join signals BEFORE calling expensive analyzer
        has_join_signal = _is_shop_queue_join_request(user_msg)
        has_wait_signal = _is_shop_wait_request(user_msg)
        extracted_name, extracted_phone, extracted_service = _extract_customer_details_for_join(user_msg)

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
                    service_name=extracted_service,
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
            greeting_response = "Hello! I'm ZeroQ, your AI operations assistant. Here's what I can do for you:\n\n1. **Register a Shop** — Set up your business and get your own AI agent team\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works\n\nWhat would you like to do?"
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
                    customer_name, customer_phone, customer_service = _extract_customer_details_for_join(user_msg)
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
                            service_name=customer_service,
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
                'pricing': "Here's our pricing! **Free** gives you 1 shop and an AI receptionist, **Premium** ($29/mo) unlocks the full AI agent team plus analytics, and **Enterprise** is custom. Take a look below!",
                'features': "Here are our features! ZeroQwait offers AI receptionist flows, live queue and appointment experiences, owner approvals, analytics dashboards, and voice interaction. Check them out below!",
                'faq': "Here are our frequently asked questions! Take a look below for answers to common questions about ZeroQwait.",
                'testimonials': "Here's what our users are saying! Check out the testimonials below."
            }
            response_text = responses.get(target, "Great question! ZeroQwait gives service businesses an AI receptionist for customers and an AI workspace for owners. Check out our pricing and features below!")
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


