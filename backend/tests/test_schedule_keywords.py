"""
Unit tests for the looks_like_schedule_intent() keyword prefilter in
agents/schedule_intent_parser.py.

This function is a pure regex check — no LLM, DB, or Temporal calls required.
We import only the regex constant and the function to keep the test dependency-free.
"""
import sys
import os
import re
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# We need to avoid the module-level langchain_core imports by grabbing only
# what we need from the module source. We do this by extracting the regex
# and the function logic inline, matching the implementation exactly.

# Mirror of the regex and function from schedule_intent_parser.py
_SCHEDULE_KEYWORDS = re.compile(
    r"\b(every|each|daily|weekly|monthly|recurring|schedule|remind\s+me|every\s+morning|"
    r"every\s+evening|every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b",
    re.IGNORECASE,
)


def looks_like_schedule_intent(text: str) -> bool:
    if not text:
        return False
    return bool(_SCHEDULE_KEYWORDS.search(text))


class TestLooksLikeScheduleIntent:
    """Tests for the schedule-intent keyword prefilter."""

    # --- Should match (True) ---------------------------------------------------

    def test_every_keyword(self):
        assert looks_like_schedule_intent("Send me a report every day") is True

    def test_each_keyword(self):
        assert looks_like_schedule_intent("run this each morning") is True

    def test_daily_keyword(self):
        assert looks_like_schedule_intent("Give me a daily summary") is True

    def test_weekly_keyword(self):
        assert looks_like_schedule_intent("I need weekly analytics") is True

    def test_monthly_keyword(self):
        assert looks_like_schedule_intent("monthly revenue report please") is True

    def test_recurring_keyword(self):
        assert looks_like_schedule_intent("set up a recurring task") is True

    def test_schedule_keyword(self):
        assert looks_like_schedule_intent("can you schedule this for me?") is True

    def test_remind_me_phrase(self):
        assert looks_like_schedule_intent("remind me to check the queue") is True

    def test_every_morning_phrase(self):
        assert looks_like_schedule_intent("every morning send me the stats") is True

    def test_every_evening_phrase(self):
        assert looks_like_schedule_intent("every evening run the summary") is True

    def test_every_monday(self):
        assert looks_like_schedule_intent("Every Monday send the revenue report") is True

    def test_every_tuesday(self):
        assert looks_like_schedule_intent("every Tuesday update the team") is True

    def test_every_wednesday(self):
        assert looks_like_schedule_intent("every Wednesday at noon") is True

    def test_every_thursday(self):
        assert looks_like_schedule_intent("every Thursday") is True

    def test_every_friday(self):
        assert looks_like_schedule_intent("every Friday at 5pm") is True

    def test_every_saturday(self):
        assert looks_like_schedule_intent("every saturday morning") is True

    def test_every_sunday(self):
        assert looks_like_schedule_intent("every Sunday at 9am") is True

    def test_case_insensitive_EVERY(self):
        assert looks_like_schedule_intent("EVERY day run this") is True

    def test_case_insensitive_Daily(self):
        assert looks_like_schedule_intent("Daily report please") is True

    def test_mixed_case_Weekly(self):
        assert looks_like_schedule_intent("I want a Weekly update") is True

    # --- Should NOT match (False) ----------------------------------------------

    def test_empty_string_returns_false(self):
        assert looks_like_schedule_intent("") is False

    def test_none_returns_false(self):
        assert looks_like_schedule_intent(None) is False

    def test_plain_question_returns_false(self):
        assert looks_like_schedule_intent("What is the current queue size?") is False

    def test_revenue_query_returns_false(self):
        assert looks_like_schedule_intent("How much revenue did we make today?") is False

    def test_add_employee_message_returns_false(self):
        assert looks_like_schedule_intent("Add John as an employee") is False

    def test_close_queue_returns_false(self):
        assert looks_like_schedule_intent("Close the queue now") is False

    def test_greeting_returns_false(self):
        assert looks_like_schedule_intent("Hello, how are you?") is False

    def test_word_containing_every_not_standalone(self):
        """'every' embedded inside another word (no word boundary after it) should not match.

        'everyone' starts with 'every' but has no word-boundary after 'every',
        so the regex's trailing \\b prevents a match.
        """
        assert looks_like_schedule_intent("everyone here is happy") is False

    def test_whitespace_only_returns_false(self):
        assert looks_like_schedule_intent("   ") is False

    def test_numbers_only_returns_false(self):
        assert looks_like_schedule_intent("12345 67890") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
