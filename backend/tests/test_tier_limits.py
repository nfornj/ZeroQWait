"""
Unit tests for tier_limits.py.

Tests tier configuration correctness and get_tier_limit() helper.
No external dependencies required.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tier_limits import TIER_LIMITS, get_tier_limit


class TestTierLimitsStructure:
    """Verify TIER_LIMITS has the expected shape and required tiers."""

    def test_free_tier_present(self):
        assert "free" in TIER_LIMITS

    def test_premium_tier_present(self):
        assert "premium" in TIER_LIMITS

    def test_free_tier_has_required_keys(self):
        required = {"max_queue_size", "max_shops", "max_queues_per_shop", "features"}
        assert required.issubset(TIER_LIMITS["free"].keys())

    def test_premium_tier_has_required_keys(self):
        required = {"max_queue_size", "max_shops", "max_queues_per_shop", "features"}
        assert required.issubset(TIER_LIMITS["premium"].keys())

    def test_premium_limits_exceed_free(self):
        free = TIER_LIMITS["free"]
        premium = TIER_LIMITS["premium"]
        assert premium["max_queue_size"] > free["max_queue_size"]
        assert premium["max_shops"] > free["max_shops"]
        assert premium["max_queues_per_shop"] >= free["max_queues_per_shop"]

    def test_features_are_lists(self):
        assert isinstance(TIER_LIMITS["free"]["features"], list)
        assert isinstance(TIER_LIMITS["premium"]["features"], list)

    def test_free_features_not_empty(self):
        assert len(TIER_LIMITS["free"]["features"]) > 0

    def test_premium_features_not_empty(self):
        assert len(TIER_LIMITS["premium"]["features"]) > 0

    def test_all_numeric_limits_are_positive(self):
        for tier_name, tier in TIER_LIMITS.items():
            for key in ("max_queue_size", "max_shops", "max_queues_per_shop"):
                value = tier[key]
                assert isinstance(value, int), f"{tier_name}.{key} must be int"
                assert value > 0, f"{tier_name}.{key} must be positive"


class TestGetTierLimit:
    """Tests for the get_tier_limit() helper function."""

    def test_known_tier_known_key_returns_value(self):
        result = get_tier_limit("free", "max_queue_size")
        assert result == TIER_LIMITS["free"]["max_queue_size"]

    def test_premium_max_shops(self):
        result = get_tier_limit("premium", "max_shops")
        assert result == TIER_LIMITS["premium"]["max_shops"]

    def test_unknown_tier_falls_back_to_free(self):
        """Unknown tier names should fall back to the free tier defaults."""
        result = get_tier_limit("enterprise", "max_queue_size")
        assert result == TIER_LIMITS["free"]["max_queue_size"]

    def test_unknown_key_returns_none(self):
        result = get_tier_limit("free", "nonexistent_limit")
        assert result is None

    def test_unknown_tier_unknown_key_returns_none(self):
        result = get_tier_limit("gold", "nonexistent_limit")
        assert result is None

    def test_empty_tier_falls_back_to_free(self):
        result = get_tier_limit("", "max_queue_size")
        assert result == TIER_LIMITS["free"]["max_queue_size"]

    def test_free_max_queues_per_shop(self):
        result = get_tier_limit("free", "max_queues_per_shop")
        assert result == TIER_LIMITS["free"]["max_queues_per_shop"]

    def test_premium_max_queues_per_shop(self):
        result = get_tier_limit("premium", "max_queues_per_shop")
        assert result == TIER_LIMITS["premium"]["max_queues_per_shop"]

    def test_features_key_returns_list(self):
        result = get_tier_limit("free", "features")
        assert isinstance(result, list)

    def test_premium_features_includes_analytics(self):
        features = get_tier_limit("premium", "features")
        assert any("analytics" in f.lower() for f in features)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
