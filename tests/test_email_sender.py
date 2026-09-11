from unittest.mock import MagicMock, patch

from src.utils import email_sender


def _smtp_capture():
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    return smtp


def test_recipients_override_ignores_team_list(monkeypatch):
    monkeypatch.setenv("EMAIL_SENDER", "bot@example.com")
    monkeypatch.setenv("EMAIL_APP_PASSWORD", "pw")
    monkeypatch.setenv("EMAIL_RECIPIENTS", "a@example.com,b@example.com")
    smtp = _smtp_capture()
    with patch.object(email_sender.smtplib, "SMTP", return_value=smtp):
        ok = email_sender.send_daily_email(
            "s", "<p>x</p>", recipients=["alert@example.com"])
    assert ok
    _, to, raw = smtp.sendmail.call_args.args
    assert to == ["alert@example.com"]
    assert b"a@example.com" not in raw


def test_default_recipients_come_from_env(monkeypatch):
    monkeypatch.setenv("EMAIL_SENDER", "bot@example.com")
    monkeypatch.setenv("EMAIL_APP_PASSWORD", "pw")
    monkeypatch.setenv("EMAIL_RECIPIENTS", "a@example.com, b@example.com")
    smtp = _smtp_capture()
    with patch.object(email_sender.smtplib, "SMTP", return_value=smtp):
        email_sender.send_daily_email("s", "<p>x</p>")
    assert smtp.sendmail.call_args.args[1] == ["a@example.com", "b@example.com"]


def test_email_configured(monkeypatch):
    for k in ("EMAIL_SENDER", "EMAIL_APP_PASSWORD", "EMAIL_RECIPIENTS"):
        monkeypatch.setenv(k, "x")
    assert email_sender.email_configured()
    monkeypatch.delenv("EMAIL_APP_PASSWORD")
    assert not email_sender.email_configured()
