#!/usr/bin/env python3
"""
Test that inventory margin queries route to inventory specialist (fast path)
instead of finance agent (slow LLM path).

This test verifies the routing fix for the 127+ second hang issue.
"""

import re
from typing import Tuple, Optional

# Copy the exact patterns from backend/agents/supervisor.py
_FINANCE_OPERATION_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:revenue|sales)\b.*\b(?:trend|trends|graph|chart|over\s+time|by\s+day|by\s+date|daily\s+breakdown)\b"),
    re.compile(r"\b(?:trend|trends|graph|chart|over\s+time|by\s+day|by\s+date|daily\s+breakdown)\b.*\b(?:revenue|sales)\b"),
    re.compile(r"\b(?:customers?|clients?|visits?|attended|served)\b.*\b(?:per|by|for each|each)\s+(?:service|services)\b"),
    re.compile(r"\b(?:service|services)\b.*\b(?:customers?|clients?|visits?|attended|served|count|counts)\b"),
    re.compile(r"\b(?:this\s+week|weekly|last\s+week)\s*(?:'s)?\s*(?:earnings?|revenue|income|sales|profit)\b", re.IGNORECASE),
    re.compile(r"\b(?:earnings?|revenue|income|sales|profit)\s+(?:for\s+)?(?:this|last)\s+week\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+service\s+(?:makes?|earns?|brings?|generates?)\s+(?:the\s+)?most\b", re.IGNORECASE),
    re.compile(r"\bmost\s+(?:profitable|money|revenue)\b.*\bservice\b", re.IGNORECASE),
    re.compile(r"\bservice\b.*\bmost\s+(?:profitable|money|revenue|popular)\b", re.IGNORECASE),
    re.compile(r"\btop\s+(?:earning|revenue|performing|profitable)\s+service\b", re.IGNORECASE),
)

_INVENTORY_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:inventory|stock|restock|restocking)\b", re.IGNORECASE),
    re.compile(r"\bsuppl(?:y|ies)\b", re.IGNORECASE),
    re.compile(r"\breorder\b", re.IGNORECASE),
    re.compile(r"\b(?:items?\s+in\s+stock|in[\s-]stock|out[\s-]of[\s-]stock|low\s+stock)\b", re.IGNORECASE),
    re.compile(r"\b(?:cogs|cost\s+of\s+goods|usage\s+report)\b", re.IGNORECASE),
    re.compile(r"\b(?:what\s+products?|which\s+products?|products?\s+(?:we|do\s+we|you)\s+(?:carry|sell|have|offer|stock))\b", re.IGNORECASE),
    re.compile(r"\b(?:hair\s+color|hair\s+dye|pomade|clippers?\s+oil|razor\s+blades?|shaving\s+cream|aftershave)\b", re.IGNORECASE),
    # NEW PATTERNS - the fix for 127s hang issue
    re.compile(r"\b(?:retail\s+)?(?:profit\s+)?margin\b.*\b(?:item|product)\b", re.IGNORECASE),
    re.compile(r"\b(?:item|product)\b.*\b(?:retail\s+)?(?:profit\s+)?margin\b", re.IGNORECASE),
    re.compile(r"\b(?:best|highest|most|top)\s+margin\b.*\b(?:item|product)\b", re.IGNORECASE),
    re.compile(r"\b(?:item|product)\b.*\b(?:best|highest|most|top)\s+margin\b", re.IGNORECASE),
    re.compile(r"\bmargin\b.*\b(?:per\s+)?(?:item|product|inventory)\b", re.IGNORECASE),
)


def classify_fastpath(user_input: str) -> Optional[str]:
    """Simplified fastpath classifier matching supervisor.py logic."""
    normalized = " ".join(str(user_input or "").lower().split())
    if not normalized:
        return None

    finance_match = any(p.search(normalized) for p in _FINANCE_OPERATION_PATTERNS)
    if finance_match:
        return "finance"

    inventory_match = any(p.search(normalized) for p in _INVENTORY_PATTERNS)
    if inventory_match:
        return "inventory"

    return None


def test_routing():
    """Test that inventory margin queries route to inventory, not finance."""
    
    test_cases = [
        # Inventory margin queries (should route to inventory)
        ("Which item has the best retail profit margin?", "inventory"),
        ("What's the margin on products?", "inventory"),
        ("Show me product margins", "inventory"),
        ("Which product has the highest margin?", "inventory"),
        ("What's the profit margin per item?", "inventory"),
        ("Show me retail margins for all items", "inventory"),
        ("Which item has the best margin?", "inventory"),
        ("Top margin products", "inventory"),
        
        # Finance service queries (should route to finance)
        ("Which service makes the most money?", "finance"),
        ("What's this week's revenue?", "finance"),
        ("Show me revenue trends", "finance"),
        ("Which service is most profitable?", "finance"),
        
        # Other inventory queries (should route to inventory)
        ("What's in stock?", "inventory"),
        ("Show me inventory", "inventory"),
        ("Low stock alerts", "inventory"),
    ]
    
    print("Testing routing classification...")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for query, expected_route in test_cases:
        actual_route = classify_fastpath(query)
        status = "✓ PASS" if actual_route == expected_route else "✗ FAIL"
        
        if actual_route == expected_route:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} | {query}")
        print(f"         Expected: {expected_route}, Got: {actual_route}")
        print()
    
    print("=" * 80)
    print(f"Results: {passed} PASS / {failed} FAIL / {passed + failed} TOTAL")
    
    if failed == 0:
        print("✓ All routing tests passed! Inventory margin queries will use fast path.")
    else:
        print("✗ Some routing tests failed. Review patterns in supervisor.py.")
    
    return failed == 0


if __name__ == "__main__":
    import sys
    success = test_routing()
    sys.exit(0 if success else 1)
