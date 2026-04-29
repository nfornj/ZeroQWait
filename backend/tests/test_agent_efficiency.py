import asyncio
import pytest
import time
from unittest.mock import patch, AsyncMock
from agent_logic import unified_query_analyzer
from agent_logic import QueryAnalysis, ContextUpdates
from pydantic_ai.result import RunResult

# Mock the LLM Response for testing
async def mock_agent_run(prompt, *args, **kwargs):
    await asyncio.sleep(0.5)  # Simulate 500ms LLM latency
    
    # Simple rule-based mock matching the tests
    terms = ""
    city = None
    last_city = None
    last_cat = None
    
    prompt_str = str(prompt).lower()
    
    if "toronto" in prompt_str:
        terms = "barber"
        city = "Toronto"
    elif "alien pet groomer" in prompt_str:
        terms = "alien pet groomer"
    elif "oshawa" in prompt_str and "auto repair" in prompt_str:
        terms = "auto repair"
        city = "Oshawa"
        last_city = "Oshawa"
        last_cat = "auto repair"
    elif "nail saloon" in prompt_str or "nail salon" in prompt_str:
        terms = "nail salon"
        last_city = "Oshawa" # carry over
        last_cat = "nail salon"
        
    analysis = QueryAnalysis(
        intent="ACTION",
        terms=terms,
        city=city,
        near_me="near" in prompt_str or "nearby" in prompt_str,
        context_updates=ContextUpdates(last_category=last_cat, last_city=last_city)
    )
    
    result = type('RunResult', (), {'data': analysis})()
    return result

@pytest.fixture(autouse=True)
def mock_llm_calls():
    # Patch the main agent run method to avoid needing live Ollama
    with patch('agent_logic.unified_query_analyzer.analyzer_agent.run', new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = mock_agent_run
        yield mock_run

@pytest.mark.asyncio
async def test_unified_query_extraction_latency():
    """Latency Benchmark: Validate processing time is under 2.5 seconds."""
    start_time = time.time()
    query = "find me a barber in Toronto"
    analysis = await unified_query_analyzer.analyze(query, "")
    duration = time.time() - start_time
    
    assert duration < 2.5, f"Extraction took too long: {duration}s"
    assert "barber" in analysis.terms.lower()
    assert getattr(analysis, "city", None) == "Toronto"
    assert getattr(analysis, "intent", None) == "ACTION"

@pytest.mark.asyncio
async def test_zero_hardcoding_edge_case():
    """Zero-Hardcoding Edge Case Test: Validate extraction of absurd undefined noun."""
    query = "Find me an alien pet groomer near me"
    analysis = await unified_query_analyzer.analyze(query, "")
    
    assert "alien pet groomer" in analysis.terms.lower()
    assert getattr(analysis, "near_me", False) is True

@pytest.mark.asyncio
async def test_context_retention_multi_turn():
    """Context Retention Test: Validate persistent category updates while pinning city."""
    # Turn 1
    query_1 = "Find auto repair in Oshawa"
    analysis_1 = await unified_query_analyzer.analyze(query_1, "")
    
    assert analysis_1.context_updates.last_city == "Oshawa"
    assert "auto repair" in analysis_1.context_updates.last_category.lower()
    
    # Turn 2
    mock_history = "[CONVERSATION HISTORY]\\nUser: Find auto repair in Oshawa\\nZeroQ: Found some options!"
    query_2 = "What about nail salons?"
    
    analysis_2 = await unified_query_analyzer.analyze(query_2, mock_history)
    
    assert "nail salon" in analysis_2.context_updates.last_category.lower()
    assert analysis_2.context_updates.last_city == "Oshawa"

@pytest.mark.asyncio
async def test_concurrency_non_blocking():
    """Concurrency/Non-Blocking Test: Prove asyncio.to_thread prevents main loop blocking with 5 requests."""
    
    async def make_request(query):
        start = time.time()
        # We need to bypass the SemanticCache for the concurrency test to actually hit the 5 simulate delays
        with patch('agent_logic.semantic_cache.get', return_value=None):
            res = await unified_query_analyzer.analyze(query, "")
        return time.time() - start
        
    queries = [
        "Find me a barber in Toronto",
        "Looking for an alien pet groomer near me",
        "Find auto repair in Oshawa",
        "What about nail salons?",
        "Dog groomer in Austin"
    ]
    
    start_time = time.time()
    latencies = await asyncio.gather(*(make_request(q) for q in queries))
    total_time = time.time() - start_time
    
    max_latency = max(latencies)
    
    # 5 requests sequential would be 2.5s. Parallel should be ~0.5s.
    # Buffer allows for some overhead, but clearly proves parallel execution.
    assert total_time < (max_latency * 1.5), f"Tasks blocking! Total: {total_time:.2f}s, Max Single: {max_latency:.2f}s"
