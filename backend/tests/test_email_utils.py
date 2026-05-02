"""
Unit tests for shared/email_utils.py.

Tests send_password_reset_email in both:
  - No-password (logging-only) mode — should return True without SMTP call.
  - SMTP success path — verifies the correct server methods are called.
  - SMTP failure path — verifies graceful degradation (still returns True).

No real SMTP server is required.
"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSendPasswordResetEmail:
    """Tests for send_password_reset_email()."""

    def _import(self):
        """Re-import with controlled env vars so module-level constants are fresh."""
        import importlib
        import shared.email_utils as module
        importlib.reload(module)
        return module.send_password_reset_email

    def test_no_password_returns_true(self):
        """When EMAIL_PASSWORD is empty the function logs only and returns True."""
        with patch.dict(os.environ, {"EMAIL_PASSWORD": "", "FRONTEND_URL": "https://example.com"}):
            fn = self._import()
            result = fn("user@example.com", "reset-token-abc")
        assert result is True

    def test_no_password_does_not_open_smtp(self):
        """Without EMAIL_PASSWORD, smtplib.SMTP must not be called."""
        with patch.dict(os.environ, {"EMAIL_PASSWORD": "", "FRONTEND_URL": "https://example.com"}):
            fn = self._import()
            with patch("smtplib.SMTP") as mock_smtp:
                fn("user@example.com", "token")
        mock_smtp.assert_not_called()

    def test_smtp_success_returns_true(self):
        """When SMTP is available and configured correctly, returns True."""
        mock_server = MagicMock()
        mock_smtp_ctx = MagicMock()
        mock_smtp_ctx.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_ctx.__exit__ = MagicMock(return_value=False)

        with patch.dict(os.environ, {
            "EMAIL_PASSWORD": "secret",
            "EMAIL_USER": "bot@example.com",
            "FRONTEND_URL": "https://example.com",
        }):
            fn = self._import()
            with patch("smtplib.SMTP", return_value=mock_smtp_ctx):
                result = fn("recipient@example.com", "tok123")

        assert result is True

    def test_smtp_login_called_with_credentials(self):
        """Server.login() must be called with the configured EMAIL_USER / EMAIL_PASSWORD."""
        mock_server = MagicMock()
        mock_smtp_ctx = MagicMock()
        mock_smtp_ctx.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_ctx.__exit__ = MagicMock(return_value=False)

        with patch.dict(os.environ, {
            "EMAIL_PASSWORD": "app-pass",
            "EMAIL_USER": "sender@example.com",
            "FRONTEND_URL": "https://example.com",
        }):
            fn = self._import()
            with patch("smtplib.SMTP", return_value=mock_smtp_ctx):
                fn("to@example.com", "tok")

        mock_server.login.assert_called_once()
        call_args = mock_server.login.call_args
        assert "sender@example.com" in call_args[0]
        assert "app-pass" in call_args[0]

    def test_smtp_failure_still_returns_true(self):
        """Even if SMTP raises an exception, function returns True (security best practice)."""
        with patch.dict(os.environ, {
            "EMAIL_PASSWORD": "secret",
            "FRONTEND_URL": "https://example.com",
        }):
            fn = self._import()
            with patch("smtplib.SMTP", side_effect=Exception("connection refused")):
                result = fn("user@example.com", "tok")

        assert result is True

    def test_reset_link_contains_token(self, capsys):
        """The reset link embedded in the email must contain the provided token."""
        token = "unique-reset-xyz"
        with patch.dict(os.environ, {
            "EMAIL_PASSWORD": "",
            "FRONTEND_URL": "https://myapp.com",
        }):
            fn = self._import()
            fn("test@example.com", token)

        captured = capsys.readouterr()
        assert token in captured.out

    def test_reset_link_uses_frontend_url(self, capsys):
        """The reset link must use the FRONTEND_URL env variable."""
        frontend_url = "https://custom-domain.io"
        with patch.dict(os.environ, {
            "EMAIL_PASSWORD": "",
            "FRONTEND_URL": frontend_url,
        }):
            fn = self._import()
            fn("test@example.com", "tok")

        captured = capsys.readouterr()
        # The output line contains "Link: <url>" — verify the URL starts with
        # the configured FRONTEND_URL so we can be sure it uses the right domain.
        link_lines = [line for line in captured.out.splitlines() if "Link:" in line]
        assert link_lines, "Expected a 'Link:' line in the output"
        link_value = link_lines[0].split("Link:")[-1].strip()
        assert link_value.startswith(frontend_url), (
            f"Reset link '{link_value}' does not start with FRONTEND_URL '{frontend_url}'"
        )

    def test_starttls_called_on_smtp_success(self):
        """server.starttls() must be called when connecting via SMTP."""
        mock_server = MagicMock()
        mock_smtp_ctx = MagicMock()
        mock_smtp_ctx.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_ctx.__exit__ = MagicMock(return_value=False)

        with patch.dict(os.environ, {
            "EMAIL_PASSWORD": "pass",
            "FRONTEND_URL": "https://example.com",
        }):
            fn = self._import()
            with patch("smtplib.SMTP", return_value=mock_smtp_ctx):
                fn("to@example.com", "tok")

        mock_server.starttls.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
