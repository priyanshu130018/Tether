from unittest.mock import MagicMock, patch
import pytest

from app.models import ChannelType
from app.notifications.base import mask_sensitive_config
from app.notifications.email import EmailNotificationSender
from app.notifications.registry import NotificationRegistry, default_notification_registry
from app.notifications.slack import SlackNotificationSender
from app.notifications.webhook import WebhookNotificationSender


def test_mask_sensitive_config():
    raw = {
        "smtp_host": "smtp.mailgun.org",
        "smtp_port": 587,
        "username": "postmaster@mailgun.org",
        "password": "super-secret-password-123",
        "auth_token": "bearer-xyz",
        "webhook_url": "https://hooks.slack.com/services/T00/B00/SECRET_TOKEN_XYZ",
        "custom_header": "normal-value",
    }
    masked = mask_sensitive_config(raw)
    assert masked["smtp_host"] == "smtp.mailgun.org"
    assert masked["password"] == "********"
    assert masked["auth_token"] == "********"
    assert masked["webhook_url"] == "https://hooks.slack.com/services/***"
    assert masked["custom_header"] == "normal-value"


def test_email_sender_missing_config():
    sender = EmailNotificationSender()
    success, err = sender.send({}, {"event_type": "OUTAGE"})
    assert not success
    assert "Missing SMTP host" in err


def test_email_sender_success():
    sender = EmailNotificationSender()
    config = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "username": "alerts@example.com",
        "password": "secretpassword",
        "from_email": "alerts@example.com",
        "to_emails": "admin@example.com, ops@example.com",
    }
    event_data = {
        "event_type": "OUTAGE",
        "target_name": "Web App",
        "target_host": "example.com",
        "protocol": "HTTPS",
        "timestamp": "2026-10-02T12:00:00Z",
        "message": "Service is unreachable",
        "metadata": {"consecutive_failures": 3, "error_type": "timeout", "latency_ms": None},
    }

    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

        success, err = sender.send(config, event_data)
        assert success
        assert err is None
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("alerts@example.com", "secretpassword")
        mock_smtp.sendmail.assert_called_once()


def test_slack_sender_success():
    sender = SlackNotificationSender()
    config = {"webhook_url": "https://hooks.slack.com/services/T00/B00/XYZ"}
    event_data = {
        "event_type": "OUTAGE",
        "target_name": "API Service",
        "target_host": "api.domain.com",
        "protocol": "HTTP",
        "timestamp": "2026-10-02T12:00:00Z",
        "message": "500 Internal Server Error",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        success, err = sender.send(config, event_data)
        assert success
        assert err is None
        mock_post.assert_called_once()


def test_slack_sender_invalid_url():
    sender = SlackNotificationSender()
    success, err = sender.send({"webhook_url": "ftp://bad-url"}, {"event_type": "OUTAGE"})
    assert not success
    assert "Invalid Slack webhook URL" in err


def test_webhook_sender_ssrf_protection():
    sender = WebhookNotificationSender()
    
    # Invalid scheme
    success, err = sender.send({"url": "file:///etc/passwd"}, {"event_type": "OUTAGE"})
    assert not success
    assert "Unsupported URL scheme" in err

    # Missing netloc
    success, err = sender.send({"url": "http://"}, {"event_type": "OUTAGE"})
    assert not success
    assert "missing hostname" in err


def test_webhook_sender_success():
    sender = WebhookNotificationSender()
    config = {
        "url": "https://alerts.mycompany.com/webhook",
        "headers": {"Authorization": "Bearer token123"},
    }
    event_data = {
        "event_type": "RECOVERY",
        "target_id": 42,
        "target_name": "Primary Database",
        "target_host": "db.internal",
        "protocol": "TCP",
        "timestamp": "2026-10-02T12:05:00Z",
        "message": "Database port is reachable again",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        success, err = sender.send(config, event_data)
        assert success
        assert err is None
        mock_post.assert_called_once()


def test_notification_registry():
    registry = NotificationRegistry()
    assert not registry.has(ChannelType.EMAIL)

    mock_sender = MagicMock(spec=EmailNotificationSender)
    registry.register(ChannelType.EMAIL, mock_sender)
    assert registry.has(ChannelType.EMAIL)
    assert registry.get(ChannelType.EMAIL) is mock_sender

    with pytest.raises(ValueError, match="No notification sender registered"):
        registry.get("NON_EXISTENT")
