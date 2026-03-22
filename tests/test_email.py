"""Tests for send_email() in fda_510k_html_watch.py."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import fda_510k_html_watch as module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_smtp_env(monkeypatch, *, host="smtp.example.com", port=587,
                  user="from@example.com", password="secret",
                  mail_to="to@example.com"):
    monkeypatch.setattr(module, "SMTP_HOST", host)
    monkeypatch.setattr(module, "SMTP_PORT", port)
    monkeypatch.setattr(module, "SMTP_USER", user)
    monkeypatch.setattr(module, "SMTP_PASS", password)
    monkeypatch.setattr(module, "MAIL_TO", mail_to)


# ---------------------------------------------------------------------------
# Skip conditions (missing env)
# ---------------------------------------------------------------------------

def test_send_email_skips_when_smtp_user_is_none(monkeypatch, caplog):
    _set_smtp_env(monkeypatch, user=None)
    module.send_email("Subject", "<p>body</p>")
    assert "SMTP env not set" in caplog.text


def test_send_email_skips_when_smtp_pass_is_none(monkeypatch, caplog):
    _set_smtp_env(monkeypatch, password=None)
    module.send_email("Subject", "<p>body</p>")
    assert "SMTP env not set" in caplog.text


def test_send_email_skips_when_mail_to_is_none(monkeypatch, caplog):
    _set_smtp_env(monkeypatch, mail_to=None)
    module.send_email("Subject", "<p>body</p>")
    assert "SMTP env not set" in caplog.text


# ---------------------------------------------------------------------------
# Successful send
# ---------------------------------------------------------------------------

def test_send_email_calls_smtp_with_correct_host_and_port(monkeypatch):
    _set_smtp_env(monkeypatch, host="smtp.gmail.com", port=587)
    mock_smtp = MagicMock()
    mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_smtp.return_value)
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

    with patch("fda_510k_html_watch.smtplib.SMTP", mock_smtp):
        module.send_email("Subject", "<p>body</p>")

    mock_smtp.assert_called_once_with("smtp.gmail.com", 587)


def test_send_email_performs_starttls_and_login(monkeypatch):
    _set_smtp_env(monkeypatch, user="u@example.com", password="pw")
    smtp_instance = MagicMock()
    mock_smtp = MagicMock()
    mock_smtp.return_value.__enter__ = MagicMock(return_value=smtp_instance)
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

    with patch("fda_510k_html_watch.smtplib.SMTP", mock_smtp):
        module.send_email("Subject", "<p>body</p>")

    smtp_instance.starttls.assert_called_once()
    smtp_instance.login.assert_called_once_with("u@example.com", "pw")


def test_send_email_sendmail_uses_correct_addresses(monkeypatch):
    _set_smtp_env(monkeypatch, user="from@example.com", mail_to="to@example.com")
    smtp_instance = MagicMock()
    mock_smtp = MagicMock()
    mock_smtp.return_value.__enter__ = MagicMock(return_value=smtp_instance)
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

    with patch("fda_510k_html_watch.smtplib.SMTP", mock_smtp):
        module.send_email("My Subject", "<b>hello</b>")

    args = smtp_instance.sendmail.call_args
    from_addr, to_addrs, msg_str = args[0]
    assert from_addr == "from@example.com"
    assert "to@example.com" in to_addrs
    assert "My Subject" in msg_str


def test_send_email_message_contains_html_body(monkeypatch):
    """MIMEText serializes UTF-8 HTML as base64; decode the payload to verify body."""
    import email as email_lib

    _set_smtp_env(monkeypatch)
    smtp_instance = MagicMock()
    mock_smtp = MagicMock()
    mock_smtp.return_value.__enter__ = MagicMock(return_value=smtp_instance)
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

    with patch("fda_510k_html_watch.smtplib.SMTP", mock_smtp):
        module.send_email("Subject", "<strong>important</strong>")

    _, _, msg_str = smtp_instance.sendmail.call_args[0]
    parsed = email_lib.message_from_string(msg_str)
    body = parsed.get_payload(decode=True).decode("utf-8")
    assert "<strong>important</strong>" in body


# ---------------------------------------------------------------------------
# SMTP error handling
# ---------------------------------------------------------------------------

def test_send_email_handles_smtp_exception_gracefully(monkeypatch, caplog):
    _set_smtp_env(monkeypatch)
    mock_smtp = MagicMock()
    mock_smtp.return_value.__enter__ = MagicMock(side_effect=Exception("connection refused"))
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

    with patch("fda_510k_html_watch.smtplib.SMTP", mock_smtp):
        # Should not raise
        module.send_email("Subject", "<p>body</p>")

    assert "Error sending email" in caplog.text
