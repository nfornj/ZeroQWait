"""
Unit tests for agents/vertical_profiles.py.

Tests get_vertical_profile() and build_vertical_system_prompt().
No external dependencies required.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.vertical_profiles import get_vertical_profile, build_vertical_system_prompt, _DEFAULT, _VERTICALS


class TestGetVerticalProfile:
    """Tests for get_vertical_profile()."""

    def test_known_vertical_barber(self):
        profile = get_vertical_profile("barber")
        assert profile["label"] == "Barbershop"
        assert "haircut" in profile["vocabulary"].lower()

    def test_known_vertical_salon(self):
        profile = get_vertical_profile("salon")
        assert profile["label"] == "Hair Salon"

    def test_known_vertical_clinic(self):
        profile = get_vertical_profile("clinic")
        assert profile["label"] == "Medical Clinic"

    def test_known_vertical_dental(self):
        profile = get_vertical_profile("dental")
        assert profile["label"] == "Dental Practice"

    def test_known_vertical_auto(self):
        profile = get_vertical_profile("auto")
        assert profile["label"] == "Auto Shop"

    def test_known_vertical_spa(self):
        profile = get_vertical_profile("spa")
        assert profile["label"] == "Spa & Wellness"

    def test_known_vertical_restaurant(self):
        profile = get_vertical_profile("restaurant")
        assert profile["label"] == "Restaurant"

    def test_known_vertical_fitness(self):
        profile = get_vertical_profile("fitness")
        assert profile["label"] == "Fitness / Gym"

    def test_case_insensitive_match(self):
        """Input should be normalized to lowercase."""
        profile = get_vertical_profile("BARBER")
        assert profile["label"] == "Barbershop"

    def test_case_insensitive_mixed(self):
        profile = get_vertical_profile("Salon")
        assert profile["label"] == "Hair Salon"

    def test_unknown_type_returns_default(self):
        profile = get_vertical_profile("artisan_bakery")
        assert profile == _DEFAULT

    def test_empty_string_returns_default(self):
        profile = get_vertical_profile("")
        assert profile == _DEFAULT

    def test_none_returns_default(self):
        profile = get_vertical_profile(None)
        assert profile == _DEFAULT

    def test_prefix_match_barber_shop(self):
        """'barbershop' contains 'barber' so should resolve to barber profile."""
        profile = get_vertical_profile("barbershop")
        assert profile["label"] == "Barbershop"

    def test_all_profiles_have_required_keys(self):
        required = {"label", "vocabulary", "tone", "example_services"}
        for shop_type in _VERTICALS:
            profile = get_vertical_profile(shop_type)
            assert required.issubset(profile.keys()), f"Missing keys in profile for '{shop_type}'"

    def test_default_has_required_keys(self):
        required = {"label", "vocabulary", "tone", "example_services"}
        assert required.issubset(_DEFAULT.keys())

    def test_whitespace_stripped(self):
        profile = get_vertical_profile("  barber  ")
        assert profile["label"] == "Barbershop"


class TestBuildVerticalSystemPrompt:
    """Tests for build_vertical_system_prompt()."""

    def test_returns_string(self):
        result = build_vertical_system_prompt("barber")
        assert isinstance(result, str)

    def test_includes_shop_label(self):
        result = build_vertical_system_prompt("barber")
        assert "Barbershop" in result

    def test_includes_vocabulary(self):
        result = build_vertical_system_prompt("barber")
        assert "haircut" in result.lower()

    def test_includes_tone(self):
        result = build_vertical_system_prompt("barber")
        assert "casual" in result.lower() or "friendly" in result.lower()

    def test_includes_example_services(self):
        result = build_vertical_system_prompt("barber")
        assert "classic cut" in result.lower() or "beard trim" in result.lower()

    def test_unknown_vertical_uses_default_label(self):
        result = build_vertical_system_prompt("unknown_vertical")
        assert "Service Business" in result

    def test_agent_role_does_not_break_output(self):
        result = build_vertical_system_prompt("clinic", agent_role="finance")
        assert "Medical Clinic" in result
        assert len(result) > 50

    def test_output_not_empty(self):
        for shop_type in _VERTICALS:
            result = build_vertical_system_prompt(shop_type)
            assert len(result) > 20, f"Empty prompt for '{shop_type}'"

    def test_prompt_instructs_domain_language(self):
        result = build_vertical_system_prompt("dental")
        assert "domain" in result.lower() or "vocabulary" in result.lower() or "language" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
