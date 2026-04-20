"""
Unit tests for PostgreSQL RLS ContextVar wiring in database.py.

Verifies that:
1. set_current_user_for_request() stores the user_id in the ContextVar.
2. The SQLAlchemy after_begin event listener calls SET CONFIG with the correct uid.
3. Clearing the user (None) emits an empty string to reset the RLS context.
"""
import sys
import os
from unittest.mock import MagicMock, call
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import database as db_module
from database import set_current_user_for_request, _current_user_id, _on_session_begin


class TestRLSContextVar:

    def setup_method(self):
        # Reset ContextVar to a clean state before each test.
        _current_user_id.set(None)

    def test_set_current_user_stores_value(self):
        set_current_user_for_request(99)
        assert _current_user_id.get() == 99

    def test_clear_current_user(self):
        set_current_user_for_request(99)
        set_current_user_for_request(None)
        assert _current_user_id.get() is None

    def test_event_listener_sets_config_when_user_present(self):
        """_on_session_begin() must call set_config with the user_id when set."""
        set_current_user_for_request(42)

        mock_conn = MagicMock()
        _on_session_begin(session=None, transaction=None, connection=mock_conn)

        # Find the set_config call among all execute calls.
        executed = [str(c.args[0]) for c in mock_conn.execute.call_args_list]
        config_calls = [s for s in executed if "set_config" in s]
        assert config_calls, "Expected set_config to be called"

        # Also verify the params passed contain the correct uid.
        found = False
        for c in mock_conn.execute.call_args_list:
            if len(c.args) > 1 and isinstance(c.args[1], dict):
                if c.args[1].get("uid") == "42":
                    found = True
                    break
        assert found, "set_config must be called with uid='42'"

    def test_event_listener_clears_config_when_no_user(self):
        """_on_session_begin() must emit empty string when no user is set."""
        # Ensure ContextVar is None.
        set_current_user_for_request(None)

        mock_conn = MagicMock()
        _on_session_begin(session=None, transaction=None, connection=mock_conn)

        executed = [str(c.args[0]) for c in mock_conn.execute.call_args_list]
        # One of the calls must include set_config with empty string.
        config_calls = [s for s in executed if "set_config" in s and "''" in s]
        assert config_calls, "Expected set_config with empty string when no user"

    def test_tenant_search_path_still_set(self):
        """Existing tenant search_path routing still fires alongside RLS config."""
        from database import set_tenant_for_request
        set_tenant_for_request("tenant_5")
        set_current_user_for_request(7)

        mock_conn = MagicMock()
        _on_session_begin(session=None, transaction=None, connection=mock_conn)

        executed_stmts = [str(c.args[0]) for c in mock_conn.execute.call_args_list]
        # Must set search_path AND set_config.
        path_calls = [s for s in executed_stmts if "search_path" in s.lower()]
        rls_calls = [s for s in executed_stmts if "set_config" in s]
        assert path_calls, "Expected SET search_path call"
        assert rls_calls, "Expected set_config call"

        # Reset tenant state.
        set_tenant_for_request(None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
