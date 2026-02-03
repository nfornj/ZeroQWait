from typing import List, Optional, Dict, Any, Literal, Annotated
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from db_interface import db_interface

# Setup logging
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
MODEL_NAME = "llama3.2"

# --- STATE DEFINITION ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    session_id: str
    latitude: Optional[float]
    longitude: Optional[float]
    context: Optional[Dict[str, Any]]
    # We'll use this to pass results back to the caller
    actions: List[Dict[str, Any]]

# --- TOOLS ---

@tool
def search_shops(
    query: Optional[str] = None,
    category: Optional[str] = None,
    city: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None
) -> str:
    """
    Search for shops or businesses. 
    Use this when the user asks to find a place, lists a service (like 'haircut'), or asks what is nearby.
    """
    # Clean query logic (ported from original)
    clean_query = query
    if clean_query:
        noise_words = [
            "find", "search", "show", "list", "get", "display",
            "shops", "shop", "stores", "store", "places", "place", "businesses", "business",
            "me", "a", "the", "some", "any", "all",
            "near", "nearby", "around", "close", "closest", "local",
            "in", "for", "to", "with", "by", "at",
            "please", "can", "you", "could", "would", "i", "want"
        ]
        clean_query = clean_query.lower()
        for noise in noise_words:
            clean_query = clean_query.replace(noise, " ")
        clean_query = " ".join(clean_query.split()).strip()
    
    if not clean_query: 
        clean_query = None

    # Note: In LangChain tools, we don't have direct access to the state 'latitude/longitude' unless passed as args.
    # The LLM should be instructed to populate these from context if available, or we inject them bound to the tool.
    # For simplicity here, we assume the LLM extracts it or we pass it via binding (see MasterAgent).

    result = db_interface.search_shops(
        query=clean_query,
        shop_type=category,
        city=city,
        latitude=latitude,
        longitude=longitude,
        limit=10
    )
    
    # We return a JSON string or description, AND we need to signal the action.
    # Since tools return strings to the LLM, we'll return a description.
    # The 'actions' list generation happens by inspecting tool calls after the run.
    return f"Found {len(result)} shops. The UI has been updated to show them."

@tool
def check_pricing() -> str:
    """View the pricing page and subscription plans."""
    return "Navigated user to pricing page."

@tool
def see_features() -> str:
    """View the features page."""
    return "Navigated user to features page."

@tool
def see_faq() -> str:
    """View the FAQ page."""
    return "Navigated user to FAQ page."

# --- Front Desk Tools ---
@tool
def get_shop_status(shop_id: int) -> str:
    """Get current queue lengths and waiting times for a specific shop."""
    try:
        queues = db_interface.get_queues({"shop_id": shop_id, "is_active": True})
        status_lines = []
        for q in queues:
            items = db_interface.get_queue_items({"queue_id": q["id"]})
            active = [i for i in items if i["status"] in ["waiting", "being_served"]]
            wait_count = len([i for i in active if i["status"] == "waiting"])
            status_lines.append(f"{q['name']}: {wait_count} waiting")
        
        if not status_lines:
            return "No active queues at the moment."
        return "\\n".join(status_lines)
    except Exception as e:
        return f"Error checking status: {str(e)}"

# --- MASTER AGENT ---

class MasterAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=OLLAMA_URL,
            api_key="ollama",
            model=MODEL_NAME,
            temperature=0.1
        )
        self.tools = [search_shops, check_pricing, see_features, see_faq]
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Build Graph
        builder = StateGraph(AgentState)
        builder.add_node("agent", self._agent_node)
        builder.add_node("tools", ToolNode(self.tools))
        
        builder.add_edge(START, "agent")
        builder.add_conditional_edges("agent", self._should_continue)
        builder.add_edge("tools", "agent")
        
        self.graph = builder.compile()

    def _should_continue(self, state: AgentState) -> Literal["tools", END]:
        messages = state['messages']
        last_message = messages[-1]
        
        if last_message.tool_calls:
            return "tools"
        return END

    def _agent_node(self, state: AgentState):
        messages = state['messages']
        last_msg = messages[-1]
        print(f"DEBUG: Last Message Type: {type(last_msg)}")
        print(f"DEBUG: Last Message Content: {last_msg.content}")
        user_text = last_msg.content.lower() if isinstance(last_msg, HumanMessage) else ""
        print(f"DEBUG: Parsed User Text: {user_text}")

        # --- HYBRID INTENT DETECTION (Reliability Layer) ---
        # Force tool calls for clear intents to avoid LLM hallucination
        
        # 1. Shop Search
        shop_keywords = ['shop', 'shops', 'store', 'stores', 'barber', 'salon', 'restaurant', 'find', 'search', 'near me', 'nearby', 'looking for']
        if any(kw in user_text for kw in shop_keywords):
            # Extract basic query if possible, or just default
            tool_call_id = "call_" + os.urandom(4).hex()
            return {"messages": [AIMessage(
                content="", 
                tool_calls=[{
                    "name": "search_shops", 
                    "args": {"query": last_msg.content}, 
                    "id": tool_call_id
                }]
            )]}

        # 2. Pricing
        if any(kw in user_text for kw in ['price', 'pricing', 'cost', 'how much', 'plan', 'subscription']):
            tool_call_id = "call_" + os.urandom(4).hex()
            return {"messages": [AIMessage(
                content="", 
                tool_calls=[{"name": "check_pricing", "args": {}, "id": tool_call_id}]
            )]}

        # 3. Features
        if any(kw in user_text for kw in ['feature', 'features', 'what can you do', 'capabilities']):
            tool_call_id = "call_" + os.urandom(4).hex()
            return {"messages": [AIMessage(
                content="", 
                tool_calls=[{"name": "see_features", "args": {}, "id": tool_call_id}]
            )]}

        # 4. FAQ
        if any(kw in user_text for kw in ['faq', 'help', 'support', 'question']):
            tool_call_id = "call_" + os.urandom(4).hex()
            return {"messages": [AIMessage(
                content="", 
                tool_calls=[{"name": "see_faq", "args": {}, "id": tool_call_id}]
            )]}

        # --- FALLBACK TO LLM ---
        # System prompt injection
        if not isinstance(messages[0], SystemMessage):
            sys_msg = SystemMessage(content="""You are ZeroQ, the AI Assistant for ZeroQwait.
You have NO internal knowledge of real-world shops, pricing, or features.
You MUST use the provided tools to answer questions.

RULES:
1. If the user asks to find, search, or list shops/businesses, you MUST return a tool call to 'search_shops'. DO NOT make up shops.
2. If the user asks about pricing, costs, or plans, you MUST return a tool call to 'check_pricing'.
3. If the user asks about features or capabilities, you MUST return a tool call to 'see_features'.
4. If the user needs help or FAQ, you MUST return a tool call to 'see_faq'.

By default, keep your text response short (e.g., "Let me check that for you...") and let the tool do the work.
""")
            messages = [sys_msg] + messages
            
        response = self.llm_with_tools.invoke(messages)
        return {"messages": [response]}

    async def chat(self, session_id: str, user_msg: str, latitude: float = None, longitude: float = None, history: List[Dict[str, str]] = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        # 1. Convert History
        langchain_history = []
        if history:
            for h in history:
                if h['role'] == 'user':
                    langchain_history.append(HumanMessage(content=h['content']))
                elif h['role'] in ['assistant', 'ai']:
                    langchain_history.append(AIMessage(content=h['content']))
        
        # 2. Add Context Note (Hidden from user, visible to LLM)
        context_str = f"User Context: Lat={latitude}, Lng={longitude}"
        if context and context.get('active_view'):
            context_str += f", ActiveView={context['active_view']}"
        
        # We append a hidden system/human message with context + the actual user message
        # But for 'search_shops' to work well with args, we explicitly mention the lat/long in the prompt context
        combined_msg = f"{user_msg}\n\n[System Context: {context_str}]"
        
        langchain_history.append(HumanMessage(content=combined_msg))

        initial_state: AgentState = {
            "messages": langchain_history,
            "session_id": session_id,
            "latitude": latitude,
            "longitude": longitude,
            "context": context,
            "actions": []
        }

        # 3. Run Graph
        final_state = await self.graph.ainvoke(initial_state)
        
        # 4. Extract Response and Actions
        final_messages = final_state['messages']
        last_msg = final_messages[-1]
        response_text = last_msg.content
        
        # Reconstruct actions from tool calls found in the trace
        actions = []
        for msg in final_messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    t_name = tc['name']
                    t_args = tc['args']
                    
                    if t_name == 'search_shops':
                        # We need to re-run the DB content for the UI artifact? 
                        # Or we can trust that the tool execution happened and we can just pass a marker?
                        # The original code returned the RESULT of the search in the actions.
                        # LangGraph executed the tool, which returned a string summary.
                        # We need the actual data object for the UI.
                        # OPTION: Re-run search strictly for the UI payload, or modify tool to return complex obj (handled by ToolNode?)
                        
                        # Re-running search for actions payload (safe, read-only)
                        # This ensures the UI gets the structured data it expects
                        res = db_interface.search_shops(
                            query=t_args.get('query'),
                            shop_type=t_args.get('category'),
                            city=t_args.get('city'),
                            latitude=t_args.get('latitude') or latitude,
                            longitude=t_args.get('longitude') or longitude,
                            limit=10
                        )
                        actions.append({"tool": "search_shops", "result": res})
                        
                    elif t_name == 'check_pricing':
                        actions.append({"tool": "navigate_to_page_section", "result": {"target": "pricing"}})
                    elif t_name == 'see_features':
                        actions.append({"tool": "navigate_to_page_section", "result": {"target": "features"}})
                    elif t_name == 'see_faq':
                        actions.append({"tool": "navigate_to_page_section", "result": {"target": "faq"}})

        # Fallback for empty response (if tool call was the last thing)
        if not response_text:
            response_text = "I've updated the view for you."

        return {
            "response": str(response_text),
            "actions": actions,
            "agent_name": "ZeroQ (LangGraph)"
        }

# --- FRONT DESK AGENT ---

class FrontDeskAgent:
    def __init__(self, shop_id: int, shop_name: str, ai_agent_name: Optional[str] = None):
        self.shop_id = shop_id
        self.shop_name = shop_name
        self.ai_agent_name = ai_agent_name or shop_name
        
        self.llm = ChatOpenAI(
            base_url=OLLAMA_URL,
            api_key="ollama",
            model=MODEL_NAME,
            temperature=0.2
        )
        self.tools = [get_shop_status] # Add more as needed
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        builder = StateGraph(AgentState)
        builder.add_node("agent", self._agent_node)
        builder.add_node("tools", ToolNode(self.tools))
        
        builder.add_edge(START, "agent")
        builder.add_conditional_edges("agent", self._should_continue)
        builder.add_edge("tools", "agent")
        
        self.graph = builder.compile()

    def _should_continue(self, state: AgentState) -> Literal["tools", END]:
        if state['messages'][-1].tool_calls:
            return "tools"
        return END

    def _agent_node(self, state: AgentState):
        messages = state['messages']
        if not isinstance(messages[0], SystemMessage):
            sys_msg = SystemMessage(content=f"""You are {self.ai_agent_name}, the AI Front Desk for {self.shop_name}.
Manage the queue and answer questions.
Shop ID: {self.shop_id}
Use 'get_shop_status' if asked about wait times or queue length.
Do NOT assist with other shops.
""")
            messages = [sys_msg] + messages
        return {"messages": [self.llm_with_tools.invoke(messages)]}

    async def chat(self, user_message: str, history: List[Dict[str, str]] = []) -> Dict[str, Any]:
        langchain_history = []
        if history:
            for h in history:
                if h['role'] == 'user':
                    langchain_history.append(HumanMessage(content=h['content']))
                elif h['role'] in ['assistant', 'ai']:
                    langchain_history.append(AIMessage(content=h['content']))
        
        langchain_history.append(HumanMessage(content=user_message))

        initial_state: AgentState = {
            "messages": langchain_history,
            "session_id": "shop_session", # Simplified
            "latitude": None,
            "longitude": None,
            "context": {},
            "actions": []
        }

        final_state = await self.graph.ainvoke(initial_state)
        response_text = final_state['messages'][-1].content
        
        # Simplified action extraction for front desk (can be expanded)
        return {
            "response": str(response_text),
            "actions": [],
            "agent_name": self.ai_agent_name
        }
